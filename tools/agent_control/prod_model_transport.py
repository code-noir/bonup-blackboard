"""Bounded PROD-01 model transport; proposals only, with no execution authority."""
from dataclasses import dataclass
from typing import Protocol

from .prod_contract import REFERENCE_TYPES, validate_product_proposal, validate_product_task
from .serialization import canonical_json, digest, parse_json
from .types import ValidationError

MAX_REQUEST_BYTES = 65536
MAX_RESPONSE_BYTES = 65536
TIMEOUT_SECONDS = 30
MAX_REQUESTS_PER_CYCLE = 1
MAX_RETRIES = 0
ALLOW_REDIRECTS = False
TRUST_ENVIRONMENT = False
MAX_OUTPUT_ITEMS = 32
MAX_CONTENT_PARTS = 8
INITIAL_PREDECESSOR_INVALID = "INITIAL_PREDECESSOR_INVALID"
TASK_ID_PATTERN = (
    r"^ATS-(?:[0-9]{3}[1-9]|[0-9]{2}[1-9][0-9]|[0-9][1-9][0-9]{2}|[1-9][0-9]{3,})$"
)
PROVIDER_ERROR = "PROVIDER_ERROR"
PROVIDER_AUTH_ERROR = "PROVIDER_AUTH_ERROR"
PROVIDER_PERMISSION_ERROR = "PROVIDER_PERMISSION_ERROR"
PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
PROVIDER_REQUEST_REJECTED = "PROVIDER_REQUEST_REJECTED"
PROVIDER_SERVER_ERROR = "PROVIDER_SERVER_ERROR"
PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
PROVIDER_CONNECTION_ERROR = "PROVIDER_CONNECTION_ERROR"
PROVIDER_RESPONSE_TOO_LARGE = "PROVIDER_RESPONSE_TOO_LARGE"
SAFE_TRANSPORT_FAILURE_REASONS = frozenset({
    PROVIDER_ERROR, PROVIDER_AUTH_ERROR, PROVIDER_PERMISSION_ERROR,
    PROVIDER_NOT_FOUND, PROVIDER_RATE_LIMIT, PROVIDER_REQUEST_REJECTED,
    PROVIDER_SERVER_ERROR, PROVIDER_TIMEOUT, PROVIDER_CONNECTION_ERROR,
    PROVIDER_RESPONSE_TOO_LARGE,
})
_PROVIDER_SCHEMA_KEYWORDS = frozenset({
    "type", "additionalProperties", "required", "properties", "items",
    "pattern", "format", "minLength", "maxLength", "minItems", "maxItems",
    "enum", "const", "anyOf",
})
TRUSTED_ENDPOINT = "https://api.openai.com/v1/responses"
TRUSTED_MODEL = "PROD-01-STRUCTURED-MODEL-V1"
LOCAL_CONTRACT_VALIDATED = True
PROVIDER_WIRE_COMPATIBILITY = "LIVE_OR_OFFICIAL_CHECK_REQUIRED"
ACCOUNT_MODEL_ACCESS = "AUTHENTICATED_CHECK_REQUIRED"

_REFERENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reference_type", "reference_id", "digest", "knowledge_state"],
    "properties": {
        "reference_type": {"type": "string", "enum": list(REFERENCE_TYPES)},
        "reference_id": {
            "type": "string", "maxLength": 128,
            "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
        },
        "digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "knowledge_state": {"type": "string", "enum": ["DIRECT_FOUNDER", "APPROVED_INTERNAL"]},
    },
}
_TEXT = {"type": "string", "minLength": 1, "maxLength": 4096, "pattern": "\\S"}
_TEXT_LIST = {"type": "array", "maxItems": 50, "items": _TEXT}


def validate_provider_schema_subset(schema):
    """Reject provider-schema keywords outside the reviewed local subset."""
    def visit(value):
        if type(value) is not dict or not set(value) <= _PROVIDER_SCHEMA_KEYWORDS:
            raise ValidationError("Unsupported PROD-01 provider schema keyword.")
        properties = value.get("properties")
        if properties is not None:
            if type(properties) is not dict:
                raise ValidationError("Malformed PROD-01 provider schema properties.")
            for child in properties.values():
                visit(child)
        if "items" in value:
            visit(value["items"])
        if "anyOf" in value:
            alternatives = value["anyOf"]
            if type(alternatives) is not list:
                raise ValidationError("Malformed PROD-01 provider schema alternatives.")
            for child in alternatives:
                visit(child)

    visit(schema)


