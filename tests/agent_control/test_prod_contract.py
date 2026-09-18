import unittest

from tools.agent_control.prod_contract import (
    TASK_CLASSES, contract_digest, load_contract, validate_product_proposal,
    validate_product_task,
)
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import ValidationError


def reference(kind="PRODUCT_DOCUMENT"):
    return {"reference_type": kind, "reference_id": "DOC-APPROVED-1", "digest": "a" * 64,
            "knowledge_state": "APPROVED_INTERNAL"}


def task(task_class="PRODUCT_REQUIREMENT"):
    return {"agent_id": "PROD-01", "task_id": "ATS-0001", "task_class": task_class,
            "objective": "Define a bounded product requirement.", "input_references": [reference()]}


def proposal():
    return {
        "agent_id": "PROD-01", "task_id": "ATS-0001",
        "proposal_id": "00000000-0000-4000-8000-000000000001",
        "predecessor_proposal_id": None,
        "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL", "title": "Synthetic proposal",
        "problem_user_need": "A user needs a clear bounded flow.",
        "objective": "Describe referenced product intent.",
        "proposed_requirement": "The product should expose the bounded flow.",
        "acceptance_intent": ["The intended flow is understandable."],
        "dependencies": [], "assumptions": ["Product context reference is supplied."],
        "risks_open_questions": ["Founder approval remains pending."],
        "priority_recommendation": "P2", "evidence_references": [reference()],
        "knowledge_state": "WORKING",
    }


class ProductContractTests(unittest.TestCase):
    def test_contract_identity_role_permissions_and_determinism(self):
        contract = load_contract()
        self.assertEqual(contract["agent_id"], "PROD-01")
        self.assertEqual(contract["role"], "Product")
        self.assertEqual(contract["role_family"], "PRODUCT")
        self.assertEqual(contract["status"], "NON_ACTIVE")
        self.assertEqual(tuple(contract["task_classes"]), TASK_CLASSES)
        self.assertTrue(all(value is False for value in contract["permissions"].values()))
        self.assertEqual(contract_digest(), contract_digest())
        self.assertEqual(canonical_json(contract), canonical_json(load_contract()))

    def test_all_closed_task_classes_validate_and_unknown_is_rejected(self):
        for task_class in TASK_CLASSES:
            with self.subTest(task_class=task_class):
                self.assertEqual(validate_product_task(task(task_class))["task_class"], task_class)
        with self.assertRaises(ValidationError):
            validate_product_task(task("DEPLOYMENT"))
        for task_id in ("ATS-0000", "ATS-00001"):
            with self.subTest(task_id=task_id), self.assertRaises(ValidationError):
                value = task(); value["task_id"] = task_id
                validate_product_task(value)
        for task_id in ("ATS-0001", "ATS-1201", "ATS-10000"):
            with self.subTest(task_id=task_id):
                value = task(); value["task_id"] = task_id
                self.assertEqual(validate_product_task(value)["task_id"], task_id)

    def test_task_references_only_approved_bounded_inputs(self):
        founder = reference("FOUNDER_DIRECTION")
        founder.update(reference_id="FOUNDER-DIRECTION-1", knowledge_state="DIRECT_FOUNDER")
        value = task(); value["input_references"] = [founder]
        validate_product_task(value)
        for change in ({"path": "/etc/passwd"}, {"environment": {"TOKEN": "value"}},
                       {"command": "execute"}, {"raw_customer_record": "value"}):
            bad = task(); bad["input_references"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                validate_product_task(bad)

    def test_proposal_is_bounded_and_cannot_claim_authority(self):
        validate_product_proposal(proposal())
        for field in ("approved", "authorized", "execution_grant", "assignment",
                      "deployment_status", "implementation_status", "grant", "execution",
                      "deployment", "status"):
            bad = proposal(); bad[field] = True
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_product_proposal(bad)
        bad = proposal(); bad["acceptance_intent"] = ["x"] * 51
        with self.assertRaises(ValidationError):
            validate_product_proposal(bad)

    def test_duplicate_dependencies_are_rejected_by_runtime_validator(self):
        bad = proposal()
        bad["dependencies"] = ["ATS-0001", "ATS-0001"]
        with self.assertRaises(ValidationError):
            validate_product_proposal(bad)
        for claim in ("approved", "assigned", "authorized", "deployed", "implemented",
                      "tested", "published"):
            bad = proposal(); bad["proposed_requirement"] = f"This proposal is {claim}."
            with self.subTest(claim=claim), self.assertRaises(ValidationError):
                validate_product_proposal(bad)

    def test_current_status_claims_are_denied_but_future_requirements_are_allowed(self):
        rejected = (
            "Implementation is complete.",
            "This feature has been implemented.",
            "Tests passed.",
            "This was tested successfully.",
            "Deployment completed.",
            "This is approved.",
            "Execution was authorized.",
            "The task was assigned.",
            "The feature is already implemented!",
            "THE FEATURE WAS TESTED SUCCESSFULLY.",
            "The deployment has completed.",
            "The feature\twas\nimplemented.",
            "Tests have passed.",
            "Deployment was completed successfully.",
            "The feature has already been implemented.",
            "The task had been successfully assigned.",
            "All tests have passed.",
        )
        for claim in rejected:
            bad = proposal(); bad["proposed_requirement"] = claim
            with self.subTest(claim=claim), self.assertRaises(ValidationError):
                validate_product_proposal(bad)

        allowed = (
            "The criterion must be tested before release.",
            "The feature should be implemented behind a feature flag.",
            "Deployment must require Founder approval.",
            "The requirement should be tested on mobile.",
            "Implementation should preserve task history.",
            "The UI should show whether a task was tested.",
            "Acceptance requires the feature to be deployed safely.",
        )
        for requirement in allowed:
            value = proposal(); value["proposed_requirement"] = requirement
            with self.subTest(requirement=requirement):
                self.assertEqual(validate_product_proposal(value)["proposed_requirement"],
                                 requirement)

    def test_revision_predecessor_remains_valid_outside_initial_first_live(self):
        value = proposal()
        value["predecessor_proposal_id"] = "00000000-0000-4000-8000-000000000002"
        self.assertEqual(validate_product_proposal(value), value)

    def test_secrets_and_credentials_are_rejected(self):
        for secret in ("API_KEY=synthetic-secret", "password: synthetic-secret",
                       "-----BEGIN PRIVATE KEY-----"):
            bad = proposal(); bad["proposed_requirement"] = secret
            with self.subTest(secret=secret), self.assertRaises(ValidationError):
                validate_product_proposal(bad)

    def test_knowledge_cannot_self_promote(self):
        for state in ("APPROVED_INTERNAL", "PUBLICATION_ELIGIBLE"):
            bad = proposal(); bad["knowledge_state"] = state
            with self.subTest(state=state), self.assertRaises(ValidationError):
                validate_product_proposal(bad)

    def test_identity_and_role_are_closed(self):
        bad = task(); bad["agent_id"] = "PROD-02"
        with self.assertRaises(ValidationError):
            validate_product_task(bad)
        contract = load_contract()
        self.assertNotIn("APPROVE", contract["authority_mode"])


if __name__ == "__main__":
    unittest.main()
