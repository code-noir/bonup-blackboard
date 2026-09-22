"""v5 binds the complete trusted Django projection installation scope."""
from copy import deepcopy
from pathlib import Path
import unittest

from tools.agent_control import installation_approval as approval
from tools.agent_control import installation_bundle as bundle
from tools.agent_control import privileged_installer as installer
from tools.agent_control.types import AuthorityError, ValidationError


class InstallationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[2]
        old, cls.payloads = bundle.build(cls.repo, source_commit=bundle.SOURCE_COMMIT)
        cls.scope = bundle.projection_scope()
        cls.manifest = bundle.candidate(
            old['artifacts'], old['source_commit'], old['runtime_modules'], cls.scope)

    def setUp(self):
        self.m = deepcopy(self.manifest)

    def options(self):
        return installer.RuntimeInstallOptions(
            33, 33, 'www-data', 'www-data', '/srv/bonup-web',
            'backend.core.settings', 1000, 10, 500, 2048)

    def approved(self):
        self.m['approved'] = True
        bundle.seal(self.m)
        return self.m

    def test_v5_scope_is_complete_and_unapproved(self):
        self.assertEqual(bundle.validate_manifest(self.m), 'COMPLETE_BUT_UNAPPROVED')
        scope = self.m['projection_scope']
        self.assertEqual(scope['registry']['path'], '/var/lib/bonup-agent-control/control.sqlite3')
        self.assertEqual(scope['registry']['history_path'], '/var/lib/bonup-agent-control/history.git')
        self.assertEqual(scope['registry']['target_schema_version'], 3)
        self.assertEqual(scope['registry']['accepted_existing_versions'], [1, 2, 3])
        self.assertEqual(scope['event_config_path'], bundle.EVENT_CONFIG_PATH)
        self.assertEqual(scope['event_config_file']['mode'], '0440')
        self.assertEqual(scope['event_config_sha256'],
                         bundle.sha(bundle.json_bytes(scope['event_config'])))
        self.assertEqual(scope['socket']['mode'], '0660')
        self.assertEqual(scope['service']['path'], '/etc/systemd/system/' + bundle.PROJECTION_UNIT)
        self.assertFalse(self.m['approved'])

    def test_scope_changes_change_digest_and_invalid_scope_fails_closed(self):
        original = self.m['bundle_digest']
        self.m['projection_scope']['event_config']['django']['uid'] = 34
        bundle.seal(self.m)
        self.assertNotEqual(self.m['bundle_digest'], original)
        with self.assertRaises(ValidationError):
            bundle.validate_manifest(self.m)

    def test_socket_mode_and_service_change_are_bound(self):
        for path, value in (
                (('projection_scope', 'registry', 'path'), '/var/lib/other/control.sqlite3'),
                (('projection_scope', 'registry', 'history_path'), '/var/lib/other/history.git'),
                (('projection_scope', 'registry', 'target_schema_version'), 2),
                (('projection_scope', 'socket', 'mode'), '0600'),
                (('projection_scope', 'event_config_file', 'mode'), '0644'),
                (('projection_scope', 'service', 'root'), '/srv/other')):
            changed = deepcopy(self.manifest)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            bundle.seal(changed)
            self.assertNotEqual(changed['bundle_digest'], self.manifest['bundle_digest'])
            with self.assertRaises(ValidationError):
                bundle.validate_manifest(changed)

    def test_unknown_scope_field_rejected(self):
        self.m['projection_scope']['unexpected'] = True
        bundle.seal(self.m)
        with self.assertRaises(ValidationError):
            bundle.validate_manifest(self.m)

    def test_installer_consumes_approved_scope(self):
        plan = installer.build_plan(self.approved(), self.payloads, self.options())
        self.assertEqual(plan.registry_path, bundle.REGISTRY_PATH)
        self.assertEqual(plan.history_path, bundle.HISTORY_PATH)
        self.assertEqual(plan.projection_socket, bundle.PROJECTION_SOCKET)
        self.assertEqual(plan.activation, 'INSTALL_ONLY_NO_SERVICE_ACTIVATION')

    def test_installer_options_cannot_override_scope(self):
        self.approved()
        changed = installer.RuntimeInstallOptions(
            34, 34, 'other', 'other', '/srv/bonup-web',
            'backend.core.settings', 1000, 10, 500, 2048)
        with self.assertRaises(installer.InstallerBlocked):
            installer.build_plan(self.m, self.payloads, changed)
        with self.assertRaises(ValidationError):
            installer.RuntimeInstallOptions(
                33, 33, 'www-data', 'www-data', '/srv/bonup-web',
                'backend.core.settings', 1000, 10, 500, 2048, socket_mode=0o600)
        changed = installer.RuntimeInstallOptions(
            33, 33, 'www-data', 'www-data', '/srv/bonup-web',
            'backend.core.settings', 2000, 10, 500, 2048)
        with self.assertRaises(installer.InstallerBlocked):
            installer.build_plan(self.m, self.payloads, changed)

    def test_unapproved_v5_bundle_cannot_install(self):
        with self.assertRaises(AuthorityError):
            installer.build_plan(self.m, self.payloads, self.options())

    def test_current_candidate_requires_explicit_approval_identity(self):
        raw = bundle.json_bytes(self.m)
        expected = {
            'source_commit': self.m['source_commit'],
            'candidate_manifest_digest': bundle.sha(raw),
            'candidate_bundle_digest': self.m['bundle_digest'],
        }
        self.assertEqual(approval.candidate(raw, expected=expected), self.m)
        with self.assertRaises(ValidationError):
            approval.candidate(raw)

    def test_v4_remains_valid_without_projection_scope(self):
        old, payloads = bundle.build(self.repo, source_commit=bundle.SOURCE_COMMIT)
        self.assertEqual(old['version'], 4)
        self.assertNotIn('projection_scope', old)
        self.assertEqual(bundle.validate_manifest(old), 'COMPLETE_BUT_UNAPPROVED')
        bundle.verify_payloads(old, payloads)

    def test_product_runtime_scope_binds_service_config_socket_and_artifacts(self):
        source = "a" * 40
        scope = bundle.product_runtime_scope(source)
        self.assertEqual(bundle.validate_product_runtime_scope(scope, source_commit=source), scope)
        self.assertEqual(scope["config"]["socket_path"], "/run/bonup-agent-control/prod01.sock")
        self.assertEqual(scope["config"]["model_policy"]["max_retries"], 0)
        self.assertEqual(scope["artifact_store"]["path"], "/var/lib/bonup-prod/proposals")
        changed = deepcopy(scope)
        changed["socket"]["mode"] = "0600"
        with self.assertRaises(ValidationError):
            bundle.validate_product_runtime_scope(changed, source_commit=source)


