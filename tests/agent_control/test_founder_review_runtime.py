import unittest
from uuid import uuid4

from tools.agent_control.founder_review_auth import ProductProposalReviewBinding
from tools.agent_control.founder_review_runtime import (
    FounderReviewBoundary,
    TrustedFounderReviewRuntime,
    product_review_operation_id,
)
from tools.agent_control.records import ProductReviewCompletedEvent
from tools.agent_control.serialization import digest
from tools.agent_control.types import AuthorityError, ValidationError


def binding():
    proposal = {
        "agent_id": "PROD-01",
        "task_id": "ATS-1234",
        "proposal_id": "00000000-0000-4000-8000-000000000001",
        "predecessor_proposal_id": None,
        "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
        "title": "Bounded product direction",
        "problem_user_need": "A bounded product direction needs review.",
        "objective": "Review one bounded product direction.",
        "proposed_requirement": "Review the exact requirement.",
        "acceptance_intent": ["The exact requirement is reviewed."],
        "dependencies": [],
        "assumptions": [],
        "risks_open_questions": [],
        "priority_recommendation": "P2",
        "evidence_references": [],
        "knowledge_state": "WORKING",
    }
    proposal_digest = digest(proposal)
    return ProductProposalReviewBinding.from_dict({
        "binding_version": 1,
        "purpose": "PROD_PROPOSAL_REVIEW",
        "artifact_id": "PROD-01-00000000-0000-4000-8000-000000000001",
        "artifact_digest": "a" * 64,
        "task_id": "ATS-1234",
        "proposal_id": "00000000-0000-4000-8000-000000000001",
        "proposal_digest": proposal_digest,
        "decision": "ACCEPT",
        "reason": "Approve the exact validated proposal.",
    })


def projection(subject):
    return {
        "artifact_id": subject.to_dict()["artifact_id"],
        "artifact_digest": subject.to_dict()["artifact_digest"],
        "task_id": subject.to_dict()["task_id"],
        "agent_id": "PROD-01",
        "proposal_id": subject.to_dict()["proposal_id"],
        "proposal_digest": subject.to_dict()["proposal_digest"],
        "knowledge_state": "WORKING",
        "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
        "predecessor_proposal_id": None,
        "title": "Bounded product direction",
        "problem_user_need": "A bounded product direction needs review.",
        "objective": "Review one bounded product direction.",
        "proposed_requirement": "Review the exact requirement.",
        "acceptance_intent": ["The exact requirement is reviewed."],
        "dependencies": [],
        "assumptions": [],
        "risks_open_questions": [],
        "priority_recommendation": "P2",
        "evidence_references": [],
    }


def event(task_id):
    value = {
        "event_version": 1,
        "event_id": str(uuid4()),
        "event_type": "PRODUCT_REVIEW_COMPLETED",
        "occurred_at": "2026-09-20T00:00:00Z",
        "review_id": str(uuid4()),
        "review_digest": "c" * 64,
        "task_id": task_id,
        "agent_id": "PROD-01",
        "artifact_id": "PROD-01-00000000-0000-4000-8000-000000000001",
        "artifact_digest": "a" * 64,
        "proposal_id": "00000000-0000-4000-8000-000000000001",
        "proposal_digest": "b" * 64,
        "decision": "ACCEPT",
        "prior_knowledge_state": "WORKING",
        "resulting_knowledge_state": "APPROVED_INTERNAL",
        "operation_id": str(uuid4()),
        "correlation_id": "placeholder",
    }
    value["correlation_id"] = value["operation_id"]
    value["event_digest"] = digest(value)
    result = ProductReviewCompletedEvent(value)
    object.__setattr__(result, "_trusted", True)
    return result


class FounderReviewRuntimeTests(unittest.TestCase):
    def test_only_canonical_binding_crosses_application_boundary(self):
        calls = []

        def request(value, proposal_value, *, operation_id):
            calls.append((value, proposal_value, operation_id))
            return {"status": "REQUESTED"}

        runtime = TrustedFounderReviewRuntime(FounderReviewBoundary(
            request_review=request,
            observe_review=lambda task_id: None,
        ))
        subject = binding()
        self.assertEqual(
            runtime.request_review(subject, proposal_projection=projection(subject)),
            {"status": "REQUESTED"},
        )
        self.assertEqual(calls[0][0], subject.to_dict())
        self.assertEqual(calls[0][2], product_review_operation_id(subject))

    def test_event_must_be_registry_trusted_and_exactly_task_bound(self):
        trusted = event("ATS-1234")
        runtime = TrustedFounderReviewRuntime(FounderReviewBoundary(
            request_review=lambda value, proposal_value, operation_id: {"status": "REQUESTED"},
            observe_review=lambda task_id: trusted,
        ))
        self.assertIs(runtime.observe_review(task_id="ATS-1234"), trusted)

        object.__setattr__(trusted, "_trusted", False)
        with self.assertRaises(AuthorityError):
            runtime.observe_review(task_id="ATS-1234")

    def test_boundary_rejects_untrusted_composition(self):
        with self.assertRaises(ValidationError):
            TrustedFounderReviewRuntime(object())


if __name__ == "__main__":
    unittest.main()