_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "agent_id", "task_id", "proposal_id", "predecessor_proposal_id", "proposal_type",
        "title", "problem_user_need", "objective", "proposed_requirement", "acceptance_intent",
        "dependencies", "assumptions", "risks_open_questions", "priority_recommendation",
        "evidence_references", "knowledge_state",
    ],
    "properties": {
        "agent_id": {"type": "string", "const": "PROD-01"},
        "task_id": {"type": "string", "pattern": TASK_ID_PATTERN},
        "proposal_id": {"type": "string", "format": "uuid"},
        "predecessor_proposal_id": {"anyOf": [{"type": "string", "format": "uuid"}, {"type": "null"}]},
        "proposal_type": {"type": "string", "const": "PRODUCT_REQUIREMENT_PROPOSAL"},
        "title": _TEXT,
        "problem_user_need": _TEXT,
        "objective": _TEXT,
        "proposed_requirement": _TEXT,
        "acceptance_intent": _TEXT_LIST,
        "dependencies": {"type": "array", "maxItems": 50,
                         "items": {"type": "string", "pattern": TASK_ID_PATTERN}},
        "assumptions": _TEXT_LIST,
        "risks_open_questions": _TEXT_LIST,
        "priority_recommendation": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
        "evidence_references": {"type": "array", "maxItems": 50, "items": _REFERENCE_SCHEMA},
        "knowledge_state": {"type": "string", "const": "WORKING"},
    },
}
validate_provider_schema_subset(_PROPOSAL_SCHEMA)
PRODUCT_PROPOSAL_SCHEMA_DIGEST = digest(_PROPOSAL_SCHEMA)


class ProductTransport(Protocol):
    """Trusted transport implementation; no implementation is provided here."""

    def send(self, *, endpoint, model, request, credential, timeout_seconds,
             allow_redirects, trust_environment): ...


class CredentialProvider(Protocol):
    """Trusted credential source. Its return value must remain transport-private."""

    def credential(self): ...


class ProductModelFailure(ValidationError):
    """Fail-closed error carrying only bounded, non-secret audit metadata."""

    def __init__(self, message, audit_metadata):
        super().__init__(message)
        self.audit_metadata = parse_json(canonical_json(audit_metadata))


