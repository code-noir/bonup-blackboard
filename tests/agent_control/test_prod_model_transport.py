import json
import re
import unittest
from copy import deepcopy

from prod_cycle_fixtures import DeterministicProductFake
from test_prod_cycle import synthetic_task
from tools.agent_control.prod_contract import load_contract, validate_product_proposal
from tools.agent_control.prod_model_transport import (
    ACCOUNT_MODEL_ACCESS, LOCAL_CONTRACT_VALIDATED, MAX_RESPONSE_BYTES,
    INITIAL_PREDECESSOR_INVALID, PRODUCT_PROPOSAL_SCHEMA_DIGEST,
    PROVIDER_WIRE_COMPATIBILITY, TASK_ID_PATTERN, TIMEOUT_SECONDS,
    TRUSTED_ENDPOINT, TRUSTED_MODEL,
    ProductModelFailure, build_product_model_request, project_product_context,
    run_product_model_cycle, validate_provider_schema_subset,
)
from tools.agent_control.prod_review import SyntheticFounderReviewContext, create_product_review
from tools.agent_control.serialization import canonical_json, digest
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
        return response_bytes(self.proposal)


def proposal(changes=None):
    value = DeterministicProductFake().propose(synthetic_task())
    value.update(changes or {})
    return value


def response_envelope(candidate=None, *, output=None, status="completed"):
    return {
        "id": "resp_synthetic",
        "status": status,
        "output": output if output is not None else [{
            "id": "msg_synthetic",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": canonical_json(candidate or proposal()),
                "annotations": [],
            }],
        }],
    }


