import inspect
import io
import json
import os
import stat
import unittest
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from prod_cycle_fixtures import DeterministicProductFake
from test_prod_cycle import synthetic_task as ats_0701_task
from tools.agent_control import prod_first_live
from tools.agent_control.prod_contract import load_contract
from tools.agent_control.prod_first_live import (
    EXPECTED_ATS_1201_INTERNAL_REQUEST_DIGEST,
    EXPECTED_ATS_1201_WIRE_REQUEST_DIGEST,
    EXPECTED_SCHEMA_DIGEST, EXPECTED_STABLE_CONTRACT_DIGEST,
    FROZEN_ATS_0701_WIRE_FIXTURE_DIGEST, FirstLiveFailure,
    _run_first_live_for_tests, format_success, prepare_first_live_bindings,
    stable_contract_digest, stable_contract_identity,
)
from tools.agent_control.prod_model_transport import (
    INITIAL_PREDECESSOR_INVALID, TRUSTED_ENDPOINT, TRUSTED_MODEL,
    PROVIDER_RATE_LIMIT,
    build_product_model_request,
)
from tools.agent_control.prod_openai_http import OpenAIHTTPError, project_openai_responses_request
from tools.agent_control.prod_prelive import (
    DevelopmentOneShotCredential, OwnerReviewedSource, synthetic_first_live_task,
)
from tools.agent_control.prod_response_capture import (
    CAPTURE_DIRECTORY, cleanup_private_response_captures,
)
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import ValidationError

CHECKPOINT = "fb10ef79aaf3a8c4e3e5c243c2709452e4826a7a"
SECRET = "synthetic-first-live-secret"
HIDDEN_REASONING = "synthetic-hidden-reasoning"


def proposal(changes=None):
    value = DeterministicProductFake().propose(synthetic_first_live_task())
    value.update(changes or {})
    return value


def response_bytes(candidate=None, *, refusal=False):
    content = ([{"type": "refusal", "refusal": "synthetic refusal"}]
               if refusal else [{
                   "type": "output_text",
                   "text": canonical_json(candidate or proposal()),
                   "annotations": [],
               }])
    return canonical_json({
        "id": "resp_first_live_synthetic",
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": HIDDEN_REASONING},
            {"id": "msg_first_live_synthetic", "type": "message",
             "status": "completed", "role": "assistant", "content": content},
        ],
    }).encode()


class FakeFirstLiveTransport:
    credential_owned = True
    test_only = True

    def __init__(self, provider, *, raw=None, error=None, response_metadata=None,
                 private_response_capture=None):
        self.provider = provider
        self.raw = raw if raw is not None else response_bytes()
        self.error = error
        self.response_metadata = response_metadata
        self.private_response_capture = private_response_capture
        self.calls = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        credential = self.provider.credential()
        if credential != SECRET:
            raise AssertionError("unexpected synthetic credential")
        if self.error is not None:
            raise self.error
        if self.private_response_capture is not None:
            self.private_response_capture.capture(self.raw)
        return self.raw

    @property
    def private_response_capture_result(self):
        if self.private_response_capture is None:
            return None
        return self.private_response_capture.result


def reviewed():
    return OwnerReviewedSource.from_owner_authorization(CHECKPOINT)


