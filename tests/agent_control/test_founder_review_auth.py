import base64
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from prod_cycle_fixtures import DeterministicProductFake
from test_founder_root import BOOT, ROOT, sign
from test_prod_cycle import synthetic_task
from tools.agent_control.founder_crypto import FounderRoot, PROD_PROPOSAL_REVIEW, PURPOSES
from tools.agent_control.founder_review_auth import (
    ProductProposalReviewBinding, REVIEW_BINDING_VERSION, REVIEW_DECISIONS,
)
from tools.agent_control.founder_session import FounderSessions
from tools.agent_control.authority import AuthenticatedContext
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_review import SyntheticFounderReviewContext, create_product_review
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import AuthorityError, Role, ValidationError


class ProductProposalReviewAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ProposalArtifactStore(Path(self.temp.name) / "proposals")
        proposal = DeterministicProductFake().propose(synthetic_task())
        self.artifact = self.store.persist(proposal, source_checkpoint="a" * 40)
        other = DeterministicProductFake({
            "proposal_id": "00000000-0000-4000-8000-000000000702",
        }).propose(synthetic_task())
        self.other_artifact = self.store.persist(other, source_checkpoint="a" * 40)
        self.peer = PeerIdentity(1000, 1000, 1234)
        self.process = ProcessIdentity(BOOT, 1234, 42)
        self.now = datetime(2026, 9, 15, tzinfo=timezone.utc)
        self.ticks = 100.0
        self.events = []
        self.engine = FounderSessions(
            ROOT,
            observe=lambda: (self.peer, self.process),
            audit=lambda event, correlation: self.events.append((event, correlation)),
            clock=lambda: self.now,
            boottime=lambda: self.ticks,
        )

    def binding(self, artifact=None, decision="ACCEPT", reason="Founder product review."):
        return ProductProposalReviewBinding.from_artifact(
            artifact or self.artifact, decision=decision, reason=reason)

    def issue(self, binding=None):
        binding = binding or self.binding()
        challenge = self.engine.issue_product_review(binding)
        return binding, challenge

    def submit(self, challenge):
        return self.engine.submit(dict(
            challenge_id=digest(challenge),
            signature=base64.b64encode(sign(canonical_json(challenge).encode())).decode(),
        ))

    def test_exact_accept_binding_is_deterministic_and_consumed_once(self):
        first = self.binding()
        second = self.binding()
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first.binding_digest, second.binding_digest)
        self.assertEqual(first.to_dict()["binding_version"], REVIEW_BINDING_VERSION)
        self.assertEqual(first.to_dict()["purpose"], PROD_PROPOSAL_REVIEW)
        self.assertEqual(first.to_dict()["decision"], "ACCEPT")
        binding, challenge = self.issue(first)
        session = self.submit(challenge)
        accepted_challenge, proof = self.engine.consume_product_review(session, binding)
        self.assertEqual(accepted_challenge["binding"], binding.to_dict())
        self.assertEqual(accepted_challenge["purpose"], PROD_PROPOSAL_REVIEW)
        self.assertTrue(len(proof) == 64)
        with self.assertRaises(AuthorityError):
            self.engine.consume_product_review(session, binding)
        self.assertEqual(self.events.count(("FOUNDER_SESSION_CREATED", digest(challenge))), 1)

    def test_all_decisions_are_closed_and_signed_subjects(self):
        self.assertEqual(REVIEW_DECISIONS, ("ACCEPT", "REJECT", "REQUEST_CHANGES"))
        bindings = [self.binding(decision=decision, reason="Decision: " + decision)
                    for decision in REVIEW_DECISIONS]
        self.assertEqual(len({item.binding_digest for item in bindings}), 3)

    def test_decision_artifact_digest_task_proposal_and_reason_substitution_rejected(self):
        substitutions = {
            "decision": "REJECT",
            "artifact_digest": "b" * 64,
            "task_id": "ATS-9999",
            "proposal_id": "00000000-0000-4000-8000-000000000799",
            "proposal_digest": "c" * 64,
            "reason": "A different signed reason.",
        }
        for field, replacement in substitutions.items():
            with self.subTest(field=field):
                binding, challenge = self.issue()
                session = self.submit(challenge)
                altered = binding.to_dict()
                altered[field] = replacement
                with self.assertRaises((AuthorityError, ValidationError)):
                    self.engine.consume_product_review(session, altered)

    def test_artifact_substitution_rejected(self):
        binding, challenge = self.issue()
        session = self.submit(challenge)
        other = self.binding(self.other_artifact)
        with self.assertRaises(AuthorityError):
            self.engine.consume_product_review(session, other)

    def test_wrong_purpose_and_unknown_purpose_rejected(self):
        binding, challenge = self.issue()
        session = self.submit(challenge)
        with self.assertRaises(AuthorityError):
            self.engine.consume(session, PURPOSES[0], binding.to_dict())
        with self.assertRaises(AuthorityError):
            self.engine.issue_binding("FOUNDER_ACTIVATION_APPROVAL", binding.to_dict())

    def test_expiry_replay_peer_process_boot_and_root_binding_rejected(self):
        binding, challenge = self.issue()
        self.ticks += 61
        with self.assertRaises(AuthorityError):
            self.submit(challenge)

        binding, challenge = self.issue()
        session = self.submit(challenge)
        with self.assertRaises(AuthorityError):
            self.submit(challenge)
        self.engine.revoke_all()
        with self.assertRaises(AuthorityError):
            self.engine.consume_product_review(session, binding)

        for changed_peer, changed_process in (
                (PeerIdentity(1000, 1000, 99), ProcessIdentity(BOOT, 99, 42)),
                (self.peer, ProcessIdentity(BOOT, 1234, 43)),
                (self.peer, ProcessIdentity(str(uuid4()), 1234, 42))):
            self.engine = FounderSessions(
                ROOT, observe=lambda: (self.peer, self.process), audit=lambda *args: None,
                clock=lambda: self.now, boottime=lambda: self.ticks)
            binding, challenge = self.issue()
            self.peer, self.process = changed_peer, changed_process
            with self.assertRaises(AuthorityError):
                self.submit(challenge)
            self.peer, self.process = PeerIdentity(1000, 1000, 1234), ProcessIdentity(BOOT, 1234, 42)

        self.engine = FounderSessions(
            ROOT, observe=lambda: (self.peer, self.process), audit=lambda *args: None,
            clock=lambda: self.now, boottime=lambda: self.ticks)
        binding, challenge = self.issue()
        self.engine.root = FounderRoot("different-root", ROOT.public_key, ROOT.generation)
        with self.assertRaises(AuthorityError):
            self.submit(challenge)

    def test_binding_is_closed_and_artifact_must_be_loader_shaped(self):
        value = self.binding().to_dict()
        value["unexpected"] = True
        with self.assertRaises(ValidationError):
            ProductProposalReviewBinding.from_dict(value)
        with self.assertRaises(AuthorityError):
            ProductProposalReviewBinding.from_artifact({"value": {}} , decision="ACCEPT", reason="x")

    def test_synthetic_context_is_not_production_review_authentication(self):
        with self.assertRaises(ValidationError):
            create_product_review(
                self.artifact.value["proposal"], AuthenticatedContext("FOUNDER", Role.FOUNDER, 1000),
                decision="ACCEPT", decision_id="00000000-0000-4000-8000-000000000801",
                reason="Direct context is not a production review session.")
        self.assertEqual(SyntheticFounderReviewContext().context_kind, "SYNTHETIC_TEST_ONLY")
        self.assertEqual(self.artifact.value["knowledge_state"], "WORKING")
        self.assertFalse(any("APPROVED_INTERNAL" in str(event) for event in self.events))


if __name__ == "__main__":
    unittest.main()