def response_bytes(candidate=None, **kwargs):
    return canonical_json(response_envelope(candidate, **kwargs)).encode()


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
        self.assertEqual(request["logical_model"], TRUSTED_MODEL)
        self.assertEqual(request["tools"], [])

    def test_internal_request_contract_and_schema_are_frozen(self):
        first, first_bytes = build_product_model_request(synthetic_task())
        second, second_bytes = build_product_model_request(synthetic_task())
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(first_bytes, canonical_json(first).encode())
        self.assertEqual(set(first), {
            "contract_version", "agent_id", "logical_model", "context", "tools",
            "output_contract", "request_policy"})
        self.assertEqual(first["agent_id"], "PROD-01")
        self.assertEqual(first["logical_model"], TRUSTED_MODEL)
        self.assertEqual(first["tools"], [])
        self.assertEqual(first["request_policy"], {"max_requests": 1, "max_retries": 0})
        output = first["output_contract"]
        self.assertEqual(output["type"], "PRODUCT_REQUIREMENT_PROPOSAL")
        self.assertEqual(output["encoding"], "STRICT_JSON_SCHEMA")
        self.assertTrue(output["strict"])
        self.assertFalse(output["schema"]["additionalProperties"])
        self.assertEqual(output["schema"]["properties"]["knowledge_state"],
                         {"type": "string", "const": "WORKING"})
        self.assertEqual(output["schema"]["properties"]["task_id"]["pattern"],
                         TASK_ID_PATTERN)
        self.assertEqual(output["schema"]["properties"]["title"]["pattern"], "\\S")
        self.assertNotIn("uniqueItems", output["schema"]["properties"]["dependencies"])
        self.assertEqual(output["schema"]["properties"]["dependencies"]["maxItems"], 50)
        self.assertIn("pattern", output["schema"]["properties"]["evidence_references"]
                      ["items"]["properties"]["reference_id"])
        self.assertEqual(output["schema_digest"], PRODUCT_PROPOSAL_SCHEMA_DIGEST)
        self.assertEqual(PRODUCT_PROPOSAL_SCHEMA_DIGEST,
                         "c13b322dff0b8da89699966165b4d6f3ab69f50efbb0cc540ab8a75133e661ce")
        self.assertEqual(set(output["schema"]["required"]),
                         set(output["schema"]["properties"]))
        self.assertFalse({"approved", "execution_grant", "assignment", "command"}
                         & set(output["schema"]["properties"]))
        self.assertNotIn("credential", canonical_json(first).lower())
        self.assertNotIn("endpoint", canonical_json(first).lower())
        changed = deepcopy(first)
        changed["output_contract"]["schema"]["additionalProperties"] = True
        self.assertNotEqual(canonical_json(first), canonical_json(changed))
        self.assertNotEqual(first_bytes, canonical_json(changed).encode())
        self.assertNotEqual(digest(first), digest(changed))
        self.assertIs(LOCAL_CONTRACT_VALIDATED, True)
        self.assertEqual(PROVIDER_WIRE_COMPATIBILITY, "LIVE_OR_OFFICIAL_CHECK_REQUIRED")
        self.assertEqual(ACCOUNT_MODEL_ACCESS, "AUTHENTICATED_CHECK_REQUIRED")

    def test_provider_schema_subset_rejects_unsupported_keywords(self):
        schema = build_product_model_request(synthetic_task())[0]["output_contract"]["schema"]
        validate_provider_schema_subset(schema)
        unsupported = deepcopy(schema)
        unsupported["properties"]["dependencies"]["uniqueItems"] = True
        with self.assertRaises(ValidationError):
            validate_provider_schema_subset(unsupported)

    def test_provider_task_id_pattern_matches_runtime_bounds(self):
        schema = build_product_model_request(synthetic_task())[0]["output_contract"]["schema"]
        pattern = schema["properties"]["task_id"]["pattern"]
        for task_id in ("ATS-0001", "ATS-1201", "ATS-10000"):
            with self.subTest(task_id=task_id):
                self.assertIsNotNone(re.fullmatch(pattern, task_id))
        for task_id in ("ATS-0000", "ATS-00001", "ATS-01234"):
            with self.subTest(task_id=task_id):
                self.assertIsNone(re.fullmatch(pattern, task_id))

    def test_request_states_runtime_only_task_and_evidence_constraints(self):
        context = project_product_context(synthetic_task())
        behavior = set(context["behavior_contract"])
        self.assertIn("COPY_TASK_ID_EXACTLY", behavior)
        self.assertIn("EVIDENCE_REFERENCES_MUST_BE_SUBSET_OF_INPUT_REFERENCES", behavior)
        self.assertIn("DO_NOT_INCLUDE_SENSITIVE_AUTHENTICATION_MATERIAL", behavior)
        schema = context["required_output_schema"]
        self.assertNotIn("const", schema["properties"]["task_id"])
        reference_properties = schema["properties"]["evidence_references"]["items"]["properties"]
        self.assertNotIn("const", reference_properties["reference_id"])

    def test_initial_predecessor_gate_is_local_and_revision_linkage_remains_valid(self):
        revision = proposal({
            "predecessor_proposal_id": "00000000-0000-4000-8000-000000000002"})
        result, _, _ = self.run_cycle(candidate=revision)
        self.assertEqual(result.proposal["predecessor_proposal_id"],
                         revision["predecessor_proposal_id"])
        transport = InMemoryTransport(revision)
        with self.assertRaises(ProductModelFailure) as caught:
            run_product_model_cycle(
                synthetic_task(), transport, SyntheticCredentialProvider(),
                require_initial_predecessor_null=True)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(caught.exception.audit_metadata["failure_reason"],
                         INITIAL_PREDECESSOR_INVALID)

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
            response_envelope(output=[]),
            response_envelope(output=[{"type": "function_call", "name": "execute"}]),
            response_envelope(output=[{"type": "unknown_provider_item"}]),
        ]
        for envelope in envelopes:
            transport = InMemoryTransport(raw=canonical_json(envelope).encode())
            with self.assertRaises(ProductModelFailure):
                run_product_model_cycle(synthetic_task(), transport, SyntheticCredentialProvider())

    def test_reasoning_before_completed_assistant_proposal_is_accepted(self):
        message = response_envelope()["output"][0]
        raw = response_bytes(output=[{"type": "reasoning", "id": "reasoning_synthetic"}, message])
        result, _, _ = self.run_cycle(raw=raw)
        self.assertEqual(validate_product_proposal(result.proposal), result.proposal)

    def test_ambiguous_refused_incomplete_and_malformed_responses_are_rejected(self):
        first = response_envelope()["output"][0]
        second = dict(first, id="msg_synthetic_2")
        two_parts = dict(first, content=first["content"] + first["content"])
        refusal = dict(first, content=[{"type": "refusal", "refusal": "synthetic"}])
        cases = [
            response_bytes(output=[first, second]),
            response_bytes(output=[two_parts]),
            response_bytes(output=[refusal]),
            response_bytes(status="incomplete"),
            response_bytes(output=[dict(first, status="incomplete")]),
            response_bytes(output=[dict(first, content=[{"type": "output_text", "text": "not-json"}])]),
            response_bytes(output=[dict(first, content=[{"type": "tool_result", "text": "{}"}])]),
        ]
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(ProductModelFailure):
                self.run_cycle(raw=raw)

    def test_authority_and_knowledge_claims_are_rejected(self):
        for changes in ({"approved": True}, {"execution_grant": "grant"},
                        {"knowledge_state": "APPROVED_INTERNAL"},
                        {"knowledge_state": "PUBLICATION_ELIGIBLE"}):
            with self.subTest(changes=changes), self.assertRaises(ProductModelFailure):
                self.run_cycle(candidate=proposal(changes))

    def test_output_rejections_have_bounded_stage_reasons(self):
        cases = [
            (b"not-json", "PROVIDER_ENVELOPE_INVALID"),
            (response_bytes(output=[dict(
                response_envelope()["output"][0],
                content=[{"type": "output_text", "text": "not-json"}])]),
             "STRUCTURED_JSON_INVALID"),
            (response_bytes(proposal({"title": ""})), "PROPOSAL_SCHEMA_MISMATCH"),
            (response_bytes(proposal({"proposal_id": "not-a-uuid"})),
             "PROPOSAL_ID_INVALID"),
            (response_bytes(proposal({"knowledge_state": "APPROVED_INTERNAL"})),
             "KNOWLEDGE_STATE_INVALID"),
            (response_bytes(proposal({"title": "This was approved."})),
             "AUTHORITY_CLAIM_REJECTED"),
            (response_bytes(proposal({"title": "api_key=synthetic-secret-value"})),
             "CONTENT_POLICY_REJECTED"),
            (response_bytes(proposal({"task_id": "ATS-9999"})),
             "TASK_BINDING_INVALID"),
        ]
        unbound = deepcopy(proposal())
        unbound["evidence_references"][0]["reference_id"] = "UNBOUND-REFERENCE"
        cases.append((response_bytes(unbound), "EVIDENCE_BINDING_INVALID"))
        for raw, reason in cases:
            with self.subTest(reason=reason), self.assertRaises(ProductModelFailure) as caught:
                self.run_cycle(raw=raw)
            self.assertEqual(caught.exception.audit_metadata["failure_reason"], reason)
            metadata = canonical_json(caught.exception.audit_metadata)
            for forbidden in (
                    "synthetic-secret-value", "This was approved.",
                    "The feature has been implemented."):
                self.assertNotIn(forbidden, metadata)

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