class ProductFirstLiveTests(unittest.TestCase):
    def run_local(self, *, raw=None, error=None):
        prompts = []
        transports = []

        def factory(provider):
            transport = FakeFirstLiveTransport(provider, raw=raw, error=error)
            transports.append(transport)
            return transport

        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT):
            result = _run_first_live_for_tests(
                reviewed(), lambda: True,
                lambda prompt: prompts.append(prompt) or SECRET, factory)
        return result, transports[0], prompts

    def test_reviewed_digests_regenerate_and_distinguish_task_instances(self):
        bindings = prepare_first_live_bindings()
        self.assertEqual(bindings.stable_contract_digest, EXPECTED_STABLE_CONTRACT_DIGEST)
        self.assertEqual(bindings.internal_request_digest,
                         EXPECTED_ATS_1201_INTERNAL_REQUEST_DIGEST)
        self.assertEqual(bindings.wire_request_digest,
                         EXPECTED_ATS_1201_WIRE_REQUEST_DIGEST)
        self.assertEqual(bindings.internal_request_digest,
                         digest(build_product_model_request(synthetic_first_live_task())[0]))
        old_internal, _ = build_product_model_request(ats_0701_task())
        old_wire = project_openai_responses_request(old_internal)
        self.assertEqual(FROZEN_ATS_0701_WIRE_FIXTURE_DIGEST,
                         "bdc532506e2d4ce59a4dd41af440a0a4ef3bba21a865df5d9060c58c638f759d")
        self.assertNotEqual(digest(old_wire), FROZEN_ATS_0701_WIRE_FIXTURE_DIGEST)
        self.assertNotEqual(digest(old_wire), bindings.wire_request_digest)
        self.assertEqual(stable_contract_digest(), bindings.stable_contract_digest)

    def test_stable_contract_changes_for_security_relevant_drift(self):
        original = stable_contract_identity()
        mutations = []
        for path, value in (("proposal_schema_digest", "0" * 64),
                            ("logical_model", "changed-model"),
                            ("tools", [{"type": "shell"}]),
                            ("max_retries", 1)):
            changed = deepcopy(original)
            changed[path] = value
            mutations.append(changed)
        for changed in mutations:
            with self.subTest(field=next(key for key in changed if changed[key] != original[key])):
                self.assertNotEqual(stable_contract_digest(changed),
                                    stable_contract_digest(original))
        self.assertEqual(original["proposal_schema_digest"], EXPECTED_SCHEMA_DIGEST)
        self.assertEqual(len(original["parser_implementation_digest"]), 64)
        self.assertEqual(len(original["proposal_validator_implementation_digest"]), 64)

    def test_task_objective_and_reference_changes_change_instance_digest(self):
        original = synthetic_first_live_task()
        variants = []
        changed = deepcopy(original)
        changed["objective"] += " Synthetic variation."
        variants.append(changed)
        changed = deepcopy(original)
        changed["input_references"][0]["digest"] = "0" * 64
        variants.append(changed)
        original_digest = digest(build_product_model_request(original)[0])
        for variant in variants:
            self.assertNotEqual(digest(build_product_model_request(variant)[0]),
                                original_digest)

    def test_source_contract_request_and_tty_fail_before_prompt_or_transport(self):
        prompts = []
        factory = lambda provider: self.fail("transport constructed")
        cases = [
            ("source", {"_current_source_commit": "0" * 40}),
            ("contract", {"EXPECTED_STABLE_CONTRACT_DIGEST": "0" * 64}),
            ("internal", {"EXPECTED_ATS_1201_INTERNAL_REQUEST_DIGEST": "0" * 64}),
            ("wire", {"EXPECTED_ATS_1201_WIRE_REQUEST_DIGEST": "0" * 64}),
        ]
        for name, changes in cases:
            with self.subTest(name=name):
                patches = [patch.object(prod_first_live, key, value)
                           for key, value in changes.items()]
                with patches[0]:
                    if name != "source":
                        source_patch = patch.object(
                            prod_first_live, "_current_source_commit", return_value=CHECKPOINT)
                    else:
                        source_patch = patch.object(
                            prod_first_live, "_current_source_commit", return_value=changes["_current_source_commit"])
                    with source_patch, self.assertRaises(FirstLiveFailure):
                        _run_first_live_for_tests(
                            reviewed(), lambda: True,
                            lambda prompt: prompts.append(prompt) or SECRET, factory)
        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT), self.assertRaises(FirstLiveFailure):
            _run_first_live_for_tests(
                reviewed(), lambda: False,
                lambda prompt: prompts.append(prompt) or SECRET, factory)
        self.assertEqual(prompts, [])

    def test_one_request_zero_tools_fixed_routing_and_working_proposal(self):
        result, transport, prompts = self.run_local()
        self.assertEqual(len(prompts), 1)
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["endpoint"], TRUSTED_ENDPOINT)
        self.assertEqual(call["model"], TRUSTED_MODEL)
        request = prod_first_live.json.loads(call["request"])
        self.assertEqual(request["tools"], [])
        self.assertEqual(request["request_policy"], {"max_requests": 1, "max_retries": 0})
        self.assertEqual(result.cycle.proposal["knowledge_state"], "WORKING")
        self.assertEqual(result.cycle.task["task_id"], "ATS-1201")
        self.assertIsNone(result.cycle.proposal["predecessor_proposal_id"])
        with self.assertRaises(ValidationError):
            transport.provider.credential()

    def test_private_capture_requires_explicit_flag_and_reports_private_file(self):
        default_transports = []

        def default_factory(provider):
            transport = FakeFirstLiveTransport(provider)
            default_transports.append(transport)
            return transport

        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT):
            result = _run_first_live_for_tests(
                reviewed(), lambda: True, lambda _: SECRET, default_factory)
        self.assertIsNone(default_transports[0].private_response_capture)
        self.assertIsNone(result.capture_result)
        self.assertNotIn("CAPTURE_CREATED", format_success(result))

        captured_transports = []

        def capture_factory(provider, *, private_response_capture=None):
            transport = FakeFirstLiveTransport(
                provider, private_response_capture=private_response_capture)
            captured_transports.append(transport)
            return transport

        try:
            with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT):
                result = _run_first_live_for_tests(
                    reviewed(), lambda: True, lambda _: SECRET, capture_factory,
                    private_response_capture=True)
            capture = result.capture_result
            self.assertTrue(capture["created"])
            self.assertTrue(capture["path"].startswith(CAPTURE_DIRECTORY + os.sep))
            self.assertNotIn(os.getcwd(), capture["path"])
            self.assertEqual(capture["bytes"], len(captured_transports[0].raw))
            file_stat = os.stat(capture["path"])
            self.assertTrue(stat.S_ISREG(file_stat.st_mode))
            self.assertEqual(file_stat.st_mode & 0o777, 0o600)
            with open(capture["path"], "rb") as captured:
                self.assertEqual(captured.read(), captured_transports[0].raw)
            output = format_success(result)
            self.assertIn("CAPTURE_CREATED: YES", output)
            self.assertIn("CAPTURE_MODE: PRIVATE_DIAGNOSTIC", output)
        finally:
            cleanup_private_response_captures()

    def test_initial_non_null_predecessor_is_rejected_without_review_or_routing(self):
        authority = {"agents": [], "grants": [], "assignments": [], "registry": {}}
        before = deepcopy(authority)
        transports = []

        def factory(provider):
            transport = FakeFirstLiveTransport(
                provider,
                raw=response_bytes(proposal({
                    "predecessor_proposal_id":
                    "00000000-0000-4000-8000-000000000702"})))
            transports.append(transport)
            return transport

        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT), \
                patch("tools.agent_control.prod_review.create_product_review") as review:
            with self.assertRaises(FirstLiveFailure) as caught:
                _run_first_live_for_tests(reviewed(), lambda: True, lambda _: SECRET, factory)
        self.assertEqual(caught.exception.classification, INITIAL_PREDECESSOR_INVALID)
        self.assertEqual(len(transports[0].calls), 1)
        review.assert_not_called()
        self.assertEqual(authority, before)

    def test_refusal_malformed_invalid_authority_and_self_promotion_stop_once(self):
        cases = [
            (response_bytes(refusal=True), "PROVIDER_ENVELOPE_INVALID"),
            (b"not-json", "PROVIDER_ENVELOPE_INVALID"),
            (response_bytes(proposal({"title": ""})), "PROPOSAL_SCHEMA_MISMATCH"),
            (response_bytes(proposal({"execution_grant": "grant"})),
             "PROPOSAL_SCHEMA_MISMATCH"),
            (response_bytes(proposal({"knowledge_state": "APPROVED_INTERNAL"})),
             "KNOWLEDGE_STATE_INVALID"),
        ]
        for raw, classification in cases:
            transports = []

            def factory(provider):
                transport = FakeFirstLiveTransport(provider, raw=raw)
                transports.append(transport)
                return transport

            with self.subTest(size=len(raw)), patch.object(
                    prod_first_live, "_current_source_commit", return_value=CHECKPOINT), self.assertRaises(FirstLiveFailure) as caught:
                _run_first_live_for_tests(reviewed(), lambda: True, lambda _: SECRET, factory)
            self.assertEqual(caught.exception.classification, classification)
            self.assertEqual(len(transports[0].calls), 1)

    def test_envelope_failure_exposes_only_bounded_structure(self):
        transports = []

        def factory(provider):
            transport = FakeFirstLiveTransport(
                provider,
                raw=response_bytes(refusal=True))
            transports.append(transport)
            return transport

        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT):
            with self.assertRaises(FirstLiveFailure) as caught:
                _run_first_live_for_tests(reviewed(), lambda: True, lambda _: SECRET, factory)
        self.assertEqual(caught.exception.classification, "PROVIDER_ENVELOPE_INVALID")
        structure = caught.exception.provider_structure
        self.assertEqual(structure["reason"], "REFUSAL_PRESENT")
        self.assertEqual(structure["content_types"], ["refusal"])
        self.assertTrue(structure["refusal_present"])
        diagnostic = prod_first_live.json.dumps(structure)
        self.assertNotIn("synthetic refusal", diagnostic)
        self.assertNotIn(HIDDEN_REASONING, diagnostic)
        self.assertNotIn("resp_first_live_synthetic", diagnostic)
        self.assertEqual(len(transports[0].calls), 1)

    def test_malformed_provider_json_reaches_founder_serialized_result(self):
        sentinel = "synthetic-provider-secret-model-sentinel"
        raw = (b'{"malformed":"' + sentinel.encode()).ljust(11834, b" ")
        response_metadata = {
            "http_status": 200,
            "content_type": "APPLICATION_JSON",
            "content_encoding": "GZIP",
            "body_bytes": 11834,
            "body_empty": False,
            "content_length_present": True,
            "declared_content_length": 11834,
            "declared_content_length_valid": True,
            "declared_length_matches": True,
            "utf8_decode_success": True,
            "json_decode_success": None,
        }

        def factory(provider):
            return FakeFirstLiveTransport(
                provider, raw=raw, response_metadata=response_metadata)

        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT):
            with self.assertRaises(FirstLiveFailure) as caught:
                _run_first_live_for_tests(
                    reviewed(), lambda: True, lambda _: SECRET, factory)

        error = caught.exception
        blocked = {"status": "BLOCKED", "classification": error.classification}
        if error.provider_structure is not None:
            blocked["provider_structure"] = error.provider_structure
        rendered = json.dumps(blocked, sort_keys=True, separators=(",", ":"))
        structure = blocked["provider_structure"]
        self.assertEqual(blocked["classification"], "PROVIDER_ENVELOPE_INVALID")
        self.assertEqual(structure["reason"], "RESPONSE_JSON_INVALID")
        self.assertEqual(structure["http_response"]["http_status"], 200)
        self.assertEqual(structure["http_response"]["content_type"], "APPLICATION_JSON")
        self.assertEqual(structure["http_response"]["content_encoding"], "GZIP")
        self.assertEqual(structure["http_response"]["body_bytes"], 11834)
        diagnostic = structure["json_error"]
        self.assertEqual(diagnostic["category"], "UNTERMINATED_STRING")
        self.assertEqual(diagnostic["body_bytes"], 11834)
        for key in ("line", "column", "position", "character_count", "body_bytes"):
            self.assertIsInstance(diagnostic[key], int)
            self.assertGreaterEqual(diagnostic[key], 0)
        self.assertNotIn(sentinel, rendered)
        self.assertNotIn("malformed", rendered)

    def test_strict_json_validation_reaches_founder_as_bounded_failure(self):
        sentinel = "synthetic-strict-json-secret-sentinel"
        raw = b'{"duplicate":"' + sentinel.encode() + b'","duplicate":"x"}'
        response_metadata = {
            "http_status": 200,
            "content_type": "APPLICATION_JSON",
            "content_encoding": "GZIP",
            "body_bytes": 11834,
            "body_empty": False,
            "content_length_present": True,
            "declared_content_length": 11834,
            "declared_content_length_valid": True,
            "declared_length_matches": True,
            "utf8_decode_success": True,
            "json_decode_success": None,
        }

        def factory(provider):
            return FakeFirstLiveTransport(
                provider, raw=raw, response_metadata=response_metadata)

        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT):
            with self.assertRaises(FirstLiveFailure) as caught:
                _run_first_live_for_tests(
                    reviewed(), lambda: True, lambda _: SECRET, factory)

        error = caught.exception
        blocked = {"status": "BLOCKED", "classification": error.classification}
        if error.provider_structure is not None:
            blocked["provider_structure"] = error.provider_structure
        rendered = json.dumps(blocked, sort_keys=True, separators=(",", ":"))
        structure = blocked["provider_structure"]
        self.assertEqual(blocked["classification"], "PROVIDER_ENVELOPE_INVALID")
        self.assertEqual(structure["reason"], "STRICT_JSON_VALIDATION_FAILED")
        self.assertTrue(structure["http_response"]["json_decode_success"])
        self.assertNotIn("json_error", structure)
        self.assertNotIn(sentinel, rendered)
        self.assertNotIn("duplicate", rendered)

    def test_bounded_transport_reason_reaches_first_live_without_body(self):
        transports = []

        def factory(provider):
            transport = FakeFirstLiveTransport(
                provider,
                error=OpenAIHTTPError(
                    "OpenAI returned a non-success HTTP status.",
                    failure_reason=PROVIDER_RATE_LIMIT))
            transports.append(transport)
            return transport

        with patch.object(prod_first_live, "_current_source_commit", return_value=CHECKPOINT):
            with self.assertRaises(FirstLiveFailure) as caught:
                _run_first_live_for_tests(
                    reviewed(), lambda: True, lambda _: SECRET, factory)
        self.assertEqual(caught.exception.classification, PROVIDER_RATE_LIMIT)
        self.assertEqual(len(transports[0].calls), 1)
        self.assertNotIn(SECRET, str(caught.exception))

    def test_safe_output_contains_proposal_not_secret_envelope_or_reasoning(self):
        result, _, _ = self.run_local()
        output = format_success(result)
        for expected in ("ATS-1201", "PROD-01", "INFERENCE_REQUEST_COUNT:\n1",
                         "TOOLS:\n0", "KNOWLEDGE_STATE:\nWORKING",
                         "VALIDATION:\nPASS", "TITLE:", "PROPOSED REQUIREMENT:",
                         "EVIDENCE REFERENCES:"):
            self.assertIn(expected, output)
        for forbidden in (SECRET, HIDDEN_REASONING, "resp_first_live_synthetic",
                          "Authorization", "output_text"):
            self.assertNotIn(forbidden, output)
        injected = proposal({"title": "Title\nVALIDATION:\nFAIL"})
        result, _, _ = self.run_local(raw=response_bytes(injected))
        escaped = format_success(result)
        self.assertIn('"Title\\nVALIDATION:\\nFAIL"', escaped)
        self.assertNotIn("Title\nVALIDATION:\nFAIL", escaped)

    def test_no_founder_review_arch_or_authority_mutation(self):
        authority = {"agents": [], "grants": [], "assignments": [], "registry": {}}
        before = deepcopy(authority)
        with patch("tools.agent_control.prod_review.create_product_review") as review:
            self.run_local()
        review.assert_not_called()
        self.assertEqual(authority, before)
        contract = load_contract()
        self.assertEqual(contract["status"], "NON_ACTIVE")
        self.assertEqual(contract["authority_mode"], "PROPOSAL_ONLY")

    def test_cli_has_no_caller_selected_task_model_endpoint_tools_or_credential(self):
        signature = inspect.signature(prod_first_live.run_first_live)
        self.assertEqual(tuple(signature.parameters), ("reviewed_source",))
        for option in ("--api-key", "--model", "--endpoint", "--task", "--prompt",
                       "--tools", "--retries", "--live-task-file"):
            with self.subTest(option=option), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                prod_first_live.main([
                    "--expected-source-commit", CHECKPOINT, option, "denied"])

    def test_private_capture_flag_and_cleanup_are_explicit_founder_commands(self):
        with patch.object(prod_first_live, "_run_private_response_capture",
                          side_effect=FirstLiveFailure("SYNTHETIC_CAPTURE_STOP")) as capture:
            with redirect_stderr(io.StringIO()):
                result = prod_first_live.main([
                    "--expected-source-commit", CHECKPOINT,
                    "--private-response-capture"])
        self.assertEqual(result, 2)
        capture.assert_called_once()

        with patch.object(prod_first_live, "cleanup_private_response_captures",
                          return_value=0):
            output = io.StringIO()
            with redirect_stdout(output):
                result = prod_first_live.main(["--cleanup-private-response-capture"])
        self.assertEqual(result, 0)
        self.assertIn("CLEANUP_REMAINING: NO", output.getvalue())


if __name__ == "__main__":
    unittest.main()
