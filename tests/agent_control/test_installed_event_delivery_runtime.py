"""Installed controller ownership and scheduling for domain-event delivery."""
import threading
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import os
from uuid import uuid4

import test_service_runtime as service_fixtures
from tools.agent_control.domain_event_delivery import (
    EventDeliveryConfig,
    InstalledDjangoProjectionBoundary,
    InstalledEventDeliveryRuntime,
    TrustedRuntimeUnavailable,
    UnavailableProjectionBoundary,
)
from tools.agent_control.installed_runtime import KernelIO
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2
from tools.agent_control.types import ValidationError


class FakeRegistry:
    def __init__(self):
        self.closed = False

    def domain_event_delivery_status(self):
        return {"pending": 0, "retrying": 0, "blocked": 0, "acknowledged": 0}

    def close(self):
        self.closed = True


class FakeBoundary:
    trusted_application_boundary = True
    available = True

    def deliver(self, event, consumer_name):
        raise AssertionError("The scheduler test must not bypass the worker.")


class InstalledEventDeliveryRuntimeTests(unittest.TestCase):
    def enabled_config(self):
        return EventDeliveryConfig.parse({
            "enabled": True,
            "poll_interval_ms": 1000,
            "batch_size": 7,
            "transport_identity": "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1",
            "socket_path": "/run/bonup-agent-control/django-events.sock",
            "socket_mode": 0o600,
            "agent_control": {"uid": os.geteuid(), "gid": os.getegid()},
            "django": {"uid": os.geteuid(), "gid": os.getegid()},
            "timeout_ms": 1000,
            "max_message_bytes": 4096,
        })

    def test_configuration_is_explicit_bounded_and_fail_closed(self):
        config = self.enabled_config()
        self.assertEqual((config.poll_interval_ms, config.batch_size), (1000, 7))
        for invalid in (
            {"enabled": True, "poll_interval_ms": 999, "batch_size": 7,
             "transport_identity": "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1"},
            {"enabled": True, "poll_interval_ms": 1000, "batch_size": 7,
             "transport_identity": None},
            {"enabled": False, "poll_interval_ms": 1000, "batch_size": 7,
             "transport_identity": "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                EventDeliveryConfig.parse(invalid)

    def test_controller_owned_runtime_starts_worker_and_restarts_pending_lane(self):
        opened = []
        calls = []
        first_cycle = threading.Event()

        class Worker:
            def __init__(self, registry, boundary, *, batch_size):
                calls.append((registry, boundary, batch_size))

            def run_once(self):
                first_cycle.set()
                return {"status": "IDLE", "reason": None}

        def open_registry(path):
            self.assertEqual(path, "/var/lib/bonup-agent-control/control.sqlite3")
            registry = FakeRegistry()
            opened.append(registry)
            return registry

        runtime = InstalledEventDeliveryRuntime(
            "/var/lib/bonup-agent-control/control.sqlite3",
            self.enabled_config(), FakeBoundary(), open_registry=open_registry,
        )
        with patch("tools.agent_control.domain_event_delivery.DomainEventDeliveryWorker", Worker):
            runtime.start()
            self.assertTrue(first_cycle.wait(1))
            runtime.shutdown()
            first_cycle.clear()
            runtime.start()
            self.assertTrue(first_cycle.wait(1))
            runtime.shutdown()

        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(all(call[2] == 7 for call in calls))
        self.assertTrue(all(registry.closed for registry in opened))
        self.assertEqual(runtime.status()["status"], "STOPPED")

    def test_unavailable_registry_keeps_runtime_bounded_and_fail_closed(self):
        runtime = InstalledEventDeliveryRuntime(
            "/var/lib/bonup-agent-control/control.sqlite3",
            self.enabled_config(), FakeBoundary(),
            open_registry=lambda _path: (_ for _ in ()).throw(OSError("unavailable")),
        )
        with patch("tools.agent_control.domain_event_delivery.DomainEventDeliveryWorker") as worker:
            result = runtime.run_once()
        self.assertEqual(result["status"], "REGISTRY_UNAVAILABLE")
        self.assertEqual(result["reason"], "REGISTRY_UNAVAILABLE")
        worker.assert_not_called()

    def test_unavailable_trusted_application_boundary_is_the_installed_default(self):
        boundary = KernelIO().event_delivery_boundary()
        self.assertIsInstance(boundary, UnavailableProjectionBoundary)
        self.assertFalse(boundary.available)
        with self.assertRaises(TrustedRuntimeUnavailable):
            boundary.deliver({}, "product-direction")

    def test_valid_enabled_configuration_selects_the_fixed_af_unix_adapter(self):
        boundary = KernelIO().event_delivery_boundary(self.enabled_config())
        self.assertIsInstance(boundary, InstalledDjangoProjectionBoundary)
        self.assertTrue(boundary.available)

    def test_disabled_runtime_does_not_open_registry_or_start_thread(self):
        runtime = InstalledEventDeliveryRuntime(
            "/var/lib/bonup-agent-control/control.sqlite3",
            EventDeliveryConfig.disabled(), FakeBoundary(),
            open_registry=lambda _path: self.fail("disabled runtime opened registry"),
        )
        self.assertEqual(runtime.start()["status"], "DISABLED")
        self.assertEqual(runtime.run_once()["status"], "DISABLED")
        runtime.shutdown()
        self.assertIsNone(runtime.thread)

    def test_controller_service_owns_runtime_start_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "control.sqlite3"
            with ExitStack() as patches:
                patches.enter_context(patch(
                    "tools.agent_control.registry.external_path",
                    lambda value: Path(value).absolute(),
                ))
                patches.enter_context(patch(
                    "tools.agent_control.storage.external_path",
                    lambda value: Path(value).absolute(),
                ))
                patches.enter_context(patch(
                    "tools.agent_control.publication.external_path",
                    lambda value: Path(value).absolute(),
                ))
                with Registry.initialize(
                    registry_path, Path(directory) / "history.git", operation_id=str(uuid4())
                ) as registry:
                    migrate_v2(registry)
            adapters = service_fixtures.Adapters("controller", registry_path)
            runtime = Mock()
            runtime.status.return_value = {"status": "RUNNING"}
            adapters.driver.event_delivery_runtime = runtime
            with ExitStack() as patches:
                patches.enter_context(patch(
                    "tools.agent_control.registry.external_path",
                    lambda value: Path(value).absolute(),
                ))
                patches.enter_context(patch(
                    "tools.agent_control.storage.external_path",
                    lambda value: Path(value).absolute(),
                ))
                patches.enter_context(patch(
                    "tools.agent_control.publication.external_path",
                    lambda value: Path(value).absolute(),
                ))
                service = service_fixtures.controller_entry.start(adapters=adapters)
                try:
                    runtime.start.assert_called_once_with()
                    self.assertEqual(service.event_delivery_status(), {"status": "RUNNING"})
                finally:
                    service.close()
            runtime.shutdown.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
