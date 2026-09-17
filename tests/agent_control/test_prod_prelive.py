from contextlib import redirect_stderr, redirect_stdout
import inspect
import io
import os
import pickle
import socket
import sys
import unittest
from unittest.mock import patch

from tools.agent_control import prod_prelive
from tools.agent_control.prod_model_transport import build_product_model_request
from tools.agent_control.prod_prelive import (
    DevelopmentOneShotCredential, OwnerReviewedSource, run_preflight,
    synthetic_first_live_task,
)
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import ValidationError

SECRET = "synthetic-prelive-secret-marker"
BASELINE_COMMIT = "1ca7c2ad6ed2f6497755281826d4caa7522aeba7"


def checked_preflight(provider, expected_commit=BASELINE_COMMIT):
    reviewed = OwnerReviewedSource.from_owner_authorization(expected_commit)
    with patch.object(prod_prelive, "_current_source_commit", return_value=BASELINE_COMMIT):
        return run_preflight(provider, reviewed)


class ProductPreLiveTests(unittest.TestCase):
    def provider(self):
        return DevelopmentOneShotCredential._for_tests(SECRET)

    def test_hidden_provider_is_one_shot_nonserializable_and_nonrevealing(self):
        prompts = []
        provider = DevelopmentOneShotCredential.prompt_hidden(
            lambda prompt: prompts.append(prompt) or SECRET)
        self.assertEqual(len(prompts), 1)
        self.assertNotIn(SECRET, repr(provider))
        self.assertNotIn(SECRET, str(provider))
        with self.assertRaises(TypeError) as caught:
            pickle.dumps(provider)
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertEqual(provider.credential(), SECRET)
        with self.assertRaises(ValidationError) as caught:
            provider.credential()
        self.assertNotIn(SECRET, str(caught.exception))

    def test_preflight_is_safe_deterministic_metadata_and_does_not_consume(self):
        provider = self.provider()
        first = checked_preflight(provider)
        second = checked_preflight(provider)
        self.assertEqual(first, second)
        self.assertEqual(first["live_check_status"], "LIVE_CHECK_REQUIRED")
        self.assertEqual(first["credential_present"], "YES")
        self.assertEqual(first["tool_count"], 0)
        self.assertEqual(first["max_request_count"], 1)
        self.assertEqual(first["max_retries"], 0)
        self.assertNotIn(SECRET, canonical_json(first))
        request, _ = build_product_model_request(synthetic_first_live_task())
        self.assertNotIn(SECRET, canonical_json(request))
        self.assertEqual(provider.credential(), SECRET)

    def test_dry_run_makes_no_network_call(self):
        with (patch("requests.Session") as session,
              patch.object(socket, "socket") as network):
            checked_preflight(self.provider())
        session.assert_not_called()
        network.assert_not_called()

    def test_no_argv_environment_or_file_credential_source(self):
        source = inspect.getsource(DevelopmentOneShotCredential)
        for forbidden in ("os.environ", "getenv", ".env", "open(", "sys.argv"):
            self.assertNotIn(forbidden, source)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-secret"}):
            provider = DevelopmentOneShotCredential.prompt_hidden(lambda _: SECRET)
        self.assertEqual(provider.credential(), SECRET)
        self.assertNotIn(SECRET, sys.argv)

    def test_cli_has_no_live_or_force_path_and_discards_credential(self):
        provider = self.provider()
        output = io.StringIO()
        with (patch.object(DevelopmentOneShotCredential, "prompt_hidden", return_value=provider),
              patch.object(prod_prelive, "_current_source_commit", return_value=BASELINE_COMMIT),
              redirect_stdout(output)):
            self.assertEqual(prod_prelive.main(
                ["--expected-source-commit", BASELINE_COMMIT]), 0)
        self.assertNotIn(SECRET, output.getvalue())
        with self.assertRaises(ValidationError):
            provider.credential()
        for option in ("--live", "--yes", "--force"):
            with self.subTest(option=option), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                prod_prelive.main([option])

    def test_source_endpoint_and_model_bindings_fail_closed(self):
        with self.assertRaises(ValidationError):
            checked_preflight(self.provider(), "0" * 40)
        with self.assertRaises(ValidationError):
            run_preflight(self.provider(), {"expected_commit": BASELINE_COMMIT})
        with self.assertRaises(ValidationError):
            OwnerReviewedSource.from_owner_authorization("HEAD")
        for name, value in (("TRUSTED_ENDPOINT", "https://example.invalid/v1/responses"),
                            ("TRUSTED_MODEL", "caller-model"),
                            ("PROVIDER_MODEL", "caller-provider-model")):
            with self.subTest(name=name), patch.object(prod_prelive, name, value), self.assertRaises(ValidationError):
                checked_preflight(self.provider())

    def test_active_or_executable_contract_fails_closed(self):
        original = prod_prelive.load_contract()
        for field, value in (("status", "ACTIVE"), ("authority_mode", "EXECUTION")):
            changed = dict(original)
            changed[field] = value
            with self.subTest(field=field), patch.object(
                    prod_prelive, "load_contract", return_value=changed), self.assertRaises(ValidationError):
                checked_preflight(self.provider())
        changed = dict(original)
        changed["permissions"] = dict(original["permissions"], shell=True)
        with patch.object(prod_prelive, "load_contract", return_value=changed), self.assertRaises(ValidationError):
            checked_preflight(self.provider())

    def test_tool_request_retry_redirect_and_environment_policy_fail_closed(self):
        mutations = (("MAX_REQUESTS_PER_CYCLE", 2), ("MAX_RETRIES", 1),
                     ("HTTP_MAX_RETRIES", 1), ("ALLOW_REDIRECTS", True),
                     ("TRUST_ENVIRONMENT", True))
        for name, value in mutations:
            with self.subTest(name=name), patch.object(prod_prelive, name, value), self.assertRaises(ValidationError):
                checked_preflight(self.provider())
        original = prod_prelive.build_product_model_request

        def with_tool(task):
            request, raw = original(task)
            request["tools"] = [{"type": "shell"}]
            return request, raw

        with patch.object(prod_prelive, "build_product_model_request", side_effect=with_tool), self.assertRaises(ValidationError):
            checked_preflight(self.provider())

    def test_synthetic_task_is_deterministic_and_contains_no_customer_data(self):
        first = synthetic_first_live_task()
        self.assertEqual(first, synthetic_first_live_task())
        self.assertEqual(first["task_id"], "ATS-1201")
        self.assertEqual(first["task_class"], "PRODUCT_REQUIREMENT")
        self.assertEqual(len(first["input_references"]), 1)
        self.assertEqual(first["input_references"][0]["reference_type"], "FOUNDER_DIRECTION")

    def test_current_checkpoint_can_be_bound_without_embedding_its_hash(self):
        current = prod_prelive._current_source_commit()
        reviewed = OwnerReviewedSource.from_owner_authorization(current)
        result = run_preflight(self.provider(), reviewed)
        self.assertEqual(result["source_commit"], current)
        self.assertEqual(result["live_check_status"], "LIVE_CHECK_REQUIRED")


if __name__ == "__main__":
    unittest.main()
