from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.records import ProductReviewCompletedEvent
from tools.agent_control.serialization import digest
from tools.agent_control.types import ValidationError

from backend.bonup.models import AgentControlEventInbox, ApprovedProductDirection
from backend.api.blackboard.events import consume_product_review_completed
from backend.api.tests.test_product_direction import make_verified_user


def proposal(task_id, proposal_id):
    return {
        "agent_id": "PROD-01",
        "task_id": task_id,
        "proposal_id": proposal_id,
        "predecessor_proposal_id": None,
        "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
        "title": "Product direction result",
        "problem_user_need": "The product needs one approved direction.",
        "objective": "Project Product Direction into Blackboard.",
        "proposed_requirement": "Blackboard should display the validated product knowledge.",
        "acceptance_intent": ["The direction is visible."],
        "dependencies": [],
        "assumptions": [],
        "risks_open_questions": [],
        "priority_recommendation": "P2",
        "evidence_references": [],
        "knowledge_state": "WORKING",
    }


def trusted_event(artifact, *, decision="ACCEPT", event_id=None, review_id=None,
                  artifact_digest=None):
    value = artifact.value
    result_state = "APPROVED_INTERNAL" if decision == "ACCEPT" else "WORKING"
    operation_id = str(uuid4())
    event = {
        "event_version": 1,
        "event_id": str(event_id or uuid4()),
        "event_type": "PRODUCT_REVIEW_COMPLETED",
        "occurred_at": "2026-09-20T00:00:00Z",
        "review_id": str(review_id or uuid4()),
        "review_digest": "c" * 64,
        "task_id": value["task_id"],
        "agent_id": value["agent_id"],
        "artifact_id": value["artifact_id"],
        "artifact_digest": artifact_digest or value["artifact_digest"],
        "proposal_id": value["proposal_id"],
        "proposal_digest": value["proposal_digest"],
        "decision": decision,
        "prior_knowledge_state": "WORKING",
        "resulting_knowledge_state": result_state,
        "operation_id": operation_id,
        "correlation_id": operation_id,
    }
    event["event_digest"] = digest(event)
    result = ProductReviewCompletedEvent(event)
    object.__setattr__(result, "_trusted", True)
    return result


class BlackboardProductDirectionProjectionTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="bonup-blackboard-projection-", dir="/tmp")
        self.store = ProposalArtifactStore(self.directory.name)
        self.artifact = self.store.persist(
            proposal("ATS-1234", str(uuid4())),
            source_checkpoint="a" * 40,
        )
        self.addCleanup(self.directory.cleanup)

    def test_accept_projects_approved_internal_provenance_without_product_direction(self):
        event = trusted_event(self.artifact)
        result = consume_product_review_completed(event, artifact_store=self.store)

        self.assertEqual(result["status"], "APPLIED")
        row = ApprovedProductDirection.objects.get(event_id=event["event_id"])
        self.assertEqual(row.resulting_knowledge_state, "APPROVED_INTERNAL")
        self.assertEqual(row.agent_control_task_id, event["task_id"])
        self.assertEqual(str(row.proposal_id), event["proposal_id"])
        self.assertEqual(row.proposal_digest, event["proposal_digest"])
        self.assertEqual(row.artifact_id, event["artifact_id"])
        self.assertEqual(row.artifact_digest, event["artifact_digest"])
        self.assertEqual(str(row.review_id), event["review_id"])
        self.assertEqual(row.review_digest, event["review_digest"])
        self.assertEqual(str(row.event_id), event["event_id"])
        self.assertEqual(row.event_digest, event["event_digest"])

    def test_reject_and_request_changes_are_acknowledged_but_not_projected(self):
        for decision in ("REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                result = consume_product_review_completed(
                    trusted_event(self.artifact, decision=decision),
                    artifact_store=self.store,
                )
                self.assertEqual(result["status"], "NOT_APPROVED")
        self.assertEqual(ApprovedProductDirection.objects.count(), 0)

    def test_duplicate_delivery_is_a_no_op(self):
        event = trusted_event(self.artifact)
        self.assertEqual(
            consume_product_review_completed(event, artifact_store=self.store)["status"],
            "APPLIED",
        )
        self.assertEqual(
            consume_product_review_completed(event, artifact_store=self.store)["status"],
            "DUPLICATE",
        )
        self.assertEqual(ApprovedProductDirection.objects.count(), 1)
        self.assertEqual(
            AgentControlEventInbox.objects.filter(
                consumer_name="blackboard-product-direction"
            ).count(),
            1,
        )

    def test_replay_rebuilds_projection_without_founder_or_product_direction(self):
        event = trusted_event(self.artifact)
        consume_product_review_completed(event, artifact_store=self.store)
        ApprovedProductDirection.objects.get(event_id=event["event_id"]).delete()
        with patch("tools.agent_control.founder_intake.FounderIntake", side_effect=AssertionError), \
                patch("tools.agent_control.founder_session.FounderSessions", side_effect=AssertionError), \
                patch("tools.agent_control.registry.Registry.create_product_review", side_effect=AssertionError):
            result = consume_product_review_completed(event, artifact_store=self.store)
        self.assertEqual(result["status"], "REBUILT")
        self.assertEqual(ApprovedProductDirection.objects.count(), 1)

    def test_mismatched_artifact_provenance_is_rejected_before_acknowledgement(self):
        event = trusted_event(self.artifact, artifact_digest="d" * 64)
        with self.assertRaisesRegex(ValueError, "EVENT_PROVENANCE_MISMATCH"):
            consume_product_review_completed(event, artifact_store=self.store)
        self.assertEqual(AgentControlEventInbox.objects.count(), 0)

    def test_inbox_digest_conflict_is_rejected(self):
        event = trusted_event(self.artifact)
        consume_product_review_completed(event, artifact_store=self.store)
        changed = deepcopy(event.to_dict())
        changed["review_digest"] = "d" * 64
        changed["event_digest"] = digest({
            key: value for key, value in changed.items() if key != "event_digest"
        })
        conflicting = ProductReviewCompletedEvent(changed)
        object.__setattr__(conflicting, "_trusted", True)
        with self.assertRaisesRegex(ValueError, "EVENT_INBOX_MISMATCH"):
            consume_product_review_completed(conflicting, artifact_store=self.store)

    def test_unsupported_event_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EVENT_INVALID"):
            consume_product_review_completed({"event_version": 2}, artifact_store=self.store)

    def test_projection_does_not_require_product_direction_task(self):
        event = trusted_event(self.artifact)
        with patch("backend.api.product_direction.events.consume_product_review_completed",
                   side_effect=AssertionError):
            consume_product_review_completed(event, artifact_store=self.store)
        self.assertEqual(ApprovedProductDirection.objects.count(), 1)

    def test_read_api_exposes_only_bounded_projection(self):
        event = trusted_event(self.artifact)
        consume_product_review_completed(event, artifact_store=self.store)
        user = make_verified_user("blackboard-reader", "blackboard-reader@example.com")
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/blackboard/product-direction/approved/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertNotIn("signature", response.data["results"][0])
        self.assertNotIn("session", response.data["results"][0])
        self.assertNotIn("challenge", response.data["results"][0])


if __name__ == "__main__":
    import unittest
    unittest.main()
