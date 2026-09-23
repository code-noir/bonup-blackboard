import base64
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

try:
    from test_founder_root import BOOT, ROOT, sign
    FOUNDER_FIXTURE_AVAILABLE = True
except Exception:
    BOOT, ROOT, sign = None, None, None
    FOUNDER_FIXTURE_AVAILABLE = False
from tools.agent_control.authority_installation import InstallationBinding
from tools.agent_control.founder_intake import FounderIntake, FounderPolicy
from tools.agent_control.founder_review_auth import ProductProposalReviewBinding
from tools.agent_control.founder_review_composition import FounderReviewCoordinator
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.prod_application import ProductDirectionApplicationService
from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_execution import ProdExecutionLedger
from tools.agent_control.prod_runtime import TrustedProd01Runtime
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2
from tools.agent_control.serialization import canonical_json, digest


@unittest.skipUnless(FOUNDER_FIXTURE_AVAILABLE, "trusted Founder fixture unavailable in this environment")
class FounderReviewCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bonup-founder-review-", dir="/dev/shm")
        root = Path(self.temp.name)
        self.store = ProposalArtifactStore(root / "proposals")
        self.registry = Registry.initialize(
            root / "state.sqlite3", root / "history.git", operation_id=str(uuid4())
        )
        migrate_v2(self.registry)
        self.addCleanup(self.registry.close)
        self.addCleanup(self.temp.cleanup)

        proposal = {
            "agent_id": "PROD-01",
            "task_id": "ATS-7001",
            "proposal_id": "00000000-0000-4000-8000-000000000701",
            "predecessor_proposal_id": None,
            "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
            "title": "Founder-facing product direction",
            "problem_user_need": "The Founder must review one exact proposal.",
            "objective": "Verify the trusted review presentation.",
            "proposed_requirement": "Present the immutable proposal before authorization.",
            "acceptance_intent": ["The displayed digest equals the signed binding."],
            "dependencies": [],
            "assumptions": ["The Founder transport is external."],
            "risks_open_questions": ["Provisioning remains separate."],
            "priority_recommendation": "P2",
            "evidence_references": [],
            "knowledge_state": "WORKING",
        }
        self.artifact = self.store.persist(proposal, source_checkpoint="a" * 40)
        self.binding = ProductProposalReviewBinding.from_artifact(
            self.artifact,
            decision="ACCEPT",
            reason="Approve the exact Founder-facing proposal.",
        )
        self.coordinator = FounderReviewCoordinator(self.store, self.registry)

    def intake(self):
        installation_binding = InstallationBinding(
            "a" * 40, "b" * 64, "c" * 64, "d" * 64, "e" * 64, 2,
            predecessor_candidate_manifest_digest="b" * 64
        )
        policy = FounderPolicy(True, installation_binding, ROOT.identity, "f" * 64)
        return FounderIntake(
            policy,
            ROOT,
            lambda: (PeerIdentity(1000, 1000, 1234), ProcessIdentity(BOOT, 1234, 42)),
            lambda *args: None,
            controller=object(),
            runner=None,
            runtime_context=lambda: {"boot_id": BOOT},
            receipt_reader=lambda: b"{}",
            candidate_reader=lambda: (b"", b""),
            product_review_artifact_store=self.store,
            product_review_registry=self.registry,
            product_review_gate=self.coordinator,
            clock=lambda: datetime(2026, 9, 22, tzinfo=timezone.utc),
            boottime=lambda: 100.0,
        )

    def test_application_request_founder_display_and_authorized_review_are_one_binding(self):
        class NoCallModel:
            credential_owned = True

            def send(self, **kwargs):
                raise AssertionError("The review composition must not invoke the model.")

        service = ProductDirectionApplicationService(
            TrustedProd01Runtime(
                NoCallModel(), source_checkpoint="a" * 40, artifact_store=self.store,
                execution_ledger=ProdExecutionLedger(Path(self.temp.name) / "execution.sqlite3"),
            ),
            artifact_store=self.store,
            founder_boundary=self.coordinator.boundary(),
        )
        requested = service.handle(
            "REQUEST_FOUNDER_REVIEW", {"binding": self.binding.to_dict()}
        )
        self.assertEqual(requested["status"], "REQUESTED")

        intake = self.intake()
        packet = intake.request({
            "version": 1,
            "request_id": str(uuid4()),
            "action": "REQUEST_PROD_PROPOSAL_REVIEW_CHALLENGE",
            "arguments": {"binding": self.binding.to_dict()},
        })["result"]
        display = packet["review"]
        challenge = packet["challenge"]
        self.assertEqual(display["proposal_digest"], self.binding.to_dict()["proposal_digest"])
        self.assertEqual(display["requested_decision"], "ACCEPT")
        self.assertEqual(display["resulting_knowledge_state"], "APPROVED_INTERNAL")
        self.assertNotIn("title", challenge)
        self.assertNotIn(display["title"], canonical_json(challenge))

        signature = base64.b64encode(sign(canonical_json(challenge).encode())).decode()
        result = intake.request({
            "version": 1,
            "request_id": str(uuid4()),
            "action": "SUBMIT_FOUNDER_SIGNATURE",
            "arguments": {"challenge_id": digest(challenge), "signature": signature},
        })["result"]["review"]
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertEqual(result["resulting_knowledge_state"], "APPROVED_INTERNAL")
        self.assertEqual(
            self.registry.db.execute("SELECT COUNT(*) FROM product_reviews").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.registry.db.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.coordinator.observe_product_review("ATS-7001")["proposal_digest"],
            self.binding.to_dict()["proposal_digest"],
        )

        with self.assertRaises(Exception):
            intake.request({
                "version": 1,
                "request_id": str(uuid4()),
                "action": "SUBMIT_FOUNDER_SIGNATURE",
                "arguments": {"challenge_id": digest(challenge), "signature": signature},
            })
        self.assertEqual(
            self.registry.db.execute("SELECT COUNT(*) FROM product_reviews").fetchone()[0],
            1,
        )

    def test_changed_decision_or_artifact_is_rejected_before_founder_challenge(self):
        class NoCallModel:
            credential_owned = True

        service = ProductDirectionApplicationService(
            TrustedProd01Runtime(
                NoCallModel(), source_checkpoint="a" * 40, artifact_store=self.store,
                execution_ledger=ProdExecutionLedger(Path(self.temp.name) / "execution.sqlite3"),
            ),
            artifact_store=self.store,
            founder_boundary=self.coordinator.boundary(),
        )
        changed = self.binding.to_dict()
        changed["decision"] = "REJECT"
        changed_binding = ProductProposalReviewBinding.from_dict(changed)
        with self.assertRaises(Exception):
            service.handle("REQUEST_FOUNDER_REVIEW", {"binding": changed_binding.to_dict()})
        self.assertEqual(self.coordinator._pending, {})


if __name__ == "__main__":
    unittest.main()
