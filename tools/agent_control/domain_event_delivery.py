"""Durable, trusted fan-out for committed Agent Control domain events.

This worker is deliberately a projection dispatcher. It can load facts from
the controller-owned Registry and call an explicitly composed application
boundary, but it has no operation that can create or modify authority.
"""
from datetime import datetime, timezone

from .records import PRODUCT_REVIEW_EVENT_CONSUMERS
from .registry import Registry
from .storage import RegistryBlocked
from .types import ValidationError


class TrustedRuntimeUnavailable(Exception):
    """The server-side application projection boundary is not provisioned."""

    reason = "TRUSTED_RUNTIME_UNAVAILABLE"


class UnavailableProjectionBoundary:
    """Fail-closed default; pending obligations are never discarded."""

    trusted_application_boundary = True
    available = False

    def deliver(self, event, consumer_name):
        raise TrustedRuntimeUnavailable()


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


__all__ = [
    "DomainEventDeliveryWorker",
    "PRODUCT_REVIEW_EVENT_CONSUMERS",
    "TrustedRuntimeUnavailable",
    "UnavailableProjectionBoundary",
]
