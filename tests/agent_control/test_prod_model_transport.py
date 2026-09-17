import json
import unittest
from copy import deepcopy

from prod_cycle_fixtures import DeterministicProductFake
from test_prod_cycle import synthetic_task
from tools.agent_control.prod_contract import load_contract, validate_product_proposal
from tools.agent_control.prod_model_transport import (
    MAX_RESPONSE_BYTES, TIMEOUT_SECONDS, TRUSTED_ENDPOINT, TRUSTED_MODEL,
    ProductModelFailure, build_product_model_request, project_product_context,
    run_product_model_cycle,
)
from tools.agent_control.prod_review import SyntheticFounderReviewContext, create_product_review
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import ValidationError


class SyntheticCredentialProvider:
    def __init__(self):
        self.marker = object()
        self.calls = 0

    def credential(self):
        self.calls += 1
        return self.marker


class InMemoryTransport:
    def __init__(self, proposal=None, *, raw=None, error=None):
        self.proposal = proposal
        self.raw = raw
        self.error = error
        self.calls = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.raw is not None:
            return self.raw
        return json.dumps({
            "status": "completed",
            "output": [{"type": "structured_json", "content": self.proposal}],
        }, sort_keys=True, separators=(",", ":")).encode()


def proposal(changes=None):
    value = DeterministicProductFake().propose(synthetic_task())
    value.update(changes or {})
    return value


class ProductModelTransportTests(unittest.TestCase):
    def run_cycle(self, *, candidate=None, raw=None, error=None, task=None):
        transport = InMemoryTransport(candidate or proposal(), raw=raw, error=error)
        credentials = SyntheticCredentialProvider()
        result = run_product_model_cycle(task or synthetic_task(), transport, credentials)
        return result, transport, credentials

    def test_valid_flow_is_one_request_zero_tools_and_deterministic(self):
        first, transport, credentials = self.run_cycle()
        second, _, _ = self.run_cycle()
        self.assertEqual(first.proposal_bytes, second.proposal_bytes)
        self.assertEqual(first.proposal_digest, second.proposal_digest)
        self.assertEqual(validate_product_proposal(first.proposal), first.proposal)
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        request = json.loads(call["request"])
        self.assertEqual(request["tools"], [])
        self.assertEqual(call["endpoint"], TRUSTED_ENDPOINT)
        self.assertEqual(call["model"], TRUSTED_MODEL)
        self.assertEqual(call["timeout_seconds"], TIMEOUT_SECONDS)
        self.assertFalse(call["allow_redirects"])
        self.assertFalse(call["trust_environment"])
        self.assertIs(call["credential"], credentials.marker)
        self.assertNotIn("credential", request)
        self.assertNotIn("credential", canonical_json(first.audit_metadata).lower())
        self.assertEqual(first.audit_metadata["result_classification"], "VALIDATED_PROPOSAL")

    def test_context_is_metadata_only_and_caller_cannot_select_routing(self):
        context = project_product_context(synthetic_task())
        self.assertEqual(set(context), {"agent_id", "role", "authority", "task_id", "task_class",
                                       "objective", "reference_metadata", "behavior_contract",
                                       "required_output_schema"})
        self.assertNotIn("endpoint", canonical_json(context))
        self.assertNotIn("model", context)
        request, _ = build_product_model_request(synthetic_task())
        self.assertEqual(request["model"], TRUSTED_MODEL)
        self.assertEqual(request["tools"], [])

    def test_timeout_transport_and_malformed_output_make_no_retry(self):
        cases = [
            {"error": TimeoutError("synthetic")},
            {"raw": b"not-json"},
            {"raw": json.dumps({"status": "completed", "output": []}).encode()},
        ]
        for case in cases:
            with self.subTest(case=tuple(case)):
                transport = InMemoryTransport(**case)
                with self.assertRaises(ProductModelFailure):
                    run_product_model_cycle(synthetic_task(), transport, SyntheticCredentialProvider())
                self.assertEqual(len(transport.calls), 1)

    def test_oversized_input_stops_before_transport_and_response_is_bounded(self):
        task = synthetic_task()
        task["objective"] = "x" * 4097
        transport = InMemoryTransport(proposal())
        with self.assertRaises(ValidationError):
            run_product_model_cycle(task, transport, SyntheticCredentialProvider())
        self.assertEqual(transport.calls, [])
        transport = InMemoryTransport(raw=b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaises(ProductModelFailure):
            run_product_model_cycle(synthetic_task(), transport, SyntheticCredentialProvider())
        self.assertEqual(len(transport.calls), 1)

    def test_multiple_wrong_unstructured_and_unknown_outputs_are_rejected(self):
        envelopes = [
            {"status": "completed", "output": [
                {"type": "structured_json", "content": proposal()},
                {"type": "structured_json", "content": proposal()},
            ]},
            {"status": "completed", "output": [{"type": "text", "content": "proposal"}]},
            {"status": "completed", "output": [{"type": "structured_json", "content": proposal()}], "extra": True},
        ]
        for envelope in envelopes:
            transport = InMemoryTransport(raw=canonical_json(envelope).encode())
            with self.assertRaises(ProductModelFailure):
                run_product_model_cycle(synthetic_task(), transport, SyntheticCredentialProvider())

    def test_authority_and_knowledge_claims_are_rejected(self):
        for changes in ({"approved": True}, {"execution_grant": "grant"},
                        {"knowledge_state": "APPROVED_INTERNAL"},
                        {"knowledge_state": "PUBLICATION_ELIGIBLE"}):
            with self.subTest(changes=changes), self.assertRaises(ProductModelFailure):
                self.run_cycle(candidate=proposal(changes))

    def test_state_is_unchanged_and_proposal_supports_founder_review(self):
        task = synthetic_task()
        before = deepcopy(task)
        authority = {"agents": [], "grants": [], "reservations": [], "fence": 1}
        authority_before = deepcopy(authority)
        result, _, _ = self.run_cycle(task=task)
        review = create_product_review(
            result.proposal, SyntheticFounderReviewContext(), decision="ACCEPT",
            decision_id="00000000-0000-4000-8000-000000000710", reason="Synthetic acceptance.")
        self.assertEqual(review["resulting_knowledge_state"], "APPROVED_INTERNAL")
        self.assertEqual(task, before)
        self.assertEqual(authority, authority_before)
        contract = load_contract()
        self.assertEqual(contract["status"], "NON_ACTIVE")
        self.assertEqual(contract["authority_mode"], "PROPOSAL_ONLY")


if __name__ == "__main__":
    unittest.main()
