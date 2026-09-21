import os
import socket
import struct
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.core.settings")
import django
django.setup()

from tools.agent_control.domain_event_delivery import (
    EventDeliveryConfig, InstalledDjangoProjectionBoundary,
    TrustedProjectionFailure, TrustedRuntimeUnavailable,
)
from tools.agent_control.installed_transport import (
    DjangoProjectionClient, ProjectionTransportRejected, ProjectionTransportUnavailable, packet,
)
from tools.agent_control.records import ProductReviewCompletedEvent
from tools.agent_control.serialization import digest
from tools.agent_control.types import ValidationError

from backend.api.event_delivery import (
    TrustedDjangoProjectionBoundary, TrustedDjangoProjectionReceiver,
)


class RecordingBoundary:
    trusted_application_boundary = True
    available = True

    def __init__(self, reason=None):
        self.calls = []
        self.reason = reason

    def deliver(self, event, consumer_name):
        self.calls.append((event, consumer_name))
        if self.reason:
            error = RuntimeError(self.reason)
            error.reason = self.reason
            raise error
        return {"status": "APPLIED", "event_id": event["event_id"]}


def event():
    value = {
        "event_version": 1,
        "event_id": str(uuid4()),
        "event_type": "PRODUCT_REVIEW_COMPLETED",
        "occurred_at": "2026-09-20T00:00:00Z",
        "review_id": str(uuid4()),
        "review_digest": "a" * 64,
        "task_id": "ATS-1234",
        "agent_id": "PROD-01",
        "artifact_id": "PROD-01-00000000-0000-4000-8000-000000000701",
        "artifact_digest": "b" * 64,
        "proposal_id": "00000000-0000-4000-8000-000000000701",
        "proposal_digest": "c" * 64,
        "decision": "ACCEPT",
        "prior_knowledge_state": "WORKING",
        "resulting_knowledge_state": "APPROVED_INTERNAL",
        "operation_id": str(uuid4()),
        "correlation_id": None,
    }
    value["correlation_id"] = value["operation_id"]
    value["event_digest"] = digest(value)
    result = ProductReviewCompletedEvent(value)
    object.__setattr__(result, "_trusted", True)
    return result


class ProjectionTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=str(Path.home())
        )
        self.path = str(Path(self.temp.name) / "django-events.sock")
        uid, gid = os.geteuid(), os.getegid()
        self.config = EventDeliveryConfig.parse({
            "enabled": True,
            "poll_interval_ms": 1000,
            "batch_size": 10,
            "transport_identity": "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1",
            "socket_path": self.path,
            "socket_mode": 0o600,
            "agent_control": {"uid": uid, "gid": gid},
            "django": {"uid": uid, "gid": gid},
            "timeout_ms": 1000,
            "max_message_bytes": 4096,
        })
        self.addCleanup(self.temp.cleanup)

    def receiver(self, boundary=None, config=None):
        receiver = TrustedDjangoProjectionReceiver(
            self.config if config is None else config,
            boundary=boundary or RecordingBoundary(),
        ).bind()
        self.addCleanup(receiver.close)
        return receiver

    def deliver_once(self, receiver, boundary, consumer="product-direction"):
        result = []
        thread = threading.Thread(target=lambda: result.append(receiver.serve_once()))
        thread.start()
        response = InstalledDjangoProjectionBoundary(self.config).deliver(event(), consumer)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        return response, result[0]

    def test_both_registered_consumers_deliver_over_authenticated_socket(self):
        boundary = RecordingBoundary()
        receiver = self.receiver(boundary)
        first = self.deliver_once(receiver, boundary, "product-direction")
        second = self.deliver_once(receiver, boundary, "blackboard-product-direction")
        self.assertEqual(first[0]["status"], "ACKNOWLEDGED")
        self.assertEqual(second[0]["status"], "ACKNOWLEDGED")
        self.assertEqual([name for _, name in boundary.calls], [
            "product-direction", "blackboard-product-direction",
        ])
        self.assertTrue(all(getattr(item, "_trusted", False) for item, _ in boundary.calls))

    def test_transport_invokes_existing_django_consumers_independently(self):
        receiver = self.receiver(TrustedDjangoProjectionBoundary())
        with patch("backend.api.event_delivery.consume_product_direction") as product, \
                patch("backend.api.event_delivery.consume_blackboard") as blackboard:
            first = self.deliver_once(receiver, None, "product-direction")
            second = self.deliver_once(receiver, None, "blackboard-product-direction")
        self.assertEqual(first[0]["status"], "ACKNOWLEDGED")
        self.assertEqual(second[0]["status"], "ACKNOWLEDGED")
        product.assert_called_once()
        blackboard.assert_called_once()

    def test_wrong_peer_is_rejected(self):
        config = replace(self.config, agent_control_uid=self.config.agent_control_uid + 1)
        receiver = self.receiver(config=config)
        result = []
        thread = threading.Thread(target=lambda: result.append(receiver.serve_once()))
        thread.start()
        with self.assertRaises(ProjectionTransportUnavailable):
            DjangoProjectionClient(self.config).deliver(event(), "product-direction")
        thread.join(2)
        self.assertEqual(result[0]["reason"], "TRUSTED_PEER_REJECTED")

    def test_socket_ownership_and_mode_are_verified(self):
        receiver = self.receiver()
        os.chmod(self.path, 0o644)
        with self.assertRaises(TrustedRuntimeUnavailable):
            InstalledDjangoProjectionBoundary(self.config).deliver(event(), "product-direction")
        receiver.close()

    def test_malformed_and_oversized_requests_are_rejected(self):
        receiver = self.receiver()
        for raw in (
            packet({"version": 1, "request_id": str(uuid4())}),
            struct.pack("!I", self.config.max_message_bytes + 1),
        ):
            result = []
            thread = threading.Thread(target=lambda: result.append(receiver.serve_once()))
            thread.start()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect(self.path)
                client.sendall(raw)
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result[0]["status"], "REJECTED")

    def test_invalid_event_digest_and_version_are_rejected(self):
        receiver = self.receiver()
        for mutation in ("digest", "version"):
            value = event().to_dict()
            if mutation == "digest":
                value["event_digest"] = "d" * 64
            else:
                value["event_version"] = 2
            request = {
                "version": 1,
                "request_id": str(uuid4()),
                "consumer_name": "product-direction",
                "event_id": value["event_id"],
                "event_digest": value["event_digest"],
                "event_type": value["event_type"],
                "event_version": value["event_version"],
                "event": value,
            }
            result = []
            thread = threading.Thread(target=lambda: result.append(receiver.serve_once()))
            thread.start()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect(self.path)
                client.sendall(packet(request))
                client.recv(4096)
            thread.join(2)
            self.assertEqual(result[0]["reason"], "MALFORMED_REQUEST")

    def test_consumer_failure_returns_retry_without_acknowledgement(self):
        boundary = RecordingBoundary("PROJECTION_FAILED")
        receiver = self.receiver(boundary)
        result = []
        thread = threading.Thread(target=lambda: result.append(receiver.serve_once()))
        thread.start()
        with self.assertRaises(TrustedProjectionFailure) as raised:
            InstalledDjangoProjectionBoundary(self.config).deliver(event(), "product-direction")
        thread.join(2)
        self.assertEqual(raised.exception.reason, "PROJECTION_FAILED")
        self.assertEqual(result[0]["status"], "RETRY")

    def test_unavailable_socket_is_fail_closed(self):
        with self.assertRaises(TrustedRuntimeUnavailable):
            InstalledDjangoProjectionBoundary(self.config).deliver(event(), "product-direction")

    def test_untrusted_event_never_reaches_socket(self):
        boundary = RecordingBoundary()
        receiver = self.receiver(boundary)
        untrusted = event()
        object.__setattr__(untrusted, "_trusted", False)
        with self.assertRaises(ProjectionTransportRejected):
            DjangoProjectionClient(self.config).deliver(untrusted, "product-direction")
        self.assertEqual(boundary.calls, [])
        receiver.close()

    def test_configuration_rejects_missing_bounds_or_transport_identity(self):
        value = {
            "enabled": True,
            "poll_interval_ms": 1000,
            "batch_size": 10,
            "transport_identity": "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1",
            "socket_path": self.path,
            "socket_mode": 0o600,
            "agent_control": {"uid": os.geteuid(), "gid": os.getegid()},
            "django": {"uid": os.geteuid(), "gid": os.getegid()},
            "timeout_ms": 1000,
            "max_message_bytes": 4096,
        }
        for key, replacement in (("socket_path", "tcp://127.0.0.1"),
                                 ("max_message_bytes", 65537),
                                 ("transport_identity", "AGENT_CONTROL")):
            invalid = dict(value, **{key: replacement})
            with self.subTest(key=key), self.assertRaises(ValidationError):
                EventDeliveryConfig.parse(invalid)


if __name__ == "__main__":
    unittest.main()
