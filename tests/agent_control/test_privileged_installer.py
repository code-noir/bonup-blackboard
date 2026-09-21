"""Installer contract tests; no root, systemd, or host state is touched."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools.agent_control import installation_bundle as bundle
from tools.agent_control import privileged_installer as installer
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2, migrate_v3
from tools.agent_control.types import AuthorityError, ValidationError


class MemoryHost(installer.HostOperations):
    def __init__(self, plan):
        self.accounts = {
            plan.django_account.username: plan.django_account,
        }
        self.groups = {
            plan.django_group.name: plan.django_group,
        }
        self.objects = {}
        self.contents = {}
        self.registry = "ABSENT"
        self.reloads = 0

    def account(self, username): return self.accounts.get(username)
    def account_uid(self, uid):
        return next((row for row in self.accounts.values() if row.uid == uid), None)
    def group(self, name): return self.groups.get(name)
    def group_gid(self, gid):
        return next((row for row in self.groups.values() if row.gid == gid), None)
    def object(self, path): return self.objects.get(path)
    def file_bytes(self, path): return self.contents.get(path)
    def registry_state(self, state_path, history_path): return self.registry

    def create_group(self, group):
        self.groups[group.name] = group

    def create_account(self, account):
        self.accounts[account.username] = account

    def create_directory(self, directory):
        self.objects[directory.path] = installer.HostObject(
            "directory", directory.uid, directory.gid, directory.mode)

    def create_file(self, file):
        self.objects[file.path] = installer.HostObject(
            "unit" if file.kind == "unit" else "file",
            file.uid, file.gid, file.mode)
        self.contents[file.path] = file.content

    def daemon_reload(self): self.reloads += 1


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proposal = json.loads(Path(
            "docs/agent-control/review/m3-generation-1-approval-proposal/"
            "proposed-approval-stage.json").read_text())
        cls.manifest = proposal["installation_manifest"]
        root = Path("docs/agent-control/review/m3-generation-1/payload")
        cls.payloads = {
            row["destination"]: (root / row["destination"].lstrip("/")).read_bytes()
            for row in cls.manifest["artifacts"]
        }

    def options(self):
        return installer.RuntimeInstallOptions(
            33, 33, "www-data", "www-data", "/srv/bonup-web",
            "backend.core.settings", 1000, 10, 500, 2048)

    def plan(self):
        return installer.build_plan(self.manifest, self.payloads, self.options())

    def test_clean_host_plan_is_non_mutating_and_explicit(self):
        plan = self.plan()
        host = MemoryHost(plan)
        before = (dict(host.accounts), dict(host.groups), dict(host.objects))
        report = installer.inspect_host(plan, host)
        self.assertEqual(report["blocking_conflicts"], ())
        self.assertEqual(report["registry"], "ABSENT")
        self.assertEqual(before, (host.accounts, host.groups, host.objects))
        self.assertEqual(plan.activation, "INSTALL_ONLY_NO_SERVICE_ACTIVATION")
        self.assertEqual(plan.projection_socket, installer.PROJECTION_SOCKET)

    def test_install_and_second_install_are_idempotent(self):
        plan = self.plan()
        host = MemoryHost(plan)
        with patch.object(installer, "prepare_registry", side_effect=lambda *a, **k: setattr(host, "registry", "V3") or 3):
            first = installer.apply_plan(plan, host, operation_id=str(uuid4()))
            second = installer.apply_plan(plan, host, operation_id=str(uuid4()))
        self.assertEqual(first["registry"], "V3")
        self.assertEqual(second["created"], ())
        self.assertEqual(host.reloads, 1)
        self.assertEqual(installer.inspect_host(plan, host)["blocking_conflicts"], ())

    def test_conflicting_uid_gid_fails_closed(self):
        plan = self.plan()
        host = MemoryHost(plan)
        host.groups["bonup-agentctl"] = installer.Group("bonup-agentctl", 3999)
        self.assertIn("group:bonup-agentctl", installer.inspect_host(plan, host)["blocking_conflicts"])
        with self.assertRaises(installer.InstallerBlocked): installer.apply_plan(plan, host)
        host = MemoryHost(plan)
        host.accounts["unrelated"] = installer.Account("unrelated", 3000, 3000, "/x", "/bin/false")
        host.groups["unrelated-group"] = installer.Group("unrelated-group", 3001)
        report = installer.inspect_host(plan, host)
        self.assertIn("uid:3000", report["blocking_conflicts"])
        self.assertIn("gid:3001", report["blocking_conflicts"])

    def test_insecure_directory_mode_and_wrong_owner_fail_closed(self):
        plan = self.plan()
        host = MemoryHost(plan)
        expected = plan.directories[0]
        host.objects[expected.path] = installer.HostObject(
            "directory", expected.uid, expected.gid, 0o777)
        self.assertIn("path:" + expected.path, installer.inspect_host(plan, host)["blocking_conflicts"])
        host.objects[expected.path] = installer.HostObject(
            "directory", 1234, expected.gid, expected.mode)
        self.assertIn("path:" + expected.path, installer.inspect_host(plan, host)["blocking_conflicts"])

    def test_config_and_transport_identities_match_existing_transport_contract(self):
        config = self.options().event_config()
        parsed = installer.EventDeliveryConfig.parse(config)
        self.assertEqual((parsed.agent_control_uid, parsed.agent_control_gid), (3000, 3000))
        self.assertEqual((parsed.django_uid, parsed.django_gid), (33, 33))
        self.assertEqual(parsed.socket_path, installer.PROJECTION_SOCKET)
        self.assertEqual(parsed.socket_mode, 0o660)
        self.assertEqual(installer._projection_unit(self.options()),
                         installer._projection_unit(self.options()))

    def test_missing_or_invalid_configuration_fails_closed(self):
        with self.assertRaises((installer.InstallerBlocked, ValidationError)):
            installer.RuntimeInstallOptions(33, 33, "www-data", "www-data", "/srv/bonup-web",
                                            "backend.core.settings", 10, 10, 500, 2048)
        with self.assertRaises((installer.InstallerBlocked, ValidationError)):
            installer.RuntimeInstallOptions(33, 33, "www-data", "www-data", "/srv/bonup-web",
                                            "backend.core.settings", 1000, 10, 500, 2048,
                                            socket_mode=0o666)

    def test_apply_failure_does_not_delete_registry_or_created_objects(self):
        plan = self.plan()
        host = MemoryHost(plan)
        calls = []

        def prepare(*args, **kwargs):
            host.registry = "V3"
            calls.append("registry")
            return 3

        original = host.create_file
        def fail_on_unit(file):
            if file.path.endswith(installer.PROJECTION_UNIT):
                raise OSError("synthetic install failure")
            original(file)
        host.create_file = fail_on_unit
        with patch.object(installer, "prepare_registry", side_effect=prepare):
            with self.assertRaises(OSError): installer.apply_plan(plan, host)
        self.assertEqual(calls, ["registry"])
        self.assertEqual(host.registry, "V3")
        self.assertTrue(host.objects)

    def test_rollback_plan_preserves_authoritative_registry_and_history(self):
        plan = self.plan()
        result = {"status": "INSTALLED",
                  "created": (("file", installer.EVENT_CONFIG_PATH),)}
        rollback = installer.rollback_plan(plan, result)
        self.assertEqual(rollback["preserve"], (installer.REGISTRY_PATH, installer.HISTORY_PATH))
        self.assertEqual(rollback["paths"], (installer.EVENT_CONFIG_PATH,))
        with self.assertRaises(installer.InstallerBlocked):
            installer.rollback_plan(plan, {
                "status": "INSTALLED",
                "created": (("file", installer.REGISTRY_PATH),),
            })

    def test_real_registry_prepare_reaches_v3_and_preserves_repeat(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            root = Path(directory)
            state, history = root / "control.sqlite3", root / "history.git"
            with patch("tools.agent_control.registry.external_path", lambda value: Path(value).absolute()), \
                    patch("tools.agent_control.storage.external_path", lambda value: Path(value).absolute()), \
                    patch("tools.agent_control.publication.external_path", lambda value: Path(value).absolute()):
                with Registry.initialize(state, history, operation_id=str(uuid4())) as registry:
                    migrate_v2(registry)
                self.assertEqual(installer.prepare_registry(state, history, operation_id=str(uuid4())), 3)
                before = state.read_bytes()
                self.assertEqual(installer.prepare_registry(state, history, operation_id=str(uuid4())), 3)
                self.assertEqual(state.read_bytes(), before)

    def test_invalid_or_future_registry_state_fails_closed(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            root = Path(directory)
            state, history = root / "control.sqlite3", root / "history.git"
            with patch("tools.agent_control.registry.external_path", lambda value: Path(value).absolute()), \
                    patch("tools.agent_control.storage.external_path", lambda value: Path(value).absolute()), \
                    patch("tools.agent_control.publication.external_path", lambda value: Path(value).absolute()):
                with Registry.initialize(state, history, operation_id=str(uuid4())) as registry:
                    registry.db.execute("UPDATE schema_versions SET version=99 WHERE version=1")
                with self.assertRaises(installer.InstallerBlocked):
                    installer.prepare_registry(state, history, operation_id=str(uuid4()))

    def test_registry_history_binding_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            root = Path(directory)
            state, history = root / "control.sqlite3", root / "history.git"
            other_history = root / "other-history.git"
            patches = [
                patch("tools.agent_control.registry.external_path", lambda value: Path(value).absolute()),
                patch("tools.agent_control.storage.external_path", lambda value: Path(value).absolute()),
                patch("tools.agent_control.publication.external_path", lambda value: Path(value).absolute()),
            ]
            with patches[0], patches[1], patches[2]:
                with Registry.initialize(state, history, operation_id=str(uuid4())):
                    pass
                with self.assertRaises(installer.InstallerBlocked):
                    installer.prepare_registry(state, other_history, operation_id=str(uuid4()))


if __name__ == "__main__":
    unittest.main()
