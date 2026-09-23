"""Bounded PROD-01 model transport; proposals only, with no execution authority."""
from dataclasses import dataclass
import json
import re
from typing import Protocol

from .prod_contract import REFERENCE_TYPES, validate_product_proposal, validate_product_task
from .serialization import (
    canonical_json, digest, parse_json,
)
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
MAX_DIAGNOSTIC_VALUES = 8
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
PROVIDER_CONTENT_TYPE_INVALID = "PROVIDER_CONTENT_TYPE_INVALID"
PROVIDER_ENCODING_UNSUPPORTED = "PROVIDER_ENCODING_UNSUPPORTED"
PROVIDER_RESPONSE_TRUNCATED = "PROVIDER_RESPONSE_TRUNCATED"
PROPOSAL_ARTIFACT_PERSISTENCE_FAILED = "PROPOSAL_ARTIFACT_PERSISTENCE_FAILED"
SAFE_TRANSPORT_FAILURE_REASONS = frozenset({
    PROVIDER_ERROR, PROVIDER_AUTH_ERROR, PROVIDER_PERMISSION_ERROR,
    PROVIDER_NOT_FOUND, PROVIDER_RATE_LIMIT, PROVIDER_REQUEST_REJECTED,
    PROVIDER_SERVER_ERROR, PROVIDER_TIMEOUT, PROVIDER_CONNECTION_ERROR,
    PROVIDER_RESPONSE_TOO_LARGE, PROVIDER_CONTENT_TYPE_INVALID,
    PROVIDER_ENCODING_UNSUPPORTED, PROVIDER_RESPONSE_TRUNCATED,
})
_PROVIDER_SCHEMA_KEYWORDS = frozenset({
    "type", "additionalProperties", "required", "properties", "items",
    "pattern", "format", "minLength", "maxLength", "minItems", "maxItems",
    "enum", "const", "anyOf",
})
_RESPONSE_STATUSES = frozenset({
    "completed", "incomplete", "failed", "queued", "in_progress", "cancelled",
})
_MESSAGE_STATUSES = frozenset({"completed", "incomplete", "in_progress", "failed"})
_MESSAGE_ROLES = frozenset({"assistant", "user", "system", "developer"})
_KNOWN_OUTPUT_TYPES = frozenset({"reasoning", "message"})
_KNOWN_CONTENT_TYPES = frozenset({"output_text", "refusal"})
_SAFE_STRUCTURE_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_:-]{0,63}\Z", re.ASCII)
_RESPONSE_CONTENT_TYPES = frozenset({"APPLICATION_JSON", "OTHER", "MISSING"})
_RESPONSE_ENCODINGS = frozenset({"IDENTITY", "GZIP", "DEFLATE", "OTHER", "MISSING"})
_RESPONSE_METADATA_KEYS = frozenset({
    "http_status", "content_type", "content_encoding", "body_bytes", "body_empty",
    "content_length_present", "declared_content_length", "declared_content_length_valid",
    "declared_length_matches", "utf8_decode_success", "json_decode_success",
})
_JSON_ERROR_CATEGORIES = frozenset({
    "EXPECTING_VALUE", "EXPECTING_PROPERTY_NAME", "EXPECTING_COLON",
    "EXPECTING_COMMA", "UNTERMINATED_STRING", "INVALID_ESCAPE",
    "INVALID_CONTROL_CHARACTER", "EXTRA_DATA", "OTHER_JSON_SYNTAX",
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

    def __init__(self, classification, reason, provider_structure):
        super().__init__(classification)
        self.classification = classification
        self.reason = reason
        self.provider_structure = parse_json(canonical_json(provider_structure))


def _new_provider_structure():
    return {
        "output_count": 0,
        "output_types": [],
        "message_count": 0,
        "message_statuses": [],
        "message_roles": [],
        "content_count": 0,
        "content_types": [],
        "refusal_present": False,
    }


def _append_bounded(values, value):
    if len(values) < MAX_DIAGNOSTIC_VALUES:
        values.append(value)


def _safe_structure_type(value, known):
    if type(value) is str and value in known:
        return value
    if (type(value) is str and value.isascii()
            and _SAFE_STRUCTURE_IDENTIFIER.fullmatch(value)):
        return value
    return "UNSAFE_TYPE"


def _safe_structure_enum(value, known):
    return value if type(value) is str and value in known else "UNRECOGNIZED"


def _bounded_response_metadata(value):
    """Retain only the adapter's fixed, non-content response metadata."""
    if type(value) is not dict or not set(value) <= _RESPONSE_METADATA_KEYS:
        return None
    result = {}
    for key in _RESPONSE_METADATA_KEYS:
        if key not in value:
            continue
        item = value[key]
        if key == "http_status":
            if type(item) is not int or not 100 <= item <= 599:
                return None
        elif key == "content_type":
            if type(item) is not str or item not in _RESPONSE_CONTENT_TYPES:
                return None
        elif key == "content_encoding":
            if type(item) is not str or item not in _RESPONSE_ENCODINGS:
                return None
        elif key in {"body_bytes", "declared_content_length"}:
            if item is not None and (type(item) is not int
                                     or not 0 <= item <= MAX_RESPONSE_BYTES + 1):
                return None
        elif key in {"body_empty", "content_length_present", "declared_content_length_valid"}:
            if type(item) is not bool:
                return None
        elif key in {"declared_length_matches", "utf8_decode_success",
                     "json_decode_success"}:
            if item is not None and type(item) is not bool:
                return None
        result[key] = item
    return result


def _json_error_metadata(error, body_bytes, character_count):
    """Project only bounded JSON decoder positions and code-owned categories."""
    def bounded(value):
        return min(max(value if type(value) is int else 0, 0), MAX_RESPONSE_BYTES)

    category = getattr(error, "category", None)
    if category not in _JSON_ERROR_CATEGORIES:
        category = {
            "Expecting value": "EXPECTING_VALUE",
            "Expecting property name enclosed in double quotes": "EXPECTING_PROPERTY_NAME",
            "Expecting ':' delimiter": "EXPECTING_COLON",
            "Expecting ',' delimiter": "EXPECTING_COMMA",
        }.get(getattr(error, "msg", None), "OTHER_JSON_SYNTAX")
        if getattr(error, "msg", "").startswith("Unterminated string"):
            category = "UNTERMINATED_STRING"
        elif getattr(error, "msg", "").startswith("Invalid \\escape"):
            category = "INVALID_ESCAPE"
        elif getattr(error, "msg", "").startswith("Invalid control character"):
            category = "INVALID_CONTROL_CHARACTER"
        elif getattr(error, "msg", None) == "Extra data":
            category = "EXTRA_DATA"
    line = getattr(error, "line", getattr(error, "lineno", 0))
    column = getattr(error, "column", getattr(error, "colno", 0))
    position = getattr(error, "position", getattr(error, "pos", 0))
    character_count = getattr(error, "character_count", character_count)
    return {
        "category": category,
        "line": bounded(line),
        "column": bounded(column),
        "position": bounded(position),
        "character_count": bounded(character_count),
        "body_bytes": bounded(body_bytes),
    }


def _reject_output(reason, *, classification="PROVIDER_ENVELOPE_INVALID", structure=None):
    value = _new_provider_structure() if structure is None else structure
    value = dict(value)
    value["reason"] = reason
    raise ProductOutputFailure(classification, reason, value)


@dataclass(frozen=True)
class ProductModelCycle:
    task: dict
    proposal: dict
    proposal_bytes: bytes
    proposal_digest: str
    audit_metadata: dict
    proposal_artifact: object = None


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


def parse_product_model_response(raw, *, response_metadata=None):
    structure = _new_provider_structure()
    bounded_metadata = _bounded_response_metadata(response_metadata)
    if bounded_metadata is not None:
        structure["http_response"] = bounded_metadata
    if type(raw) is not bytes or not raw:
        _reject_output("RESPONSE_BYTES_INVALID" if type(raw) is not bytes else "EMPTY_BODY",
                       structure=structure)
    if len(raw) > MAX_RESPONSE_BYTES:
        _reject_output("RESPONSE_TOO_LARGE", structure=structure)
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        if "http_response" in structure:
            structure["http_response"]["utf8_decode_success"] = False
            structure["http_response"]["json_decode_success"] = False
        _reject_output("INVALID_UTF8", structure=structure)
    try:
        # The provider envelope is third-party transport data.  It must not be
        # subjected to bonUP's canonical record rules; those begin at the
        # extracted model-produced proposal below.
        envelope = json.loads(text)
    except json.JSONDecodeError as error:
        if "http_response" in structure:
            structure["http_response"]["utf8_decode_success"] = True
            structure["http_response"]["json_decode_success"] = False
        structure["json_error"] = _json_error_metadata(error, len(raw), len(text))
        _reject_output("RESPONSE_JSON_INVALID", structure=structure)
    except (RecursionError, TypeError, ValueError):
        if "http_response" in structure:
            structure["http_response"]["utf8_decode_success"] = True
            structure["http_response"]["json_decode_success"] = False
        _reject_output("RESPONSE_JSON_INVALID", structure=structure)
    if "http_response" in structure:
        structure["http_response"]["utf8_decode_success"] = True
        structure["http_response"]["json_decode_success"] = True
    if type(envelope) is not dict:
        _reject_output("RESPONSE_NOT_OBJECT", structure=structure)

    if "status" not in envelope:
        _reject_output("RESPONSE_STATUS_MISSING", structure=structure)
    response_status = envelope["status"]
    structure["response_status"] = _safe_structure_enum(response_status, _RESPONSE_STATUSES)
    if type(response_status) is not str or response_status not in _RESPONSE_STATUSES:
        _reject_output("RESPONSE_STATUS_INVALID", structure=structure)
    if response_status != "completed":
        _reject_output("RESPONSE_STATUS_NOT_COMPLETED", structure=structure)
    if "output" not in envelope:
        _reject_output("OUTPUT_MISSING", structure=structure)
    output = envelope["output"]
    if type(output) is not list:
        _reject_output("OUTPUT_NOT_ARRAY", structure=structure)
    structure["output_count"] = min(len(output), MAX_OUTPUT_ITEMS + 1)
    if not output:
        _reject_output("OUTPUT_EMPTY", structure=structure)
    if len(output) > MAX_OUTPUT_ITEMS:
        _reject_output("OUTPUT_TOO_LARGE", structure=structure)

    proposal_texts = []
    assistant_message_count = 0
    for item in output:
        if type(item) is not dict:
            _reject_output("OUTPUT_ITEM_NOT_OBJECT", structure=structure)
        if "type" not in item:
            _reject_output("OUTPUT_ITEM_TYPE_MISSING", structure=structure)
        item_type = _safe_structure_type(item["type"], _KNOWN_OUTPUT_TYPES)
        _append_bounded(structure["output_types"], item_type)
        if item["type"] == "reasoning":
            continue
        if item["type"] != "message":
            _reject_output("UNEXPECTED_OUTPUT_ITEM", structure=structure)
        structure["message_count"] = min(structure["message_count"] + 1,
                                          MAX_DIAGNOSTIC_VALUES + 1)
        message_status = item.get("status")
        message_role = item.get("role")
        _append_bounded(structure["message_statuses"],
                        _safe_structure_enum(message_status, _MESSAGE_STATUSES))
        _append_bounded(structure["message_roles"],
                        _safe_structure_enum(message_role, _MESSAGE_ROLES))
        if type(message_status) is not str or message_status not in _MESSAGE_STATUSES:
            _reject_output("MESSAGE_STATUS_INVALID", structure=structure)
        if type(message_role) is not str or message_role not in _MESSAGE_ROLES:
            _reject_output("MESSAGE_ROLE_INVALID", structure=structure)
        if message_role != "assistant":
            _reject_output("MESSAGE_ROLE_INVALID", structure=structure)
        if message_status != "completed":
            _reject_output("MESSAGE_STATUS_INVALID", structure=structure)
        assistant_message_count += 1
        if assistant_message_count > 1:
            _reject_output("MULTIPLE_ASSISTANT_MESSAGES", structure=structure)
        if "content" not in item:
            _reject_output("CONTENT_MISSING", structure=structure)
        content = item["content"]
        if type(content) is not list:
            _reject_output("CONTENT_NOT_ARRAY", structure=structure)
        structure["content_count"] = min(len(content), MAX_CONTENT_PARTS + 1)
        if not content:
            _reject_output("CONTENT_EMPTY", structure=structure)
        if len(content) > MAX_CONTENT_PARTS:
            _reject_output("CONTENT_TOO_LARGE", structure=structure)
        for part in content:
            if type(part) is not dict:
                _reject_output("CONTENT_ITEM_NOT_OBJECT", structure=structure)
            if "type" not in part:
                _reject_output("CONTENT_TYPE_MISSING", structure=structure)
            content_type = _safe_structure_type(part["type"], _KNOWN_CONTENT_TYPES)
            _append_bounded(structure["content_types"], content_type)
            if part["type"] == "refusal":
                structure["refusal_present"] = True
                _reject_output("REFUSAL_PRESENT", structure=structure)
            if part["type"] != "output_text":
                _reject_output("UNEXPECTED_CONTENT_ITEM", structure=structure)
            if "text" not in part or type(part["text"]) is not str:
                _reject_output("OUTPUT_TEXT_INVALID", structure=structure)
            if not part["text"]:
                _reject_output("OUTPUT_TEXT_EMPTY", structure=structure)
            proposal_texts.append(part["text"])

    if assistant_message_count == 0:
        _reject_output("MESSAGE_MISSING", structure=structure)
    if len(proposal_texts) > 1:
        _reject_output("MULTIPLE_OUTPUT_TEXT", structure=structure)
    if len(proposal_texts) != 1:
        _reject_output("OUTPUT_TEXT_MISSING", structure=structure)
    if len(proposal_texts[0].encode("utf-8")) > MAX_RESPONSE_BYTES:
        _reject_output("OUTPUT_TEXT_TOO_LARGE", structure=structure)
    try:
        candidate = parse_json(proposal_texts[0])
    except ValidationError:
        _reject_output("STRUCTURED_JSON_INVALID", classification="STRUCTURED_JSON_INVALID",
                       structure=structure)
    if type(candidate) is not dict:
        _reject_output("STRUCTURED_JSON_INVALID", classification="STRUCTURED_JSON_INVALID",
                       structure=structure)
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


def _audit(task_id, request_digest, classification, *, proposal_digest=None, reason=None,
           provider_structure=None):
    value = {
        "agent_id": "PROD-01",
        "task_id": task_id,
        "request_digest": request_digest,
        "trusted_model": TRUSTED_MODEL,
        "result_classification": classification,
        "proposal_digest": proposal_digest,
        "failure_reason": reason,
    }
    if provider_structure is not None:
        value["provider_structure"] = provider_structure
    return parse_json(canonical_json(value))


def _transport_failure_reason(error):
    reason = getattr(error, "failure_reason", None)
    if type(reason) is str and reason in SAFE_TRANSPORT_FAILURE_REASONS:
        return reason
    return PROVIDER_ERROR


def _complete_product_model_cycle(task_input, raw, *, response_metadata=None,
                                  require_initial_predecessor_null=False,
                                  proposal_artifact_store=None, source_checkpoint=None):
    task = validate_product_task(task_input)
    request, _ = build_product_model_request(task)
    request_digest = digest(request)
    try:
        candidate = parse_product_model_response(raw, response_metadata=response_metadata)
    except ProductOutputFailure as error:
        metadata = _audit(task["task_id"], request_digest, "OUTPUT_REJECTED",
                          reason=error.classification,
                          provider_structure=error.provider_structure)
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
    artifact = None
    if proposal_artifact_store is not None:
        try:
            artifact = proposal_artifact_store.persist(
                proposal, source_checkpoint=source_checkpoint)
        except ValidationError:
            failure_metadata = _audit(
                task["task_id"], request_digest, "OUTPUT_REJECTED",
                proposal_digest=proposal_digest,
                reason=PROPOSAL_ARTIFACT_PERSISTENCE_FAILED)
            raise ProductModelFailure(
                "PROD-01 proposal artifact persistence failed.", failure_metadata) from None
    return ProductModelCycle(task, proposal, proposal_bytes, proposal_digest, metadata, artifact)


def resume_product_model_cycle(task_input, raw, *, response_metadata=None,
                               require_initial_predecessor_null=False,
                               proposal_artifact_store=None, source_checkpoint=None):
    """Complete a captured response without contacting the provider."""
    return _complete_product_model_cycle(
        task_input,
        raw,
        response_metadata=response_metadata,
        require_initial_predecessor_null=require_initial_predecessor_null,
        proposal_artifact_store=proposal_artifact_store,
        source_checkpoint=source_checkpoint,
    )


def run_product_model_cycle(task_input, transport, credential_provider=None, *,
                            require_initial_predecessor_null=False,
                            proposal_artifact_store=None, source_checkpoint=None,
                            response_capture=None):
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
                          reason=_transport_failure_reason(error),
                          provider_structure=(
                              {"http_response": bounded}
                              if (bounded := _bounded_response_metadata(
                                      getattr(error, "response_metadata", None))) is not None
                              else None))
        raise ProductModelFailure("PROD-01 model transport failed closed.", metadata) from None
    response_metadata = _bounded_response_metadata(
        getattr(transport, "response_metadata", None))
    if response_capture is not None:
        response_capture(raw, response_metadata)
    return _complete_product_model_cycle(
        task,
        raw,
        response_metadata=response_metadata,
        require_initial_predecessor_null=require_initial_predecessor_null,
        proposal_artifact_store=proposal_artifact_store,
        source_checkpoint=source_checkpoint,
    )
