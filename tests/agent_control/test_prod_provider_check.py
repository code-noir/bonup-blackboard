import io
import logging
import os
from pathlib import Path
import threading
import unittest
from contextlib import contextmanager, redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from tools.agent_control import prod_provider_check
from tools.agent_control.prod_prelive import OwnerReviewedSource
from tools.agent_control.prod_provider_check import (
    ALLOW_REDIRECTS, MAX_REQUESTS, MAX_RESPONSE_BYTES, MAX_RETRIES,
    MODEL_METADATA_ENDPOINT, TRUST_ENVIRONMENT, OpenAIModelMetadataCheck,
    ProviderCheckError, _run_provider_check_for_tests, format_result,
)
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import ValidationError

CHECKPOINT = "5964b6485d6f825ac872736a5f211bb586173b9c"
SECRET = "synthetic-provider-check-secret"


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.server.calls.append({"path": self.path, "headers": dict(self.headers)})
        payload = self.server.payload
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@contextmanager
def fake_server(status, payload=b"{}"):
    server = _Server(("127.0.0.1", 0), _Handler)
    server.status = status
    server.payload = payload
    server.calls = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}/v1/models/gpt-5.6-luna"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def reviewed():
    return OwnerReviewedSource.from_owner_authorization(CHECKPOINT)


class ProductProviderCheckTests(unittest.TestCase):
    def run_local(self, status=200, payload=None):
        payload = payload if payload is not None else canonical_json({
            "id": "gpt-5.6-luna", "object": "model"}).encode()
        prompts = []
        with fake_server(status, payload) as (server, endpoint), patch.object(
                prod_provider_check, "_current_source_commit", return_value=CHECKPOINT):
            def factory(provider):
                return OpenAIModelMetadataCheck._for_loopback_tests(endpoint, provider)

            result = _run_provider_check_for_tests(
                reviewed(), lambda: True,
                lambda prompt: prompts.append(prompt) or SECRET, factory)
        return result, server.calls, prompts

    def test_non_tty_and_stale_source_stop_before_credential(self):
        prompts = []
        factory = lambda provider: self.fail("checker constructed")
        with patch.object(prod_provider_check, "_current_source_commit", return_value=CHECKPOINT):
            with self.assertRaises(ValidationError):
                _run_provider_check_for_tests(
                    reviewed(), lambda: False,
                    lambda prompt: prompts.append(prompt) or SECRET, factory)
        with patch.object(prod_provider_check, "_current_source_commit", return_value="0" * 40):
            with self.assertRaises(ValidationError):
                _run_provider_check_for_tests(
                    reviewed(), lambda: True,
                    lambda prompt: prompts.append(prompt) or SECRET, factory)
        self.assertEqual(prompts, [])

    def test_exactly_one_fixed_metadata_request_and_safe_success(self):
        result, calls, prompts = self.run_local()
        self.assertEqual(len(prompts), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["path"], "/v1/models/gpt-5.6-luna")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer " + SECRET)
        self.assertEqual(result.authentication, "PASS")
        self.assertEqual(result.model_access, "PASS")
        self.assertEqual(result.request_count, 1)
        self.assertEqual(result.inference_request_count, 0)
        self.assertNotIn(SECRET, format_result(result))

    def test_network_policy_is_fixed_and_non_inference(self):
        self.assertEqual(MODEL_METADATA_ENDPOINT,
                         "https://api.openai.com/v1/models/gpt-5.6-luna")
        self.assertEqual(MAX_REQUESTS, 1)
        self.assertEqual(MAX_RETRIES, 0)
        self.assertIs(ALLOW_REDIRECTS, False)
        self.assertIs(TRUST_ENVIRONMENT, False)

    def test_auth_model_and_ambiguous_classification(self):
        for status, authentication, access in (
                (401, "FAIL", "UNKNOWN"),
                (404, "PASS", "FAIL"),
                (500, "UNKNOWN", "UNKNOWN")):
            with self.subTest(status=status):
                result, calls, _ = self.run_local(status=status)
                self.assertEqual((result.authentication, result.model_access),
                                 (authentication, access))
                self.assertEqual(len(calls), 1)

    def test_success_with_wrong_or_malformed_metadata_is_inconclusive(self):
        for payload in (b"not-json", b'{"id":"another-model"}'):
            result, calls, _ = self.run_local(payload=payload)
            self.assertEqual(result.authentication, "PASS")
            self.assertEqual(result.model_access, "UNKNOWN")
            self.assertEqual(len(calls), 1)

    def test_credential_is_one_shot_and_absent_from_output_errors_and_logs(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            result, _, _ = self.run_local()
        finally:
            root.removeHandler(handler)
        safe = format_result(result) + stream.getvalue()
        self.assertNotIn(SECRET, safe)
        with fake_server(200, b'{"id":"gpt-5.6-luna"}') as (_, endpoint):
            provider = prod_provider_check.DevelopmentOneShotCredential._for_tests(SECRET)
            checker = OpenAIModelMetadataCheck._for_loopback_tests(endpoint, provider)
            checker.check(CHECKPOINT)
            with self.assertRaises(ProviderCheckError) as caught:
                checker.check(CHECKPOINT)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_environment_and_cli_cannot_supply_credential(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-secret"}):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                prod_provider_check.main([
                    "--expected-source-commit", CHECKPOINT, "--api-key", SECRET])
        self.assertNotIn(SECRET, MODEL_METADATA_ENDPOINT)

    def test_response_bound_and_test_endpoint_restriction(self):
        with fake_server(200, b"x" * (MAX_RESPONSE_BYTES + 1)) as (_, endpoint):
            provider = prod_provider_check.DevelopmentOneShotCredential._for_tests(SECRET)
            checker = OpenAIModelMetadataCheck._for_loopback_tests(endpoint, provider)
            result = checker.check(CHECKPOINT)
            self.assertEqual((result.authentication, result.model_access, result.request_count),
                             ("UNKNOWN", "UNKNOWN", 1))
        provider = prod_provider_check.DevelopmentOneShotCredential._for_tests(SECRET)
        for endpoint in (MODEL_METADATA_ENDPOINT,
                         "http://localhost:1234/v1/models/gpt-5.6-luna",
                         "http://127.0.0.1:1234/v1/responses"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValidationError):
                OpenAIModelMetadataCheck._for_loopback_tests(endpoint, provider)

    def test_production_source_has_no_inference_or_credential_sources(self):
        source = Path(prod_provider_check.__file__).read_text(encoding="utf-8")
        for forbidden in ("/v1/responses", "chat/completions", "os.environ",
                          "getenv", ".env", "open(", "--api-key",
                          "run_product_model_cycle"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
