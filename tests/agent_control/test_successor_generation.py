"""Generation-1 to Generation-2 successor contract tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.agent_control import founder_genesis
from tools.agent_control import successor_generation as successor
from tools.agent_control.authority_installation import InstallationBinding, approval_projection
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import AuthorityError, ValidationError


ROOT = Path(__file__).resolve().parents[2]
G1_PATH = ROOT / 'docs/agent-control/review/install-07-v6-current-head/payload/etc/bonup-agent-control/approved-installation.json'


class SuccessorGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g1_raw = G1_PATH.read_bytes()
        cls.g2 = successor.generate(cls.g1_raw)
        cls.g2_raw = successor.bytes_for(cls.g2)

    def test_preserved_g1_produces_genesis_eligible_g2(self):
        identity = successor.genesis_identity(self.g2_raw)
        self.assertEqual(identity['provisioning_generation'], 2)
        self.assertEqual(identity['source_commit'], '4296301466f05ca0b479b1c802b7b1d4b15f1be8')
        self.assertEqual(self.g2['founder_root_policy'], founder_genesis.policy())

    def test_g2_binds_exact_g1_and_runtime(self):
        predecessor = self.g2['predecessor']
        self.assertEqual(predecessor['candidate_manifest_digest'], hashlib.sha256(self.g1_raw).hexdigest())
        self.assertEqual(predecessor['candidate_bundle_digest'], json.loads(self.g1_raw)['bundle_digest'])
        self.assertEqual(self.g2['runtime']['source_commit'], self.g2['source_commit'])
        self.assertEqual(self.g2['runtime']['product_runtime_scope'], json.loads(self.g1_raw)['product_runtime_scope'])
        self.assertEqual(self.g2['runtime']['runtime_modules'], json.loads(self.g1_raw)['runtime_modules'])

    def test_generation_is_deterministic_and_g1_is_unchanged(self):
        before = self.g1_raw
        self.assertEqual(successor.generate(self.g1_raw), self.g2)
        self.assertEqual(successor.bytes_for(self.g2), self.g2_raw)
        self.assertEqual(G1_PATH.read_bytes(), before)

    def test_g1_cannot_be_relabelled_as_g2(self):
        with self.assertRaises((AuthorityError, ValidationError)):
            successor.validate(json.loads(self.g1_raw))

    def test_predecessor_substitution_is_rejected(self):
        changed = deepcopy(self.g2)
        changed['predecessor']['candidate_manifest_digest'] = 'a' * 64
        changed['bundle_digest'] = digest({k: v for k, v in changed.items() if k != 'bundle_digest'})
        with self.assertRaises((AuthorityError, ValidationError)):
            successor.validate_for_predecessor(changed, self.g1_raw)

    def test_runtime_substitution_is_rejected(self):
        changed = deepcopy(self.g2)
        changed['runtime']['source_commit'] = 'b' * 40
        changed['bundle_digest'] = digest({k: v for k, v in changed.items() if k != 'bundle_digest'})
        with self.assertRaises((AuthorityError, ValidationError)):
            successor.validate(changed)

    def test_missing_policy_or_unsupported_algorithm_is_rejected(self):
        for mutation in ('missing', 'algorithm'):
            changed = deepcopy(self.g2)
            if mutation == 'missing':
                del changed['founder_root_policy']
            else:
                changed['founder_root_policy']['algorithm'] = 'RSA'
            changed['bundle_digest'] = digest({k: v for k, v in changed.items() if k != 'bundle_digest'})
            with self.subTest(mutation=mutation), self.assertRaises((AuthorityError, ValidationError)):
                successor.validate(changed)

    def test_g2_has_no_approval_or_authority_and_projection_retains_predecessor(self):
        self.assertFalse(self.g2['approved'])
        self.assertFalse(self.g2['activation'])
        self.assertFalse(self.g2['integration_services_approved'])
        approved = deepcopy(self.g2)
        approved['approved'] = True
        approved['founder_root_binding_digest'] = 'f' * 64
        approved['bundle_digest'] = digest({k: v for k, v in approved.items() if k != 'bundle_digest'})
        binding = InstallationBinding(
            self.g2['source_commit'], hashlib.sha256(self.g2_raw).hexdigest(),
            self.g2['bundle_digest'], hashlib.sha256(canonical_json(approved).encode()).hexdigest(),
            'e' * 64, 2, 'f' * 64,
            self.g2['predecessor']['candidate_manifest_digest'])
        self.assertEqual(
            approval_projection(self.g2_raw, canonical_json(approved).encode(), binding),
            hashlib.sha256(canonical_json(approved).encode()).hexdigest())

    def test_generation2_installation_binding_requires_predecessor(self):
        with self.assertRaises(ValidationError):
            InstallationBinding('a' * 40, 'b' * 64, 'c' * 64, 'd' * 64,
                                'e' * 64, 2)


if __name__ == '__main__':
    unittest.main()
