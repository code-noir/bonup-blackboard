"""Founder-run, non-inference OpenAI model-access check for PROD-01."""
import argparse
from dataclasses import dataclass
import json
import sys
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

from .prod_openai_http import PROVIDER_MODEL
from .prod_prelive import (
    DevelopmentOneShotCredential, OwnerReviewedSource, _current_source_commit,
)
from .serialization import parse_json
from .types import ValidationError

MODEL_METADATA_ENDPOINT = "https://api.openai.com/v1/models/gpt-5.6-luna"
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 65536
MAX_REQUESTS = 1
MAX_RETRIES = 0
ALLOW_REDIRECTS = False
TRUST_ENVIRONMENT = False
_RESPONSE_CHUNK_BYTES = 8192


@dataclass(frozen=True)
class ProviderCheckResult:
    checkpoint: str
    authentication: str
    model: str
    model_access: str
    request_count: int
    inference_request_count: int = 0


class ProviderCheckError(ValidationError):
    """Bounded provider-check failure that contains no response body or credential."""


class OpenAIModelMetadataCheck:
    """Single-use GET of one fixed OpenAI model metadata endpoint."""

    def __init__(self, credential_provider):
        if type(credential_provider) is not DevelopmentOneShotCredential:
            raise ValidationError("Trusted one-shot development credential is required.")
        self.__credential_provider = credential_provider
        self.__endpoint = MODEL_METADATA_ENDPOINT
        self.__session_factory = requests.Session
        self.__used = False
        self.__test_only = False

    @classmethod
    def _for_loopback_tests(cls, endpoint, credential_provider, *, session_factory=None):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                or parsed.path != "/v1/models/gpt-5.6-luna"
                or parsed.query or parsed.fragment or parsed.username is not None
                or parsed.password is not None or parsed.port is None):
            raise ValidationError("Test provider endpoint must be the exact loopback model path.")
        checker = cls(credential_provider)
        checker.__endpoint = endpoint
        checker.__test_only = True
        if session_factory is not None:
            checker.__session_factory = session_factory
        return checker

    @property
    def test_only(self):
        return self.__test_only

    def check(self, checkpoint):
        if self.__used:
            raise ProviderCheckError("Provider metadata check is already consumed.")
        self.__used = True
        credential = self.__credential_provider.credential()
        headers = {"Authorization": "Bearer " + credential}
        try:
            with self.__session_factory() as session:
                session.trust_env = TRUST_ENVIRONMENT
                session.headers.clear()
                session.mount("https://", HTTPAdapter(max_retries=MAX_RETRIES))
                session.mount("http://", HTTPAdapter(max_retries=MAX_RETRIES))
                with session.get(
                        self.__endpoint, headers=headers, stream=True,
                        allow_redirects=ALLOW_REDIRECTS,
                        timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                        verify=True) as response:
                    if response.status_code == 401:
                        return ProviderCheckResult(
                            checkpoint, "FAIL", PROVIDER_MODEL, "UNKNOWN", 1)
                    if response.status_code in {403, 404}:
                        return ProviderCheckResult(
                            checkpoint, "PASS", PROVIDER_MODEL, "FAIL", 1)
                    if response.status_code != 200:
                        return ProviderCheckResult(
                            checkpoint, "UNKNOWN", PROVIDER_MODEL, "UNKNOWN", 1)
                    body = self._bounded_body(response)
        except (requests.RequestException, ProviderCheckError):
            return ProviderCheckResult(
                checkpoint, "UNKNOWN", PROVIDER_MODEL, "UNKNOWN", 1)
        finally:
            credential = None

        try:
            metadata = parse_json(body.decode("utf-8"))
        except (UnicodeError, ValidationError):
            return ProviderCheckResult(
                checkpoint, "PASS", PROVIDER_MODEL, "UNKNOWN", 1)
        if type(metadata) is dict and metadata.get("id") == PROVIDER_MODEL:
            return ProviderCheckResult(checkpoint, "PASS", PROVIDER_MODEL, "PASS", 1)
        return ProviderCheckResult(checkpoint, "PASS", PROVIDER_MODEL, "UNKNOWN", 1)

    @staticmethod
    def _bounded_body(response):
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                if int(declared) > MAX_RESPONSE_BYTES:
                    raise ProviderCheckError("Provider metadata response exceeded the byte limit.")
            except ValueError:
                raise ProviderCheckError("Provider metadata response length is invalid.") from None
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=_RESPONSE_CHUNK_BYTES):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ProviderCheckError("Provider metadata response exceeded the byte limit.")
            chunks.append(chunk)
        return b"".join(chunks)


def _interactive_terminal_available():
    return sys.stdin.isatty() and sys.stderr.isatty()


def _run_check(reviewed_source, tty_check, prompt_fn, checker_factory):
    if type(reviewed_source) is not OwnerReviewedSource:
        raise ValidationError("Trusted owner-reviewed source identity is required.")
    current = _current_source_commit()
    if current != reviewed_source.expected_commit:
        raise ValidationError("Provider check source identity is not approved.")
    if tty_check() is not True:
        raise ValidationError("An interactive terminal is required before credential acquisition.")
    provider = None
    try:
        provider = DevelopmentOneShotCredential.prompt_hidden(prompt_fn)
        checker = checker_factory(provider)
        return checker.check(current)
    finally:
        if provider is not None:
            provider.discard()


def run_provider_check(reviewed_source):
    """Production construction: fixed endpoint, hidden input, no injectable routing."""
    return _run_check(
        reviewed_source, _interactive_terminal_available, None,
        OpenAIModelMetadataCheck)


def _run_provider_check_for_tests(reviewed_source, tty_check, prompt_fn, checker_factory):
    """Explicit test seam; production CLI never calls this function."""
    return _run_check(reviewed_source, tty_check, prompt_fn, checker_factory)


def format_result(result):
    if type(result) is not ProviderCheckResult:
        raise ValidationError("Invalid provider-check result.")
    return "\n".join([
        "CHECKPOINT:", result.checkpoint,
        "AUTHENTICATION:", result.authentication,
        "MODEL:", result.model,
        "MODEL_ACCESS:", result.model_access,
        "REQUEST_COUNT:", str(result.request_count),
        "INFERENCE_REQUEST_COUNT:", str(result.inference_request_count),
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -B -m tools.agent_control.prod_provider_check",
        description="Founder-run one-shot OpenAI model metadata check; no inference.")
    parser.add_argument(
        "--expected-source-commit", required=True,
        help="Owner-reviewed checkpoint identity (40 lowercase hexadecimal characters).")
    args = parser.parse_args(argv)
    try:
        reviewed = OwnerReviewedSource.from_owner_authorization(
            args.expected_source_commit)
        print(format_result(run_provider_check(reviewed)))
        return 0
    except (ValidationError, OSError):
        print(json.dumps({
            "status": "BLOCKED",
            "authentication": "UNKNOWN",
            "model": PROVIDER_MODEL,
            "model_access": "UNKNOWN",
            "request_count": 0,
            "inference_request_count": 0,
        }, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
