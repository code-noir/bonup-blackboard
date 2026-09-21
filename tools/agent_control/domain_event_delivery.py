"""Durable, trusted fan-out for committed Agent Control domain events.

This worker is deliberately a projection dispatcher. It can load facts from
the controller-owned Registry and call an explicitly composed application
boundary, but it has no operation that can create or modify authority.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import threading

from .records import PRODUCT_REVIEW_EVENT_CONSUMERS
from .registry import Registry
from .storage import RegistryBlocked
from .types import ValidationError


EVENT_DELIVERY_CONFIG_PATH = "/etc/bonup-agent-control/event-delivery.json"
_TRANSPORT_IDENTITY = "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1"


class TrustedRuntimeUnavailable(Exception):
    """The server-side application projection boundary is not provisioned."""

    reason = "TRUSTED_RUNTIME_UNAVAILABLE"


class UnavailableProjectionBoundary:
    """Fail-closed default; pending obligations are never discarded."""

    trusted_application_boundary = True
    available = False

    def deliver(self, event, consumer_name):
        raise TrustedRuntimeUnavailable()


@dataclass(frozen=True)
class EventDeliveryConfig:
    """Root-controlled bounded scheduling configuration."""

    enabled: bool
    poll_interval_ms: int
    batch_size: int
    transport_identity: str | None

    @classmethod
    def parse(cls, value):
        if type(value) is not dict or set(value) != {
                "enabled", "poll_interval_ms", "batch_size", "transport_identity"}:
            raise ValidationError("Invalid event delivery configuration.")
        if (type(value["enabled"]) is not bool
                or type(value["poll_interval_ms"]) is not int
                or not 1000 <= value["poll_interval_ms"] <= 60000
                or type(value["batch_size"]) is not int
                or not 1 <= value["batch_size"] <= 100):
            raise ValidationError("Invalid event delivery bounds.")
        identity = value["transport_identity"]
        if identity is not None and (type(identity) is not str or identity != _TRANSPORT_IDENTITY):
            raise ValidationError("Invalid trusted event delivery transport.")
        if value["enabled"] and identity != _TRANSPORT_IDENTITY:
            raise ValidationError("Enabled event delivery requires its trusted transport identity.")
        if not value["enabled"] and identity is not None:
            raise ValidationError("Disabled event delivery cannot declare a transport.")
        return cls(value["enabled"], value["poll_interval_ms"], value["batch_size"], identity)

    @classmethod
    def disabled(cls):
        return cls(False, 5000, 50, None)


_PERMANENT_REASONS = frozenset({
    "EVENT_INVALID", "EVENT_PROVENANCE_MISMATCH", "EVENT_INBOX_MISMATCH",
    "EVENT_BINDING_MISMATCH", "TASK_BINDING_MISMATCH", "PROPOSAL_BINDING_MISMATCH",
    "PROPOSAL_DIGEST_MISMATCH", "ARTIFACT_BINDING_MISMATCH", "ARTIFACT_INVALID",
    "ARTIFACT_MISSING", "AGENT_BINDING_MISMATCH", "KNOWLEDGE_STATE_INVALID",
    "REVIEW_PROJECTION_CONFLICT", "PROJECTION_CONFLICT", "EVENT_TIME_INVALID",
    "PROPOSAL_NOT_AVAILABLE", "REVIEW_NOT_AVAILABLE", "REVIEW_ALREADY_RECORDED",
})


def _bounded_consumer_failure(error):
    reason = getattr(error, "reason", None)
    if type(reason) is str and reason in _PERMANENT_REASONS:
        return reason, False
    return "CONSUMER_RUNTIME_FAILURE", True


def _event_load_failure(error):
    if "Unsupported domain event version" in str(error):
        return "EVENT_UNSUPPORTED_VERSION"
    return "EVENT_INTEGRITY_FAILURE"


class DomainEventDeliveryWorker:
    """Deliver committed events at least once to independent consumers."""

    def __init__(self, registry, boundary=None, *, now=None, batch_size=100):
        if type(registry) is not Registry:
            raise ValidationError("Trusted Agent Control Registry required.")
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ValidationError("Delivery batch size is out of bounds.")
        boundary = UnavailableProjectionBoundary() if boundary is None else boundary
        if (getattr(boundary, "trusted_application_boundary", False) is not True
                or not callable(getattr(boundary, "deliver", None))):
            raise ValidationError("Trusted application projection boundary required.")
        self.registry = registry
        self.boundary = boundary
        self.now = now or (lambda: datetime.now(timezone.utc).isoformat(
            timespec="microseconds").replace("+00:00", "Z"))
        self.batch_size = batch_size

    def run_once(self, *, replay=False):
        rows = self.registry.pending_domain_event_deliveries(
            now=self.now(), limit=self.batch_size, replay=replay)
        summary = {
            "status": "IDLE" if not rows else "DELIVERED",
            "selected": len(rows),
            "acknowledged": 0,
            "retried": 0,
            "blocked": 0,
            "pending": len(rows),
            "replay": bool(replay),
        }
        if not rows:
            return summary
        if not getattr(self.boundary, "available", True):
            summary.update(status="TRUSTED_RUNTIME_UNAVAILABLE",
                           reason="TRUSTED_RUNTIME_UNAVAILABLE")
            return summary

        for row in rows:
            event_id = row["event_id"]
            consumer_name = row["consumer_name"]
            try:
                event = self.registry.load_domain_event(event_id)
            except RegistryBlocked as error:
                reason = _event_load_failure(error)
                self.registry.record_domain_event_delivery_failure(
                    event_id, consumer_name, reason, retryable=False)
                summary["blocked"] += 1
                summary["pending"] -= 1
                continue
            try:
                if (row["event_type"] != event["event_type"]
                        or row["event_digest"] != event["event_digest"]):
                    raise RegistryBlocked("Domain event delivery binding mismatch.")
                self.boundary.deliver(event, consumer_name)
            except TrustedRuntimeUnavailable:
                summary.update(status="TRUSTED_RUNTIME_UNAVAILABLE",
                               reason="TRUSTED_RUNTIME_UNAVAILABLE")
                return summary
            except RegistryBlocked:
                self.registry.record_domain_event_delivery_failure(
                    event_id, consumer_name, "EVENT_INTEGRITY_FAILURE", retryable=False)
                summary["blocked"] += 1
                summary["pending"] -= 1
                continue
            except Exception as error:
                reason, retryable = _bounded_consumer_failure(error)
                outcome = self.registry.record_domain_event_delivery_failure(
                    event_id, consumer_name, reason, retryable=retryable)
                if outcome["status"] == "RETRY":
                    summary["retried"] += 1
                else:
                    summary["blocked"] += 1
                summary["pending"] -= 1
                continue
            self.registry.acknowledge_domain_event_delivery(event_id, consumer_name)
            summary["acknowledged"] += 1
            summary["pending"] -= 1
        if summary["retried"] or summary["blocked"]:
            summary["status"] = "PARTIAL"
        return summary


class InstalledEventDeliveryRuntime:
    """Recurring delivery lane owned by the installed controller service.

    Each cycle opens its own controller-owned Registry connection. The existing
    controller thread therefore remains the sole owner of its active SQLite
    connection and execution-authority operations stay isolated from delivery.
    """

    def __init__(self, registry_path, config, boundary, *, open_registry):
        if type(config) is not EventDeliveryConfig:
            raise ValidationError("Event delivery configuration required.")
        if (type(registry_path) is not str or not registry_path.startswith("/")
                or ".." in registry_path.split("/")):
            raise ValidationError("Absolute Agent Control registry path required.")
        if not callable(open_registry):
            raise ValidationError("Trusted Agent Control registry opener required.")
        if (getattr(boundary, "trusted_application_boundary", False) is not True
                or not callable(getattr(boundary, "deliver", None))):
            raise ValidationError("Trusted application projection boundary required.")
        self.registry_path = registry_path
        self.config = config
        self.boundary = boundary
        self.open_registry = open_registry
        self.stop_event = threading.Event()
        self.thread = None
        self._lock = threading.RLock()
        self._snapshot = {
            "status": "DISABLED" if not config.enabled else "STOPPED",
            "pending": None,
            "retrying": None,
            "blocked": None,
            "last_cycle_at": None,
            "last_successful_cycle_at": None,
            "reason": None,
        }

    def _record(self, snapshot):
        with self._lock:
            self._snapshot = dict(snapshot)

    def run_once(self):
        if not self.config.enabled:
            return self.status()
        try:
            registry = self.open_registry(self.registry_path)
        except (OSError, RegistryBlocked, ValidationError):
            snapshot = dict(self.status(), status="REGISTRY_UNAVAILABLE",
                            reason="REGISTRY_UNAVAILABLE")
            self._record(snapshot)
            return snapshot
        try:
            summary = DomainEventDeliveryWorker(
                registry, self.boundary, batch_size=self.config.batch_size
            ).run_once()
            counts = registry.domain_event_delivery_status()
            now = datetime.now(timezone.utc).isoformat(
                timespec="microseconds").replace("+00:00", "Z")
            successful = summary["status"] in {"IDLE", "DELIVERED", "PARTIAL"}
            snapshot = {
                "status": summary["status"],
                "pending": counts["pending"],
                "retrying": counts["retrying"],
                "blocked": counts["blocked"],
                "last_cycle_at": now,
                "last_successful_cycle_at": now if successful else self.status()["last_successful_cycle_at"],
                "reason": summary.get("reason"),
            }
            self._record(snapshot)
            return snapshot
        except (OSError, RegistryBlocked, ValidationError):
            snapshot = dict(self.status(), status="REGISTRY_UNAVAILABLE",
                            reason="REGISTRY_UNAVAILABLE")
            self._record(snapshot)
            return snapshot
        except BaseException:
            snapshot = dict(self.status(), status="DELIVERY_RUNTIME_FAILURE",
                            reason="DELIVERY_RUNTIME_FAILURE")
            self._record(snapshot)
            return snapshot
        finally:
            registry.close()

    def _run(self):
        self.run_once()
        while not self.stop_event.wait(self.config.poll_interval_ms / 1000):
            self.run_once()

    def start(self):
        if not self.config.enabled:
            return self.status()
        with self._lock:
            if self.thread is not None and self.thread.is_alive():
                raise ValidationError("Event delivery runtime already started.")
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._run, name="agent-event-delivery", daemon=True
            )
            self.thread.start()
        return self.status()

    def shutdown(self):
        self.stop_event.set()
        thread = self.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(2)
        with self._lock:
            if self.config.enabled and self._snapshot["status"] not in {
                    "DELIVERY_RUNTIME_FAILURE", "REGISTRY_UNAVAILABLE"}:
                self._snapshot["status"] = "STOPPED"

    def status(self):
        with self._lock:
            return dict(self._snapshot)


__all__ = [
    "DomainEventDeliveryWorker",
    "EVENT_DELIVERY_CONFIG_PATH",
    "EventDeliveryConfig",
    "InstalledEventDeliveryRuntime",
    "PRODUCT_REVIEW_EVENT_CONSUMERS",
    "TrustedRuntimeUnavailable",
    "UnavailableProjectionBoundary",
]