class ProductRuntimeScopeTests(unittest.TestCase):
    SOURCE = "a" * 40

    def setUp(self):
        self.scope = bundle.product_runtime_scope(self.SOURCE)

    def test_controller_writable_paths_are_exactly_the_existing_state_and_proposal_paths(self):
        unit = bundle.product_controller_unit().decode()
        writable = next(
            line.split("=", 1)[1].split()
            for line in unit.splitlines()
            if line.startswith("ReadWritePaths=")
        )
        self.assertEqual(
            set(writable),
            {
                "/var/lib/bonup-agent-control",
                "/run/bonup-agent-control",
                bundle.PRODUCT_ARTIFACT_DIRECTORY,
            },
        )
        self.assertIn(bundle.PRODUCT_ARTIFACT_DIRECTORY, writable)
        self.assertNotIn(bundle.PRODUCT_ARTIFACT_PARENT, writable)

    def test_parent_is_root_traversable_and_proposals_are_controller_writable(self):
        store = self.scope["artifact_store"]
        self.assertEqual(
            (store["parent_owner_uid"], store["parent_group_gid"],
             int(store["parent_mode"], 8)),
            (0, 0, 0o711),
        )
        self.assertEqual(
            (store["owner_uid"], store["group_gid"], int(store["mode"], 8)),
            (3000, 3000, 0o700),
        )
        self.assertNotEqual(store["parent_owner_uid"], store["owner_uid"])
        self.assertFalse(int(store["parent_mode"], 8) & 0o022)

    def test_installer_directory_specs_preserve_parent_and_proposal_authority(self):
        options = installer.RuntimeInstallOptions(
            33, 33, "www-data", "www-data", "/srv/bonup-web",
            "backend.core.settings", 1000, 10, 500, 2048,
        )
        rows = {
            row.path: (row.uid, row.gid, row.mode)
            for row in installer._directory_specs(options, self.scope)
        }
        self.assertEqual(rows[bundle.PRODUCT_ARTIFACT_PARENT], (0, 0, 0o711))
        self.assertEqual(rows[bundle.PRODUCT_ARTIFACT_DIRECTORY], (3000, 3000, 0o700))

    def test_v6_scope_digest_and_closed_authority_are_bound(self):
        scope_digest = bundle.sha(bundle.json_bytes(self.scope))
        changed = deepcopy(self.scope)
        changed["artifact_store"]["parent_mode"] = "0700"
        self.assertNotEqual(scope_digest, bundle.sha(bundle.json_bytes(changed)))
        with self.assertRaises(ValidationError):
            bundle.validate_product_runtime_scope(changed, source_commit=self.SOURCE)

        manifest = bundle.candidate([], self.SOURCE, product_scope=self.scope)
        self.assertFalse(manifest["approved"])
        self.assertFalse(manifest["activation"])
        self.assertFalse(manifest["integration_services_approved"])
        self.assertFalse(self.scope["runtime_owner"]["execution_authority"])
        self.assertNotIn("ExecutionGrant", bundle.canonical_json(self.scope))
        self.assertNotIn("ARCH_ROUTING", bundle.canonical_json(self.scope))


if __name__ == '__main__':
    unittest.main()
