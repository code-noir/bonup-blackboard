"""Hardened OpenAI HTTP transport for PROD-01; no live construction side effects."""
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

from .prod_model_transport import (
    ALLOW_REDIRECTS, MAX_REQUEST_BYTES, MAX_REQUESTS_PER_CYCLE, MAX_RESPONSE_BYTES,
    MAX_RETRIES, PRODUCT_PROPOSAL_SCHEMA_DIGEST, PROVIDER_AUTH_ERROR,
    PROVIDER_CONNECTION_ERROR, PROVIDER_ERROR, PROVIDER_NOT_FOUND,
    PROVIDER_PERMISSION_ERROR, PROVIDER_RATE_LIMIT, PROVIDER_REQUEST_REJECTED,
    PROVIDER_RESPONSE_TOO_LARGE, PROVIDER_SERVER_ERROR, PROVIDER_TIMEOUT,
    PROVIDER_CONTENT_TYPE_INVALID, PROVIDER_ENCODING_UNSUPPORTED,
    PROVIDER_RESPONSE_TRUNCATED,
    SAFE_TRANSPORT_FAILURE_REASONS, TIMEOUT_SECONDS, TRUSTED_ENDPOINT, TRUSTED_MODEL,
    TRUST_ENVIRONMENT, validate_provider_schema_subset,
)
from .serialization import canonical_json, digest, parse_json
from .types import ValidationError

PROVIDER = "OpenAI"
PROVIDER_MODEL = "gpt-5.6-luna"
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = TIMEOUT_SECONDS
HTTP_MAX_RETRIES = 0
_RESPONSE_CHUNK_BYTES = 8192


def project_openai_responses_request(request):
    """Translate the closed internal PROD-01 contract into one OpenAI wire body."""
    if type(request) is not dict or set(request) != {
            "contract_version", "agent_id", "logical_model", "context", "tools",
            "output_contract", "request_policy"}:
        raise OpenAIHTTPError("Malformed internal PROD-01 request contract.")
    output = request["output_contract"]
    policy = request["request_policy"]
    if (request["contract_version"] != 1 or request["agent_id"] != "PROD-01"
            or request["logical_model"] != TRUSTED_MODEL or request["tools"] != []
            or type(request["context"]) is not dict
            or type(output) is not dict or set(output) != {
                "type", "encoding", "name", "strict", "schema", "schema_digest"}
            or output["type"] != "PRODUCT_REQUIREMENT_PROPOSAL"
            or output["encoding"] != "STRICT_JSON_SCHEMA"
            or output["name"] != "product_requirement_proposal"
            or output["strict"] is not True
            or output["schema_digest"] != PRODUCT_PROPOSAL_SCHEMA_DIGEST
            or digest(output["schema"]) != PRODUCT_PROPOSAL_SCHEMA_DIGEST
            or policy != {"max_requests": MAX_REQUESTS_PER_CYCLE,
                          "max_retries": MAX_RETRIES}):
        raise OpenAIHTTPError("Internal PROD-01 request contract mismatch.")
    validate_provider_schema_subset(output["schema"])
    return {
        "model": PROVIDER_MODEL,
        "input": canonical_json(request["context"]),
        "tools": [],
        "text": {"format": {
            "type": "json_schema",
            "name": output["name"],
            "strict": True,
            "schema": output["schema"],
        }},
        "store": False,
    }


class OpenAIHTTPError(ValidationError):
    """Bounded transport failure. Messages never contain provider bodies or credentials."""

    def __init__(self, message, *, failure_reason=PROVIDER_ERROR, response_metadata=None):
        super().__init__(message)
        self.failure_reason = (
            failure_reason if type(failure_reason) is str
            and failure_reason in SAFE_TRANSPORT_FAILURE_REASONS else PROVIDER_ERROR)
        self.response_metadata = response_metadata


class InjectedOpenAICredentialProvider:
    """Trusted composition supplies the secret; tasks and environment never do."""

    def __init__(self, credential):
        if (type(credential) is not str or not credential or len(credential) > 4096
                or "\r" in credential or "\n" in credential):
            raise ValidationError("Invalid trusted OpenAI credential.")
        self.__credential = credential

    def credential(self):
        return self.__credential


