import base64
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from prod_cycle_fixtures import DeterministicProductFake
from test_founder_root import BOOT, ROOT, sign
from test_prod_cycle import synthetic_task
from fixtures import ARCH
from tools.agent_control.authority import AuthenticatedContext
from tools.agent_control.founder_review_auth import ProductProposalReviewBinding
from tools.agent_control.founder_session import FounderSessions
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_review_adapter import ProductionProductReviewAdapter
from tools.agent_control.records import ProductReviewRecord
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2
from tools.agent_control.serialization import canonical_json, digest, parse_json
from tools.agent_control.types import AuthorityError, Role, ValidationError


class ProductionProductReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="bonup-prod-review-")
        root=Path(self.temp.name)
        self.store=ProposalArtifactStore(root / "proposals")
        self.registry=Registry.initialize(root / "state.sqlite3", root / "history.git",
                                          operation_id=str(uuid4()))
        migrate_v2(self.registry)
        task=self.registry.create_task(
            {"title":"Review task","objective":"Review one product proposal",
             "source_base_commit":"a" * 40}, operation_id=str(uuid4()), context=ARCH)
        self.task_id=task["task_id"]
        self.now=datetime(2026, 9, 15, tzinfo=timezone.utc)
        self.ticks=100.0
        self.peer=PeerIdentity(1000, 1000, 1234)
        self.process=ProcessIdentity(BOOT, 1234, 42)
        self.events=[]
        self.sessions=FounderSessions(
            ROOT, observe=lambda: (self.peer, self.process),
            audit=lambda event, correlation: self.events.append((event, correlation)),
            clock=lambda: self.now, boottime=lambda: self.ticks)
        self.adapter=ProductionProductReviewAdapter(self.store, self.sessions, self.registry)
        self.addCleanup(self.registry.close)
        self.addCleanup(self.temp.cleanup)

    def product(self, number=701):
        task=synthetic_task()
        task["task_id"]=self.task_id
        return DeterministicProductFake({
            "proposal_id": f"00000000-0000-4000-8000-000000000{number:03d}",
        }).propose(task)

    def artifact(self, number=701):
        return self.store.persist(self.product(number), source_checkpoint="a" * 40)

    def binding(self, artifact, decision="ACCEPT", reason="Founder product review."):
        return ProductProposalReviewBinding.from_artifact(
            artifact, decision=decision, reason=reason)

    def signed_session(self, binding):
        challenge=self.sessions.issue_product_review(binding)
        session=self.sessions.submit({
            "challenge_id": digest(challenge),
            "signature": base64.b64encode(sign(canonical_json(challenge).encode())).decode(),
        })
        return session

    def review(self, artifact, *, decision="ACCEPT", reason="Founder product review."):
        binding=self.binding(artifact, decision, reason)
        return self.adapter.review(binding, session=self.signed_session(binding),
                                   operation_id=str(uuid4()))

    def test_authenticated_accept_is_durable_and_knowledge_only(self):
        artifact=self.artifact()
        before=Path(artifact.path).read_bytes()
        review=self.review(artifact)
        self.assertEqual(review["decision"], "ACCEPT")
        self.assertEqual(review["resulting_knowledge_state"], "APPROVED_INTERNAL")
        self.assertEqual(Path(artifact.path).read_bytes(), before)
        self.assertEqual(self.registry.load("ProductReviewRecord", review["review_id"]).to_dict(),
                         review.to_dict())
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 1)
        self.assertEqual(self.registry.verify(check_history=False)["status"], "DEGRADED")

    def test_reject_and_request_changes_never_approve(self):
        reject=self.review(self.artifact(702), decision="REJECT", reason="Reject this direction.")
        changes=self.review(self.artifact(703), decision="REQUEST_CHANGES", reason="Request bounded changes.")
        self.assertEqual(reject["resulting_knowledge_state"], "WORKING")
        self.assertEqual(changes["resulting_knowledge_state"], "WORKING")
        self.assertNotIn("PUBLICATION_ELIGIBLE", canonical_json(reject.to_dict()))
        self.assertNotIn("PUBLICATION_ELIGIBLE", canonical_json(changes.to_dict()))

    def test_authentication_is_not_caller_created_context(self):
        artifact=self.artifact()
        binding=self.binding(artifact)
        with self.assertRaises(AuthorityError):
            self.registry.create_product_review(
                artifact, binding, AuthenticatedContext("FOUNDER", Role.FOUNDER, 1000),
                operation_id=str(uuid4()))
        with self.assertRaises(AuthorityError):
            self.registry.create_product_review(
                artifact, binding, object(), operation_id=str(uuid4()))

    def test_wrong_binding_artifact_and_decision_are_denied_before_session_consumption(self):
        artifact=self.artifact()
        signed=self.binding(artifact)
        session=self.signed_session(signed)
        changed=signed.to_dict();changed["decision"]="REJECT"
        changed=ProductProposalReviewBinding.from_dict(changed)
        with self.assertRaises((AuthorityError, ValidationError)):
            self.adapter.review(changed, session=session, operation_id=str(uuid4()))
        self.assertNotIn(session, self.sessions.sessions)

        other=self.artifact(704)
        other_binding=self.binding(other)
        with self.assertRaises(AuthorityError):
            self.adapter.review(other_binding, session=session, operation_id=str(uuid4()))

    def test_changed_artifact_digest_is_denied(self):
        artifact=self.artifact()
        binding=self.binding(artifact)
        session=self.signed_session(binding)
        value=deepcopy(artifact.value)
        value["proposal_digest"]="b" * 64
        Path(artifact.path).write_text(canonical_json(value) + "\n", encoding="utf-8")
        with self.assertRaises(ValidationError):
            self.adapter.review(binding, session=session, operation_id=str(uuid4()))
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 0)

    def test_expired_replayed_and_wrong_purpose_sessions_are_denied(self):
        artifact=self.artifact()
        binding=self.binding(artifact)
        challenge=self.sessions.issue_product_review(binding)
        self.ticks=161
        with self.assertRaises(AuthorityError):
            self.sessions.submit({
                "challenge_id": digest(challenge),
                "signature": base64.b64encode(sign(canonical_json(challenge).encode())).decode(),
            })

        self.ticks=100
        binding=self.binding(artifact, decision="REJECT", reason="Reject.")
        challenge=self.sessions.issue_product_review(binding)
        session=self.sessions.submit({
            "challenge_id": digest(challenge),
            "signature": base64.b64encode(sign(canonical_json(challenge).encode())).decode(),
        })
        with self.assertRaises(AuthorityError):self.sessions.submit({
            "challenge_id": digest(challenge),
            "signature": base64.b64encode(sign(canonical_json(challenge).encode())).decode(),
        })
        with self.assertRaises(AuthorityError):self.sessions.consume(session, "FOUNDER_INSTALLATION_APPROVAL", binding.to_dict())

    def test_duplicate_review_is_denied_and_no_second_record(self):
        artifact=self.artifact()
        binding=self.binding(artifact)
        self.adapter.review(binding, session=self.signed_session(binding), operation_id=str(uuid4()))
        second_session=self.signed_session(binding)
        with self.assertRaises(AuthorityError):
            self.adapter.review(binding, session=second_session, operation_id=str(uuid4()))
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 1)

    def test_record_validation_and_audit_outbox_binding(self):
        review=self.review(self.artifact())
        body=review.to_dict();body["decision"]="REJECT"
        with self.assertRaises(ValidationError):
            ProductReviewRecord(body, context=AuthenticatedContext("FOUNDER", Role.FOUNDER, 1000))
        audits=[parse_json(row[0]) for row in self.registry.db.execute(
            "SELECT payload FROM audit_events ORDER BY sequence")]
        audit=next(event for event in audits
                    if event["event_type"] == "PROD_PROPOSAL_REVIEW_RECORDED")
        self.assertIn(digest(review.to_dict()), audit["record_digests"])
        outbox=self.registry.db.execute(
            "SELECT record_type,source_digest FROM outbox WHERE record_id=?", (review["review_id"],)).fetchone()
        self.assertEqual(outbox["record_type"], "ProductReviewRecord")
        self.assertEqual(outbox["source_digest"], digest(review.to_dict()))
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM executions").fetchone()[0], 0)
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM approvals").fetchone()[0], 0)
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 1)

    def test_malformed_review_does_not_create_authority(self):
        artifact=self.artifact()
        binding=self.binding(artifact)
        with self.assertRaises(AuthorityError):
            self.registry.create_product_review(artifact, binding, object(), operation_id=str(uuid4()))
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 0)
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM audit_events").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