class ProductOutputFailure(ValidationError):
    """Internal output rejection carrying only a bounded, code-owned reason."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _reject_output(reason):
    raise ProductOutputFailure(reason)


@dataclass(frozen=True)
class ProductModelCycle:
    task: dict
    proposal: dict
    proposal_bytes: bytes
    proposal_digest: str
    audit_metadata: dict


def project_product_context(task):
    """Project validated task metadata only; never dereference supplied references."""
    task = validate_product_task(task)
    return {
        "agent_id": "PROD-01",
        "role": "Product",
        "authority": "PROPOSAL_ONLY",
        "task_id": task["task_id"],
        "task_class": task["task_class"],
        "objective": task["objective"],
        "reference_metadata": task["input_references"],
        "behavior_contract": [
            "PRODUCE_PRODUCT_REQUIREMENT_PROPOSAL_ONLY",
            "CANNOT_APPROVE", "CANNOT_ASSIGN", "CANNOT_GRANT_AUTHORITY", "CANNOT_EXECUTE",
            "CANNOT_DEPLOY", "CANNOT_PUBLISH", "CANNOT_ACTIVATE_AGENTS",
            "COPY_TASK_ID_EXACTLY",
            "EVIDENCE_REFERENCES_MUST_BE_SUBSET_OF_INPUT_REFERENCES",
            "USE_CANONICAL_UUID_PROPOSAL_IDENTITIES",
            "INITIAL_PROPOSAL_PREDECESSOR_MUST_BE_NULL",
            "DO_NOT_USE_APPROVED_ASSIGNED_AUTHORIZED_DEPLOYED_IMPLEMENTED_TESTED_PUBLISHED_AS_STATUS_CLAIMS",
            "DO_NOT_INCLUDE_SENSITIVE_AUTHENTICATION_MATERIAL",
        ],
        "required_output_schema": parse_json(canonical_json(_PROPOSAL_SCHEMA)),
    }


def build_product_model_request(task):
    validate_provider_schema_subset(_PROPOSAL_SCHEMA)
    context = project_product_context(task)
    request = {
        "contract_version": 1,
        "agent_id": "PROD-01",
        "logical_model": TRUSTED_MODEL,
        "context": context,
        "tools": [],
        "output_contract": {
            "type": "PRODUCT_REQUIREMENT_PROPOSAL",
            "encoding": "STRICT_JSON_SCHEMA",
            "name": "product_requirement_proposal",
            "strict": True,
            "schema": parse_json(canonical_json(_PROPOSAL_SCHEMA)),
            "schema_digest": PRODUCT_PROPOSAL_SCHEMA_DIGEST,
        },
        "request_policy": {
            "max_requests": MAX_REQUESTS_PER_CYCLE,
            "max_retries": MAX_RETRIES,
        },
    }
    raw = canonical_json(request).encode("utf-8")
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValidationError("Bounded PROD-01 model request is too large.")
    return request, raw


def parse_product_model_response(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_RESPONSE_BYTES:
        _reject_output("PROVIDER_ENVELOPE_INVALID")
    try:
        envelope = parse_json(raw.decode("utf-8"))
    except (UnicodeError, ValidationError):
        _reject_output("PROVIDER_ENVELOPE_INVALID")
    if (type(envelope) is not dict or envelope.get("status") != "completed"
            or type(envelope.get("output")) is not list
            or not envelope["output"] or len(envelope["output"]) > MAX_OUTPUT_ITEMS):
        _reject_output("PROVIDER_ENVELOPE_INVALID")

    proposal_texts = []
    for item in envelope["output"]:
        if type(item) is not dict or type(item.get("type")) is not str:
            _reject_output("PROVIDER_ENVELOPE_INVALID")
        if item["type"] == "reasoning":
            continue
        if (item["type"] != "message" or item.get("role") != "assistant"
                or item.get("status") != "completed"):
            _reject_output("PROVIDER_ENVELOPE_INVALID")
        content = item.get("content")
        if (type(content) is not list or not content
                or len(content) > MAX_CONTENT_PARTS):
            _reject_output("PROVIDER_ENVELOPE_INVALID")
        for part in content:
            if type(part) is not dict or type(part.get("type")) is not str:
                _reject_output("PROVIDER_ENVELOPE_INVALID")
            if part["type"] == "refusal":
                _reject_output("PROVIDER_ENVELOPE_INVALID")
            if part["type"] != "output_text" or type(part.get("text")) is not str:
                _reject_output("PROVIDER_ENVELOPE_INVALID")
            proposal_texts.append(part["text"])

    if len(proposal_texts) != 1:
        _reject_output("PROVIDER_ENVELOPE_INVALID")
    if not proposal_texts[0] or len(proposal_texts[0].encode("utf-8")) > MAX_RESPONSE_BYTES:
        _reject_output("PROVIDER_ENVELOPE_INVALID")
    try:
        candidate = parse_json(proposal_texts[0])
    except ValidationError:
        _reject_output("STRUCTURED_JSON_INVALID")
    if type(candidate) is not dict:
        _reject_output("STRUCTURED_JSON_INVALID")
    return candidate


def _proposal_rejection_reason(error):
    """Map trusted validator messages to bounded codes without returning content."""
    message = str(error)
    if message == "PROD-01 proposal cannot claim approval, authority, execution, or publication.":
        return "AUTHORITY_CLAIM_REJECTED"
    if message == "PROD-01 content cannot contain secrets or credentials.":
        return "CONTENT_POLICY_REJECTED"
    if message == "PROD-01 cannot self-promote proposal knowledge.":
        return "KNOWLEDGE_STATE_INVALID"
    if message in {
            "PROD-01 proposal identity mismatch.",
            "Invalid PROD-01 predecessor proposal identity."}:
        return "PROPOSAL_ID_INVALID"
    return "PROPOSAL_SCHEMA_MISMATCH"


def _audit(task_id, request_digest, classification, *, proposal_digest=None, reason=None):
    value = {
        "agent_id": "PROD-01",
        "task_id": task_id,
        "request_digest": request_digest,
        "trusted_model": TRUSTED_MODEL,
        "result_classification": classification,
        "proposal_digest": proposal_digest,
        "failure_reason": reason,
    }
    return parse_json(canonical_json(value))


def _transport_failure_reason(error):
    reason = getattr(error, "failure_reason", None)
    if type(reason) is str and reason in SAFE_TRANSPORT_FAILURE_REASONS:
        return reason
    return PROVIDER_ERROR


def run_product_model_cycle(task_input, transport, credential_provider=None, *,
                            require_initial_predecessor_null=False):
    """Perform one bounded model call and stop; create no authority or registry state."""
    task = validate_product_task(task_input)
    request, request_bytes = build_product_model_request(task)
    request_digest = digest(request)
    try:
        if getattr(transport, "credential_owned", False) is True:
            if credential_provider is not None:
                raise ValidationError("Credential provider must remain inside the trusted transport.")
            credential = None
        else:
            if credential_provider is None:
                raise ValidationError("Trusted PROD-01 model credential provider is unavailable.")
            credential = credential_provider.credential()
            if credential is None:
                raise ValidationError("Trusted PROD-01 model credential is unavailable.")
        raw = transport.send(
            endpoint=TRUSTED_ENDPOINT,
            model=TRUSTED_MODEL,
            request=request_bytes,
            credential=credential,
            timeout_seconds=TIMEOUT_SECONDS,
            allow_redirects=ALLOW_REDIRECTS,
            trust_environment=TRUST_ENVIRONMENT,
        )
    except Exception as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        metadata = _audit(task["task_id"], request_digest, "TRANSPORT_FAILED",
                          reason=_transport_failure_reason(error))
        raise ProductModelFailure("PROD-01 model transport failed closed.", metadata) from None
    try:
        candidate = parse_product_model_response(raw)
    except ProductOutputFailure as error:
        metadata = _audit(task["task_id"], request_digest, "OUTPUT_REJECTED",
                          reason=error.reason)
        raise ProductModelFailure("PROD-01 model output failed strict validation.", metadata) from None
    try:
        proposal = validate_product_proposal(candidate)
    except ValidationError as error:
        metadata = _audit(task["task_id"], request_digest, "OUTPUT_REJECTED",
                          reason=_proposal_rejection_reason(error))
        raise ProductModelFailure("PROD-01 model output failed strict validation.", metadata) from None
    if proposal["task_id"] != task["task_id"]:
        metadata = _audit(task["task_id"], request_digest, "OUTPUT_REJECTED",
                          reason="TASK_BINDING_INVALID")
        raise ProductModelFailure("PROD-01 model output failed strict validation.", metadata) from None
    if (require_initial_predecessor_null
            and proposal["predecessor_proposal_id"] is not None):
        metadata = _audit(task["task_id"], request_digest, "OUTPUT_REJECTED",
                          reason=INITIAL_PREDECESSOR_INVALID)
        raise ProductModelFailure("PROD-01 model output failed strict validation.", metadata) from None
    available = {canonical_json(item) for item in task["input_references"]}
    if any(canonical_json(item) not in available for item in proposal["evidence_references"]):
        metadata = _audit(task["task_id"], request_digest, "OUTPUT_REJECTED",
                          reason="EVIDENCE_BINDING_INVALID")
        raise ProductModelFailure("PROD-01 model output failed strict validation.", metadata) from None
    proposal_bytes = (canonical_json(proposal) + "\n").encode("utf-8")
    proposal_digest = digest(proposal)
    metadata = _audit(task["task_id"], request_digest, "VALIDATED_PROPOSAL",
                      proposal_digest=proposal_digest)
    return ProductModelCycle(task, proposal, proposal_bytes, proposal_digest, metadata)