class OpenAIResponsesHTTPAdapter:
    """One POST per call to a fixed provider route; retry and redirect free."""

    credential_owned = True

    def __init__(self, credential_provider):
        if not callable(getattr(credential_provider, "credential", None)):
            raise ValidationError("Trusted OpenAI credential provider is required.")
        self.__credential_provider = credential_provider
        self.__endpoint = TRUSTED_ENDPOINT
        self.__timeouts = (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)
        self.__session_factory = requests.Session
        self.__test_only = False
        self.__response_metadata = None

    @classmethod
    def _for_loopback_tests(cls, endpoint, credential_provider, *, timeouts=None,
                            session_factory=None):
        """Test-only seam: accepts an explicit numeric loopback HTTP endpoint."""
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                or parsed.path != "/v1/responses" or parsed.query or parsed.fragment
                or parsed.username is not None or parsed.password is not None
                or parsed.port is None):
            raise ValidationError("Test OpenAI endpoint must be an explicit loopback Responses path.")
        adapter = cls(credential_provider)
        adapter.__endpoint = endpoint
        adapter.__test_only = True
        if timeouts is not None:
            if (type(timeouts) is not tuple or len(timeouts) != 2
                    or any(type(value) not in (int, float) or value <= 0 or value > 30
                           for value in timeouts)):
                raise ValidationError("Invalid bounded test HTTP timeout.")
            adapter.__timeouts = timeouts
        if session_factory is not None:
            adapter.__session_factory = session_factory
        return adapter

    @property
    def test_only(self):
        return self.__test_only

    @property
    def response_metadata(self):
        return self.__response_metadata

    def send(self, *, endpoint, model, request, credential, timeout_seconds,
             allow_redirects, trust_environment):
        self.__response_metadata = None
        if (endpoint != TRUSTED_ENDPOINT or model != TRUSTED_MODEL
                or timeout_seconds != TIMEOUT_SECONDS or allow_redirects is not ALLOW_REDIRECTS
                or trust_environment is not TRUST_ENVIRONMENT):
            raise OpenAIHTTPError("Trusted PROD-01 model transport binding mismatch.")
        if (type(request) is not bytes or not request or len(request) > MAX_REQUEST_BYTES):
            raise OpenAIHTTPError("Invalid bounded OpenAI request.")
        if credential is not None:
            raise OpenAIHTTPError("Credential must remain inside the trusted OpenAI adapter.")
        credential = self.__credential_provider.credential()
        if (type(credential) is not str or not credential or len(credential) > 4096
                or "\r" in credential or "\n" in credential):
            raise OpenAIHTTPError("Trusted OpenAI credential is unavailable.")
        try:
            internal_request = parse_json(request.decode("utf-8"))
        except (UnicodeError, ValidationError):
            raise OpenAIHTTPError("Malformed trusted OpenAI request.") from None
        body = project_openai_responses_request(internal_request)
        encoded = canonical_json(body).encode("utf-8")
        if len(encoded) > MAX_REQUEST_BYTES:
            raise OpenAIHTTPError("Bounded OpenAI request is too large.")
        headers = {
            "Authorization": "Bearer " + credential,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            with self.__session_factory() as session:
                session.trust_env = False
                session.headers.clear()
                session.mount("https://", HTTPAdapter(max_retries=HTTP_MAX_RETRIES))
                session.mount("http://", HTTPAdapter(max_retries=HTTP_MAX_RETRIES))
                with session.post(
                        self.__endpoint, data=encoded, headers=headers, stream=True,
                        allow_redirects=ALLOW_REDIRECTS, timeout=self.__timeouts,
                        verify=True) as response:
                    response_metadata = _response_metadata(response)
                    self.__response_metadata = response_metadata
                    if response.status_code != 200:
                        raise OpenAIHTTPError(
                            "OpenAI returned a non-success HTTP status.",
                            failure_reason=_status_failure_reason(response.status_code),
                            response_metadata=response_metadata)
                    if response_metadata["content_type"] != "APPLICATION_JSON":
                        raise OpenAIHTTPError(
                            "OpenAI response content type was not JSON.",
                            failure_reason=PROVIDER_CONTENT_TYPE_INVALID,
                            response_metadata=response_metadata)
                    if response_metadata["content_encoding"] == "OTHER":
                        raise OpenAIHTTPError(
                            "OpenAI response content encoding was unsupported.",
                            failure_reason=PROVIDER_ENCODING_UNSUPPORTED,
                            response_metadata=response_metadata)
                    if not response_metadata["declared_content_length_valid"]:
                        raise OpenAIHTTPError(
                            "OpenAI returned an invalid response length.",
                            response_metadata=response_metadata)
                    declared_bytes = response_metadata["declared_content_length"]
                    if (declared_bytes is not None
                            and declared_bytes > MAX_RESPONSE_BYTES):
                        raise OpenAIHTTPError(
                            "OpenAI response exceeded the byte limit.",
                            failure_reason=PROVIDER_RESPONSE_TOO_LARGE,
                            response_metadata=response_metadata)
                    chunks = []
                    total = 0
                    for chunk in response.iter_content(
                            chunk_size=_RESPONSE_CHUNK_BYTES, decode_unicode=False):
                        if not chunk:
                            continue
                        if type(chunk) is not bytes:
                            raise OpenAIHTTPError(
                                "OpenAI response was not delivered as bytes.",
                                response_metadata=response_metadata)
                        total += len(chunk)
                        response_metadata["body_bytes"] = min(total, MAX_RESPONSE_BYTES + 1)
                        response_metadata["body_empty"] = False
                        if total > MAX_RESPONSE_BYTES:
                            raise OpenAIHTTPError(
                                "OpenAI response exceeded the byte limit.",
                                failure_reason=PROVIDER_RESPONSE_TOO_LARGE,
                                response_metadata=response_metadata)
                        chunks.append(chunk)
                    response_metadata["body_empty"] = total == 0
                    if (declared_bytes is not None
                            and response_metadata["content_encoding"] in {"MISSING", "IDENTITY"}):
                        response_metadata["declared_length_matches"] = total == declared_bytes
                        if total != declared_bytes:
                            raise OpenAIHTTPError(
                                "OpenAI response length did not match its declaration.",
                                failure_reason=PROVIDER_RESPONSE_TRUNCATED,
                                response_metadata=response_metadata)
                    return b"".join(chunks)
        except OpenAIHTTPError:
            raise
        except requests.exceptions.ChunkedEncodingError:
            raise OpenAIHTTPError(
                "OpenAI response was truncated.",
                failure_reason=PROVIDER_RESPONSE_TRUNCATED,
                response_metadata=self.__response_metadata) from None
        except requests.exceptions.ContentDecodingError:
            raise OpenAIHTTPError(
                "OpenAI response encoding could not be decoded.",
                failure_reason=PROVIDER_ENCODING_UNSUPPORTED,
                response_metadata=self.__response_metadata) from None
        except requests.exceptions.Timeout:
            raise OpenAIHTTPError(
                "OpenAI HTTP request timed out.", failure_reason=PROVIDER_TIMEOUT,
                response_metadata=self.__response_metadata) from None
        except requests.exceptions.SSLError:
            raise OpenAIHTTPError(
                "OpenAI TLS connection failed.", failure_reason=PROVIDER_CONNECTION_ERROR,
                response_metadata=self.__response_metadata) from None
        except requests.exceptions.ConnectionError:
            raise OpenAIHTTPError(
                "OpenAI HTTP connection failed.",
                failure_reason=PROVIDER_CONNECTION_ERROR,
                response_metadata=self.__response_metadata) from None
        except requests.exceptions.RequestException:
            raise OpenAIHTTPError(
                "OpenAI HTTP request failed closed.", failure_reason=PROVIDER_ERROR,
                response_metadata=self.__response_metadata) from None


def _classify_content_type(value):
    if value is None:
        return "MISSING"
    if type(value) is not str:
        return "OTHER"
    media_type = value.split(";", 1)[0].strip().lower()
    return "APPLICATION_JSON" if media_type == "application/json" else "OTHER"


def _classify_content_encoding(value):
    if value is None or not value.strip():
        return "MISSING"
    encodings = [item.strip().lower() for item in value.split(",")]
    if len(encodings) != 1:
        return "OTHER"
    return {
        "identity": "IDENTITY",
        "gzip": "GZIP",
        "deflate": "DEFLATE",
    }.get(encodings[0], "OTHER")


def _response_metadata(response):
    declared = response.headers.get("Content-Length")
    declared_valid = True
    declared_bytes = None
    if declared is not None:
        try:
            parsed = int(declared)
            if parsed < 0:
                raise ValueError
            declared_bytes = min(parsed, MAX_RESPONSE_BYTES + 1)
        except (TypeError, ValueError):
            declared_valid = False
    return {
        "http_status": response.status_code,
        "content_type": _classify_content_type(response.headers.get("Content-Type")),
        "content_encoding": _classify_content_encoding(response.headers.get("Content-Encoding")),
        "body_bytes": 0,
        "body_empty": True,
        "content_length_present": declared is not None,
        "declared_content_length": declared_bytes,
        "declared_content_length_valid": declared_valid,
        "declared_length_matches": None,
        "utf8_decode_success": None,
        "json_decode_success": None,
    }


def _status_failure_reason(status_code):
    if status_code == 401:
        return PROVIDER_AUTH_ERROR
    if status_code == 403:
        return PROVIDER_PERMISSION_ERROR
    if status_code == 404:
        return PROVIDER_NOT_FOUND
    if status_code == 429:
        return PROVIDER_RATE_LIMIT
    if 300 <= status_code < 500:
        return PROVIDER_REQUEST_REJECTED
    if 500 <= status_code < 600:
        return PROVIDER_SERVER_ERROR
    return PROVIDER_ERROR
