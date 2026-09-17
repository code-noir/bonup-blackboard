"""Bounded PROD-01 model transport; proposals only, with no execution authority."""
from dataclasses import dataclass
from typing import Protocol

from .prod_contract import validate_product_proposal, validate_product_task
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
TRUSTED_ENDPOINT = "https://api.openai.com/v1/responses"
TRUSTED_MODEL = "PROD-01-STRUCTURED-MODEL-V1"

_REFERENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reference_type", "reference_id", "digest", "knowledge_state"],
    "properties": {
        "reference_type": {"type": "string"},
        "reference_id": {"type": "string", "maxLength": 128},
        "digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "knowledge_state": {"type": "string", "enum": ["DIRECT_FOUNDER", "APPROVED_INTERNAL"]},
    },
}
_TEXT = {"type": "string", "minLength": 1, "maxLength": 4096}
_TEXT_LIST = {"type": "array", "maxItems": 50, "items": _TEXT}
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
        "task_id": {"type": "string", "pattern": "^ATS-(?:[0-9]{4}|[1-9][0-9]{4,})$"},
        "proposal_id": {"type": "string", "format": "uuid"},
        "predecessor_proposal_id": {"anyOf": [{"type": "string", "format": "uuid"}, {"type": "null"}]},
        "proposal_type": {"type": "string", "const": "PRODUCT_REQUIREMENT_PROPOSAL"},
        "title": _TEXT,
        "problem_user_need": _TEXT,
        "objective": _TEXT,
        "proposed_requirement": _TEXT,
        "acceptance_intent": _TEXT_LIST,
        "dependencies": {"type": "array", "maxItems": 50, "items": {"type": "string", "pattern": "^ATS-(?:[0-9]{4}|[1-9][0-9]{4,})$"}},
        "assumptions": _TEXT_LIST,
        "risks_open_questions": _TEXT_LIST,
        "priority_recommendation": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
        "evidence_references": {"type": "array", "maxItems": 50, "items": _REFERENCE_SCHEMA},
        "knowledge_state": {"type": "string", "const": "WORKING"},
    },
}


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
        ],
        "required_output_schema": parse_json(canonical_json(_PROPOSAL_SCHEMA)),
    }


def build_product_model_request(task):
    context = project_product_context(task)
    request = {
        "model": TRUSTED_MODEL,
        "input": canonical_json(context),
        "tools": [],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "product_requirement_proposal",
                "strict": True,
                "schema": parse_json(canonical_json(_PROPOSAL_SCHEMA)),
            }
        },
        "store": False,
    }
    raw = canonical_json(request).encode("utf-8")
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValidationError("Bounded PROD-01 model request is too large.")
    return request, raw


def parse_product_model_response(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise ValidationError("Invalid bounded PROD-01 model response.")
    try:
        envelope = parse_json(raw.decode("utf-8"))
    except (UnicodeError, ValidationError):
        raise ValidationError("Malformed PROD-01 model response.") from None
    if (type(envelope) is not dict or envelope.get("status") != "completed"
            or type(envelope.get("output")) is not list
            or not envelope["output"] or len(envelope["output"]) > MAX_OUTPUT_ITEMS):
        raise ValidationError("PROD-01 model response is incomplete or unbounded.")

    proposal_texts = []
    for item in envelope["output"]:
        if type(item) is not dict or type(item.get("type")) is not str:
            raise ValidationError("Invalid PROD-01 Responses output item.")
        if item["type"] == "reasoning":
            continue
        if (item["type"] != "message" or item.get("role") != "assistant"
                or item.get("status") != "completed"):
            raise ValidationError("Unexpected non-assistant PROD-01 Responses output.")
        content = item.get("content")
        if (type(content) is not list or not content
                or len(content) > MAX_CONTENT_PARTS):
            raise ValidationError("Invalid bounded PROD-01 message content.")
        for part in content:
            if type(part) is not dict or type(part.get("type")) is not str:
                raise ValidationError("Invalid PROD-01 message content part.")
            if part["type"] == "refusal":
                raise ValidationError("PROD-01 model refused the proposal request.")
            if part["type"] != "output_text" or type(part.get("text")) is not str:
                raise ValidationError("Unexpected PROD-01 message content type.")
            proposal_texts.append(part["text"])

    if len(proposal_texts) != 1:
        raise ValidationError("PROD-01 response must contain exactly one proposal text.")
    if not proposal_texts[0] or len(proposal_texts[0].encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValidationError("Invalid bounded PROD-01 proposal text.")
    try:
        candidate = parse_json(proposal_texts[0])
    except ValidationError:
        raise ValidationError("Malformed PROD-01 proposal JSON.") from None
    if type(candidate) is not dict:
        raise ValidationError("PROD-01 proposal JSON must be an object.")
    return candidate


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


def run_product_model_cycle(task_input, transport, credential_provider=None):
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
                          reason="TRANSPORT_ERROR")
        raise ProductModelFailure("PROD-01 model transport failed closed.", metadata) from None
    try:
        candidate = parse_product_model_response(raw)
        proposal = validate_product_proposal(candidate)
        if proposal["task_id"] != task["task_id"]:
            raise ValidationError("PROD-01 model proposal belongs to another task.")
        available = {canonical_json(item) for item in task["input_references"]}
        if any(canonical_json(item) not in available for item in proposal["evidence_references"]):
            raise ValidationError("PROD-01 model proposal introduced an unbound evidence reference.")
    except ValidationError:
        metadata = _audit(task["task_id"], request_digest, "OUTPUT_REJECTED",
                          reason="INVALID_STRUCTURED_PROPOSAL")
        raise ProductModelFailure("PROD-01 model output failed strict validation.", metadata) from None
    proposal_bytes = (canonical_json(proposal) + "\n").encode("utf-8")
    proposal_digest = digest(proposal)
    metadata = _audit(task["task_id"], request_digest, "VALIDATED_PROPOSAL",
                      proposal_digest=proposal_digest)
    return ProductModelCycle(task, proposal, proposal_bytes, proposal_digest, metadata)
