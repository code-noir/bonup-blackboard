import json
import gzip
import io
import logging
import os
import requests
import threading
import time
import unittest
import zlib
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from prod_cycle_fixtures import DeterministicProductFake
from test_prod_cycle import synthetic_task
from tools.agent_control.prod_model_transport import (
    MAX_RESPONSE_BYTES, PROVIDER_AUTH_ERROR, PROVIDER_CONNECTION_ERROR,
    PROVIDER_NOT_FOUND, PROVIDER_PERMISSION_ERROR, PROVIDER_RATE_LIMIT,
    PROVIDER_REQUEST_REJECTED, PROVIDER_RESPONSE_TOO_LARGE, PROVIDER_SERVER_ERROR,
    PROVIDER_TIMEOUT, TRUSTED_ENDPOINT, TRUSTED_MODEL, ProductModelFailure,
    build_product_model_request, project_product_context, run_product_model_cycle,
)
from tools.agent_control.prod_cycle import run_synthetic_product_cycle
from tools.agent_control.prod_openai_http import (
    PROVIDER_MODEL, InjectedOpenAICredentialProvider, OpenAIResponsesHTTPAdapter,
    project_openai_responses_request,
)
from tools.agent_control.prod_response_capture import (
    CAPTURE_DIRECTORY, PrivateResponseCapture, PrivateResponseCaptureError,
    cleanup_private_response_captures,
)
from tools.agent_control.serialization import canonical_json, digest
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
        encoding = behavior.get("content_encoding")
        if encoding == "gzip":
            payload = gzip.compress(payload)
        elif encoding == "deflate":
            payload = zlib.compress(payload)
        self.send_response(status)
        if "location" in behavior:
            self.send_header("Location", behavior["location"])
        if behavior.get("content_type", "application/json") is not None:
            self.send_header("Content-Type", behavior.get("content_type", "application/json"))
        if encoding is not None:
            self.send_header("Content-Encoding", encoding)
        declared_length = behavior.get("declared_length", len(payload))
        if behavior.get("chunked"):
            self.send_header("Transfer-Encoding", "chunked")
        else:
            self.send_header("Content-Length", str(declared_length))
        if behavior.get("close"):
            self.send_header("Connection", "close")
        self.end_headers()
        try:
            if behavior.get("chunked"):
                chunk_size = behavior.get("chunk_size", 7)
                for offset in range(0, len(payload), chunk_size):
                    chunk = payload[offset:offset + chunk_size]
                    self.wfile.write(('%x\r\n' % len(chunk)).encode() + chunk + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
            else:
                self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass
        if behavior.get("close"):
            self.close_connection = True


class _ConnectionFailureSession:
    calls = 0

    def __init__(self):
        self.headers = {}
        self.trust_env = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def mount(self, *args, **kwargs):
        pass

    def post(self, *args, **kwargs):
        type(self).calls += 1
        raise requests.ConnectionError("synthetic connection failure")


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
    def run_local(self, behavior, *, timeouts=None, candidate_task=None,
                  session_factory=None):
        with fake_server(behavior) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                endpoint, provider, timeouts=timeouts, session_factory=session_factory)
            result = run_product_model_cycle(candidate_task or synthetic_task(), adapter)
            return result, server.calls, adapter

    def test_one_fixed_post_with_provider_model_zero_tools_and_structured_output(self):
        result, calls, adapter = self.run_local({"body": response_bytes()})
        self.assertTrue(adapter.test_only)
        self.assertIsNone(adapter.private_response_capture_result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["path"], "/v1/responses")
        request = json.loads(calls[0]["body"])
        self.assertEqual(request["model"], PROVIDER_MODEL)
        self.assertEqual(request["tools"], [])
        self.assertEqual(set(request), {"model", "input", "tools", "text", "store"})
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer " + SECRET)
        self.assertEqual(result.proposal["knowledge_state"], "WORKING")

    def test_provider_metadata_uses_ordinary_json_but_proposal_uses_strict_json(self):
        sentinel = "synthetic-provider-metadata-sentinel"
        envelope = json.loads(response_bytes().decode())
        envelope["provider_metadata"] = {
            "fractional": 1.25,
            "nonfinite": float("nan"),
            "sentinel": sentinel,
        }
        provider_raw = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":"), allow_nan=True,
        ).encode()
        result, calls, _ = self.run_local({"body": provider_raw})
        self.assertEqual(result.proposal["knowledge_state"], "WORKING")
        self.assertEqual(len(calls), 1)

        invalid = proposal({"canonical_violation": 1.25})
        invalid_envelope = json.loads(response_bytes().decode())
        invalid_envelope["output"][0]["content"][0]["text"] = json.dumps(
            invalid, ensure_ascii=False, separators=(",", ":"), allow_nan=True,
        )
        invalid_raw = json.dumps(
            invalid_envelope, ensure_ascii=False, separators=(",", ":"), allow_nan=True,
        ).encode()
        with fake_server({"body": invalid_raw}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
            with self.assertRaises(ProductModelFailure) as caught:
                run_product_model_cycle(synthetic_task(), adapter)
        self.assertEqual(
            caught.exception.audit_metadata["failure_reason"],
            "STRUCTURED_JSON_INVALID",
        )
        self.assertEqual(len(server.calls), 1)
        self.assertNotIn(sentinel, json.dumps(caught.exception.audit_metadata))

    def test_response_bytes_variants_use_exact_http_adapter_path(self):
        for label, behavior in (
                ("plain", {"body": response_bytes()}),
                ("whitespace", {"body": b" \n" + response_bytes() + b"\t\n"}),
                ("utf8", {"body": response_bytes(proposal({"title": "Caf\u00e9"}))}),
                ("gzip", {"body": response_bytes(), "content_encoding": "gzip"}),
                ("deflate", {"body": response_bytes(), "content_encoding": "deflate"}),
                ("chunked", {"body": response_bytes(), "chunked": True, "chunk_size": 5}),
                ("gzip_chunked", {"body": response_bytes(), "content_encoding": "gzip",
                                  "chunked": True, "chunk_size": 3}),
        ):
            with self.subTest(variant=label):
                result, calls, _ = self.run_local(behavior)
                self.assertEqual(result.proposal["knowledge_state"], "WORKING")
                self.assertEqual(len(calls), 1)

    def test_response_metadata_is_bounded_and_decode_stage_is_safe(self):
        with fake_server({"body": b"not-json"}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
            with self.assertRaises(ProductModelFailure) as caught:
                run_product_model_cycle(synthetic_task(), adapter)
        metadata = caught.exception.audit_metadata
        structure = metadata["provider_structure"]
        http = structure["http_response"]
        self.assertEqual(metadata["failure_reason"], "PROVIDER_ENVELOPE_INVALID")
        self.assertEqual(structure["reason"], "RESPONSE_JSON_INVALID")
        self.assertEqual(http["http_status"], 200)
        self.assertEqual(http["content_type"], "APPLICATION_JSON")
        self.assertEqual(http["content_encoding"], "MISSING")
        self.assertEqual(http["body_bytes"], len(b"not-json"))
        self.assertFalse(http["body_empty"])
        self.assertTrue(http["content_length_present"])
        self.assertEqual(http["declared_content_length"], len(b"not-json"))
        self.assertTrue(http["declared_length_matches"])
        self.assertTrue(http["utf8_decode_success"])
        self.assertFalse(http["json_decode_success"])
        self.assertEqual(len(server.calls), 1)
        self.assertNotIn("not-json", json.dumps(metadata))

    def test_gzip_json_decode_diagnostic_is_bounded(self):
        raw = b'{"status":"completed"'
        with fake_server({"body": raw, "content_encoding": "gzip"}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
            with self.assertRaises(ProductModelFailure) as caught:
                run_product_model_cycle(synthetic_task(), adapter)
        structure = caught.exception.audit_metadata["provider_structure"]
        self.assertEqual(structure["reason"], "RESPONSE_JSON_INVALID")
        self.assertEqual(structure["json_error"]["category"], "EXPECTING_COMMA")
        self.assertEqual(structure["http_response"]["content_encoding"], "GZIP")
        self.assertFalse(structure["http_response"]["json_decode_success"])
        self.assertNotIn(raw.decode(), json.dumps(caught.exception.audit_metadata))
        self.assertEqual(len(server.calls), 1)

    def test_private_capture_stores_only_decompressed_response_once(self):
        raw = b'{"status":"completed"'
        capture = PrivateResponseCapture()
        try:
            with fake_server({"body": raw, "content_encoding": "gzip"}) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                    endpoint, provider, private_response_capture=capture)
                with self.assertRaises(ProductModelFailure):
                    run_product_model_cycle(synthetic_task(), adapter)
            result = adapter.private_response_capture_result
            self.assertTrue(result["created"])
            self.assertEqual(result["bytes"], len(raw))
            self.assertTrue(result["path"].startswith(CAPTURE_DIRECTORY + os.sep))
            file_stat = os.stat(result["path"])
            self.assertEqual(file_stat.st_mode & 0o777, 0o600)
            with open(result["path"], "rb") as captured:
                captured_body = captured.read()
            self.assertEqual(captured_body, raw)
            self.assertNotIn(SECRET.encode(), captured_body)
            self.assertNotEqual(captured_body, server.calls[0]["body"])
            self.assertEqual(len(server.calls), 1)
            with self.assertRaises(ProductModelFailure):
                run_product_model_cycle(synthetic_task(), adapter)
            self.assertEqual(len(server.calls), 1)
        finally:
            cleanup_private_response_captures()

        success_capture = PrivateResponseCapture()
        try:
            with fake_server({"body": response_bytes()}) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                    endpoint, provider, private_response_capture=success_capture)
                result = run_product_model_cycle(synthetic_task(), adapter)
                self.assertEqual(result.proposal["knowledge_state"], "WORKING")
                self.assertEqual(len(server.calls), 1)
                capture_result = adapter.private_response_capture_result
                self.assertTrue(capture_result["created"])
                with open(capture_result["path"], "rb") as captured:
                    self.assertEqual(captured.read(), response_bytes())
        finally:
            cleanup_private_response_captures()

    def test_private_capture_is_bounded_and_does_not_follow_symlink(self):
        capture = PrivateResponseCapture()
        try:
            with self.assertRaises(PrivateResponseCaptureError):
                capture.capture(b"x" * (MAX_RESPONSE_BYTES + 1))
            self.assertFalse(capture.result["created"])

            os.makedirs(CAPTURE_DIRECTORY, mode=0o700, exist_ok=True)
            filename = "response-" + ("a" * 32) + ".bin"
            path = os.path.join(CAPTURE_DIRECTORY, filename)
            os.symlink("/etc/passwd", path)
            with patch("tools.agent_control.prod_response_capture.uuid.uuid4") as uuid4:
                uuid4.return_value.hex = "a" * 32
                with self.assertRaises(PrivateResponseCaptureError):
                    PrivateResponseCapture().capture(b"private")
            self.assertFalse(os.path.lexists(path))
        finally:
            cleanup_private_response_captures()

    def test_empty_truncated_and_oversized_decoded_bodies_fail_closed(self):
        cases = (
            ({"body": b""}, "EMPTY_BODY"),
            ({"body": b"\xff"}, "INVALID_UTF8"),
            ({"body": b'{"status":"completed"'}, "RESPONSE_JSON_INVALID"),
            ({"body": b"\xef\xbb\xbf" + response_bytes()}, "RESPONSE_JSON_INVALID"),
            ({"body": b"{}", "declared_length": 5, "close": True},
             "PROVIDER_RESPONSE_TRUNCATED"),
            ({"body": b"x" * (MAX_RESPONSE_BYTES + 1),
              "content_encoding": "gzip"}, "PROVIDER_RESPONSE_TOO_LARGE"),
        )
        for behavior, reason in cases:
            with self.subTest(reason=reason), fake_server(behavior) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
                with self.assertRaises(ProductModelFailure) as caught:
                    run_product_model_cycle(synthetic_task(), adapter)
                self.assertEqual(len(server.calls), 1)
                expected_classification = (reason if reason.startswith("PROVIDER_")
                                            else "PROVIDER_ENVELOPE_INVALID")
                self.assertEqual(caught.exception.audit_metadata["failure_reason"],
                                 expected_classification)
                if reason in {"RESPONSE_JSON_INVALID", "INVALID_UTF8"}:
                    self.assertEqual(caught.exception.audit_metadata["provider_structure"]["reason"], reason)

    def test_unexpected_media_type_and_encoding_are_bounded(self):
        cases = (
            ({"body": response_bytes(), "content_type": "text/event-stream"},
             "PROVIDER_CONTENT_TYPE_INVALID"),
            ({"body": response_bytes(), "content_type": None},
             "PROVIDER_CONTENT_TYPE_INVALID"),
            ({"body": response_bytes(), "content_encoding": "br"},
             "PROVIDER_ENCODING_UNSUPPORTED"),
        )
        for behavior, reason in cases:
            with self.subTest(reason=reason), fake_server(behavior) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
                with self.assertRaises(ProductModelFailure) as caught:
                    run_product_model_cycle(synthetic_task(), adapter)
                self.assertEqual(len(server.calls), 1)
                self.assertEqual(caught.exception.audit_metadata["failure_reason"], reason)
                http = caught.exception.audit_metadata["provider_structure"]["http_response"]
                self.assertIn(http["content_type"], {"APPLICATION_JSON", "OTHER", "MISSING"})
                self.assertIn(http["content_encoding"], {"MISSING", "IDENTITY", "GZIP", "DEFLATE", "OTHER"})
                self.assertNotIn("event-stream", json.dumps(caught.exception.audit_metadata))
                self.assertNotIn("br", json.dumps(caught.exception.audit_metadata))

    def test_request_is_ordinary_json_not_sse_and_stays_one_shot(self):
        observed = []

        class ObservedSession(requests.Session):
            def post(self, *args, **kwargs):
                observed.append(dict(kwargs))
                return super().post(*args, **kwargs)

        with fake_server({"body": response_bytes()}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                endpoint, provider, session_factory=ObservedSession)
            result = run_product_model_cycle(synthetic_task(), adapter)
        self.assertEqual(result.proposal["knowledge_state"], "WORKING")
        self.assertEqual(len(server.calls), 1)
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0]["stream"])
        self.assertFalse(observed[0]["allow_redirects"])
        self.assertEqual(server.calls[0]["headers"]["Accept"], "application/json")
        self.assertNotEqual(server.calls[0]["headers"].get("Accept"), "text/event-stream")

    def test_provider_wire_projection_is_fixed_and_deterministic(self):
        internal, _ = build_product_model_request(synthetic_task())
        first = project_openai_responses_request(internal)
        second = project_openai_responses_request(internal)
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(digest(first),
                         "4bd64360e927453e82875da68beeb4dfa4bf04cb634c3d93c6070db2dec0bb36")
        self.assertEqual(first["model"], PROVIDER_MODEL)
        self.assertEqual(first["tools"], [])
        self.assertEqual(first["text"]["format"]["type"], "json_schema")
        self.assertTrue(first["text"]["format"]["strict"])
        self.assertNotIn(SECRET, canonical_json(first))
        self.assertNotIn(TRUSTED_ENDPOINT, canonical_json(first))

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
        cases = (
            (302, PROVIDER_REQUEST_REJECTED),
            (400, PROVIDER_REQUEST_REJECTED),
            (401, PROVIDER_AUTH_ERROR),
            (403, PROVIDER_PERMISSION_ERROR),
            (404, PROVIDER_NOT_FOUND),
            (429, PROVIDER_RATE_LIMIT),
            (500, PROVIDER_SERVER_ERROR),
        )
        for status, reason in cases:
            with self.subTest(status=status), fake_server({
                    "status": status, "location": "http://127.0.0.1:1/denied", "body": b"secret provider body"
                    }) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
                with self.assertRaises(ProductModelFailure) as caught:
                    run_product_model_cycle(synthetic_task(), adapter)
                self.assertEqual(len(server.calls), 1)
                self.assertEqual(caught.exception.audit_metadata["failure_reason"], reason)
                self.assertEqual(caught.exception.audit_metadata["provider_structure"]["http_response"]["http_status"], status)
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
            self.assertEqual(caught.exception.audit_metadata["failure_reason"], PROVIDER_TIMEOUT)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_connection_failure_is_bounded_and_does_not_retry(self):
        _ConnectionFailureSession.calls = 0
        with fake_server({"body": response_bytes()}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(
                endpoint, provider, session_factory=_ConnectionFailureSession)
            with self.assertRaises(ProductModelFailure) as caught:
                run_product_model_cycle(synthetic_task(), adapter)
        self.assertEqual(_ConnectionFailureSession.calls, 1)
        self.assertEqual(server.calls, [])
        self.assertEqual(caught.exception.audit_metadata["failure_reason"],
                         PROVIDER_CONNECTION_ERROR)
        self.assertNotIn(SECRET, str(caught.exception))

    def test_oversized_response_fails_closed(self):
        with fake_server({"body": b"x" * (MAX_RESPONSE_BYTES + 1)}) as (server, endpoint):
            provider = InjectedOpenAICredentialProvider(SECRET)
            adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
            with self.assertRaises(ProductModelFailure) as caught:
                run_product_model_cycle(synthetic_task(), adapter)
            self.assertEqual(len(server.calls), 1)
            self.assertEqual(caught.exception.audit_metadata["failure_reason"],
                             PROVIDER_RESPONSE_TOO_LARGE)

    def test_malformed_json_and_proposal_do_not_retry(self):
        cases = (
            (b"not-json", "PROVIDER_ENVELOPE_INVALID"),
            (response_bytes(proposal({"approved": True})), "PROPOSAL_SCHEMA_MISMATCH"),
        )
        for body, reason in cases:
            with self.subTest(size=len(body)), fake_server({"body": body}) as (server, endpoint):
                provider = InjectedOpenAICredentialProvider(SECRET)
                adapter = OpenAIResponsesHTTPAdapter._for_loopback_tests(endpoint, provider)
                with self.assertRaises(ProductModelFailure) as caught:
                    run_product_model_cycle(synthetic_task(), adapter)
                self.assertEqual(len(server.calls), 1)
                self.assertEqual(caught.exception.audit_metadata["failure_reason"], reason)

    def test_caller_cannot_override_production_endpoint_or_model(self):
        provider = InjectedOpenAICredentialProvider(SECRET)
        adapter = OpenAIResponsesHTTPAdapter(provider)
        _, request = build_product_model_request(synthetic_task())
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
