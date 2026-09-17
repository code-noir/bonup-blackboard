import unittest
from copy import deepcopy

from prod_cycle_fixtures import DeterministicProductFake
from test_prod_cycle import synthetic_task
from tools.agent_control.prod_contract import validate_product_proposal
from tools.agent_control.prod_cycle import run_synthetic_product_cycle
from tools.agent_control.prod_review import (
    ProductReviewRecord, SyntheticFounderReviewContext, assert_review_binding, create_product_review,
    review_synthetic_cycle, validate_requested_revision,
)
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import ValidationError

ACCEPT_ID = "00000000-0000-4000-8000-000000000801"


def cycle(changes=None):
    return run_synthetic_product_cycle(synthetic_task(), DeterministicProductFake(changes))


def review(proposal, decision="ACCEPT", decision_id=ACCEPT_ID):
    return create_product_review(proposal, SyntheticFounderReviewContext(), decision=decision,
                                 decision_id=decision_id, reason="Synthetic Founder review decision.")


class ProductReviewTests(unittest.TestCase):
    def test_accept_binds_exact_proposal_and_approves_internal_knowledge_only(self):
        result = cycle(); before = result.proposal_bytes
        record = review(result.proposal)
        self.assertEqual(assert_review_binding(record, result.proposal), "APPROVED_INTERNAL")
        self.assertEqual(result.proposal_bytes, before)
        self.assertEqual(record["proposal_digest"], result.proposal_digest)
        self.assertEqual(record["reviewer"]["context_kind"], "SYNTHETIC_TEST_ONLY")
        self.assertNotIn("execution", record.to_dict())
        self.assertNotIn("assignment", record.to_dict())

    def test_reject_and_request_changes_do_not_approve_knowledge(self):
        proposal = cycle().proposal
        for decision, key in (("REJECT", "802"), ("REQUEST_CHANGES", "803")):
            record = review(proposal, decision, f"00000000-0000-4000-8000-000000000{key}")
            with self.subTest(decision=decision):
                self.assertEqual(record["resulting_knowledge_state"], "WORKING")

    def test_changed_or_second_proposal_cannot_reuse_review(self):
        first = cycle(); record = review(first.proposal)
        changed = deepcopy(first.proposal)
        changed["title"] = "Changed proposal identity binding"
        validate_product_proposal(changed)
        with self.assertRaises(ValidationError):
            assert_review_binding(record, changed)
        second = cycle({"proposal_id": "00000000-0000-4000-8000-000000000702"})
        with self.assertRaises(ValidationError):
            assert_review_binding(record, second.proposal)

    def test_request_changes_requires_new_identity_digest_and_predecessor(self):
        first = cycle(); requested = review(first.proposal, "REQUEST_CHANGES",
                                             "00000000-0000-4000-8000-000000000803")
        revised = deepcopy(first.proposal)
        revised.update(proposal_id="00000000-0000-4000-8000-000000000704",
                       predecessor_proposal_id=first.proposal["proposal_id"],
                       title="Revised task history proposal")
        self.assertEqual(validate_requested_revision(requested, first.proposal, revised), revised)
        for change in ({"proposal_id": first.proposal["proposal_id"]},
                       {"predecessor_proposal_id": None}):
            bad = deepcopy(revised); bad.update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                validate_requested_revision(requested, first.proposal, bad)

    def test_review_record_is_deterministic_and_rejects_authority_fields(self):
        proposal = cycle().proposal
        first = review(proposal); second = review(proposal)
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first["review_digest"], second["review_digest"])
        mutated = first.to_dict(); mutated["deployment"] = True
        with self.assertRaises(ValidationError):
            assert_review_binding(ProductReviewRecord(canonical_json(mutated)), proposal)

    def test_publication_state_and_non_synthetic_context_are_rejected(self):
        proposal = cycle().proposal
        with self.assertRaises(ValidationError):
            create_product_review(proposal, object(), decision="ACCEPT",
                                  decision_id=ACCEPT_ID, reason="Invalid context")
        accepted = review(proposal).to_dict()
        accepted["resulting_knowledge_state"] = "PUBLICATION_ELIGIBLE"
        with self.assertRaises(ValidationError):
            assert_review_binding(ProductReviewRecord(canonical_json(accepted)), proposal)

    def test_synthetic_cycle_accept_review_updates_document_without_arch_routing(self):
        original = cycle()
        reviewed = review_synthetic_cycle(
            original, SyntheticFounderReviewContext(), decision="ACCEPT",
            decision_id=ACCEPT_ID, reason="Synthetic product direction accepted for review testing.")
        repeated = review_synthetic_cycle(
            original, SyntheticFounderReviewContext(), decision="ACCEPT",
            decision_id=ACCEPT_ID, reason="Synthetic product direction accepted for review testing.")
        for expected in (b"Synthetic Founder Review", b"ACCEPT", b"APPROVED_INTERNAL",
                         b"product knowledge only", b"no ARCH routing"):
            self.assertIn(expected, reviewed.task_document_bytes)
        self.assertEqual(reviewed.cycle.proposal_bytes, original.proposal_bytes)
        self.assertEqual(reviewed.review_bytes, repeated.review_bytes)
        self.assertEqual(reviewed.task_document_bytes, repeated.task_document_bytes)


if __name__ == "__main__":
    unittest.main()
