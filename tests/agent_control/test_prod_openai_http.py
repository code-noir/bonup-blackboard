import json
import io
import logging
import os
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from prod_cycle_fixtures import DeterministicProductFake
from test_prod_cycle import synthetic_task
from tools.agent_control.prod_model_transport import (
    MAX_RESPONSE_BYTES, TRUSTED_ENDPOINT, TRUSTED_MODEL, ProductModelFailure,
    project_product_context, run_product_model_cycle,
)
from tools.agent_control.prod_cycle import run_synthetic_product_cycle
from tools.agent_control.prod_openai_http import (
    PROVIDER_MODEL, InjectedOpenAICredentialProvider, OpenAIResponsesHTTPAdapter,
)
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import ValidationError

SECRET = "synthetic-openai-secret-marker"


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.calls.append({"path": self.path, "headers": dict(self.headers), "body": body})
        behavior = self.server.behavior
        if behavior.get("delay"):
            time.sleep(behavior["delay"])
        status = behavior.get("status", 200)
        payload = behavior.get("body", b"")
        self.send_response(status)
        if "location" in behavior:
            self.send_header("Location", behavior["location"])
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass


@contextmanager
def fake_server(behavior):
    server = _Server(("127.0.0.1", 0), _Handler)
    server.behavior = behavior
    server.calls = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}/v1/responses"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def proposal(changes=None):
    value = DeterministicProductFake().propose(synthetic_task())
    value.update(changes or {})
    return value


def response_bytes(candidate=None):
    return canonical_json({
        "id": "resp_synthetic",
        "status": "completed",
        "output": [{
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
    }).encode()


class ProductOpenAIHTTPTests(unittest.TestCase):
    def run_local(self, behavior, *, timeouts=None, candidate_task=None):
        with fake_server(behavior) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                endpoint, provider, timeouts=timeouts)
            result = run_product_model_cycle(candidate_task or synthetic_task(), adapter)
            return result, server.calls, adapter

    def test_one_fixed_post_with_provider_model_zero_tools_and_structured_output(self):
        result, calls, adapter = self.run_local({"body": response_bytes()})
        self.assertTrue(adapter.test_only)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["path"], "/v1/responses")
        request = json.loads(calls[0]["body"])
        self.assertEqual(request["model"], PROVIDER_MODEL)
        self.assertEqual(request["tools"], [])
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer " + SECRET)
        self.assertEqual(result.proposal["knowledge_state"], "WORKING")

    def test_secret_exists_only_at_http_authorization_boundary(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            result, calls, _ = self.run_local({"body": response_bytes()})
        finally:
            root.removeHandler(handler)
        task_document = run_synthetic_product_cycle(
            synthetic_task(), DeterministicProductFake()).task_document_bytes.decode()
        values = [
            canonical_json(synthetic_task()), canonical_json(project_product_context(synthetic_task())),
            canonical_json(result.proposal), result.proposal_digest,
            canonical_json(result.audit_metadata), stream.getvalue(), calls[0]["body"].decode(),
            task_document,
        ]
        self.assertTrue(all(SECRET not in value for value in values))
        self.assertIn(SECRET, calls[0]["headers"]["Authorization"])

    def test_environment_proxy_and_netrc_are_not_inherited(self):
        observed = []
        import requests

        class ObservedSession(requests.Session):
            def send(self, request, **kwargs):
                observed.append(self.trust_env)
                return super().send(request, **kwargs)

        with fake_server({"body": response_bytes()}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                endpoint, provider, session_factory=ObservedSession)
            with patch.dict(os.environ, {
                    "HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1",
                    "ALL_PROXY": "http://127.0.0.1:1", "NO_PROXY": ""}):
                run_product_model_cycle(synthetic_task(), adapter)
        self.assertEqual(observed, [False])
        self.assertEqual(len(server.calls), 1)

    def test_redirect_rate_limit_and_server_error_do_not_retry(self):
        for status in (302, 429, 500):
            with self.subTest(status=status), fake_server({
                    "status": status, "location": "http://127.0.0.1:1/denied", "body": b"secret provider body"
                    }) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
                with self.assertRaises(ProductModelFailure) as caught:
                    run_product_model_cycle(synthetic_task(), adapter)
                self.assertEqual(len(server.calls), 1)
                self.assertNotIn(SECRET, str(caught.exception))
                self.assertNotIn("provider body", str(caught.exception))

    def test_timeout_does_not_retry(self):
        with fake_server({"delay": 0.2, "body": response_bytes()}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                endpoint, provider, timeouts=(0.05, 0.05))
            with self.assertRaises(ProductModelFailure) as caught:
                run_product_model_cycle(synthetic_task(), adapter)
            self.assertEqual(len(server.calls), 1)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_oversized_response_fails_closed(self):
        with fake_server({"body": b"x" * (MAX_RESPONSE_BYTES + 1)}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
            with self.assertRaises(ProductModelFailure):
                run_product_model_cycle(synthetic_task(), adapter)
            self.assertEqual(len(server.calls), 1)

    def test_malformed_json_and_proposal_do_not_retry(self):
        cases = (b"not-json", response_bytes(proposal({"approved": True})))
        for body in cases:
            with self.subTest(size=len(body)), fake_server({"body": body}) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
                with self.assertRaises(ProductModelFailure):
                    run_product_model_cycle(synthetic_task(), adapter)
                self.assertEqual(len(server.calls), 1)

    def test_caller_cannot_override_production_endpoint_or_model(self):
        provider = InjectedOpenAICredentialProvider(SECRET)
        adapter = OpenAIResponsesHTTPAdapter(provider)
        request = canonical_json({"model": TRUSTED_MODEL, "tools": [], "store": False,
                                  "text": {"format": {"type": "json_schema", "strict": True}}}).encode()
        for changes in ({"endpoint": "http://127.0.0.1:1/v1/responses"}, {"model": PROVIDER_MODEL}):
            kwargs = {"endpoint": TRUSTED_ENDPOINT, "model": TRUSTED_MODEL, "request": request,
                      "credential": None, "timeout_seconds": 30,
                      "allow_redirects": False, "trust_environment": False}
            kwargs.update(changes)
            with self.assertRaises(ValidationError):
                adapter.send(**kwargs)
        for endpoint in (TRUSTED_ENDPOINT, "http://localhost:1234/v1/responses",
                         "http://127.0.0.1:1234/other"):
            with self.assertRaises(ValidationError):
                OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)


if __name__ == "__main__":
    unittest.main()
