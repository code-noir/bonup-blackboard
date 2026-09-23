"""Bounded PROD-01 proposal contract. This module grants no authority."""
from functools import lru_cache
from pathlib import Path
import re

from .schema import valid_format
from .serialization import canonical_json, digest, parse_json
from .types import ValidationError

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "agents" / "contracts" / "PROD-01.json"
TASK_CLASSES = (
    "PRODUCT_REQUIREMENT", "FEATURE_DEFINITION", "ACCEPTANCE_INTENT",
    "PRODUCT_GAP_ANALYSIS", "PRIORITIZATION_RECOMMENDATION", "USER_FLOW_REQUIREMENT",
)
REFERENCE_TYPES = (
    "FOUNDER_DIRECTION", "APPROVED_INTERNAL_KNOWLEDGE", "CX_FINDING", "BI_FINDING",
    "PRODUCT_DOCUMENT", "TASK_DOCUMENT", "ARCHITECTURE_CONTEXT",
)
TASK_FIELDS = {"agent_id", "task_id", "task_class", "objective", "input_references"}
PROPOSAL_FIELDS = {
    "agent_id", "task_id", "proposal_id", "proposal_type", "title", "problem_user_need",
    "objective", "proposed_requirement", "acceptance_intent", "dependencies", "assumptions",
    "risks_open_questions", "priority_recommendation", "evidence_references", "knowledge_state",
    "predecessor_proposal_id",
}
REFERENCE_FIELDS = {"reference_type", "reference_id", "digest", "knowledge_state"}
LIST_FIELDS = {"acceptance_intent", "assumptions", "risks_open_questions"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
_REFERENCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|ghp|xox[baprs])-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(?:password|api[_ -]?key|private[_ -]?key|client[_ -]?secret)\s*[:=]\s*\S+"),
)
_AUTHORITY_STATUS = r"(?:approved|assigned|authorized|deployed|implemented|tested|published|complete|completed|passed)"
_AUTHORITY_QUALIFIER = r"(?:already|currently|successfully|now|fully|finally|all)"
_AUTHORITY_SUBJECT = (
    r"(?:this(?:\s+(?:feature|implementation|deployment|execution|task|proposal|"
    r"requirement|code|system|change))?|"
    r"(?:the|a|an)\s+(?:feature|implementation|deployment|execution|task|proposal|"
    r"requirement|code|system|change|tests?|test\s+suite|checks?|validation)|"
    r"(?:feature|implementation|deployment|execution|task|proposal|requirement|"
    r"code|system|change|tests?|test\s+suite|checks?|validation))"
)
_AUTHORITY_CLAIM = re.compile(
    rf"^(?:already\s+)?{_AUTHORITY_STATUS}\b|"
    rf"\b{_AUTHORITY_SUBJECT}\s+(?:"
    rf"(?:is|are|was|were)\s+(?:not\s+)?(?:{_AUTHORITY_QUALIFIER}\s+)?|"
    rf"(?:has|have|had)\s+(?:not\s+)?(?:{_AUTHORITY_QUALIFIER}\s+)?"
    rf"(?:been\s+)?(?:{_AUTHORITY_QUALIFIER}\s+)?|"
    rf"{_AUTHORITY_QUALIFIER}\s+|"
    rf"){_AUTHORITY_STATUS}\b",
    re.IGNORECASE,
)
_HYPOTHETICAL_STATUS_CONTEXT = re.compile(
    r"(?:^|\s)(?:whether|if|when|before|after|until|once|that)\s+"
    r"(?:this|that|the|a|an)?\s*$",
    re.IGNORECASE,
)


def _reject(message):
    raise ValidationError(message)


def _safe_text(value, field, *, maximum=4096):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        _reject(f"Invalid bounded PROD-01 text field: {field}.")
    value = value.strip()
    if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
        _reject("PROD-01 content cannot contain secrets or credentials.")
    return value


def _proposal_text(value, field):
    value = _safe_text(value, field)
    authority_text = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE).strip()
    if any(
            not _HYPOTHETICAL_STATUS_CONTEXT.search(authority_text[:match.start()])
            for match in _AUTHORITY_CLAIM.finditer(authority_text)):
        _reject("PROD-01 proposal cannot claim approval, authority, execution, or publication.")
    return value


def _exact_fields(value, fields, subject):
    if type(value) is not dict or set(value) != fields:
        _reject(f"Malformed PROD-01 {subject} fields.")


@lru_cache(maxsize=1)
def load_contract():
    contract = parse_json(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = {
        "agent_id", "authority_mode", "contract_version", "external_research", "handoff",
        "input_contract", "knowledge", "mission", "output_contract", "permissions", "role",
        "role_family", "status", "task_classes",
    }
    _exact_fields(contract, expected, "contract")
    if (contract["contract_version"] != 1 or contract["agent_id"] != "PROD-01"
            or contract["role"] != "Product" or contract["role_family"] != "PRODUCT"
            or contract["status"] != "NON_ACTIVE"
            or contract["authority_mode"] != "PROPOSAL_ONLY"):
        _reject("PROD-01 identity or proposal-only status mismatch.")
    if tuple(contract["task_classes"]) != TASK_CLASSES:
        _reject("PROD-01 task-class contract mismatch.")
    if tuple(contract["input_contract"]["allowed_reference_types"]) != REFERENCE_TYPES:
        _reject("PROD-01 input-reference contract mismatch.")
    if (set(contract["output_contract"]["proposal_fields"]) != PROPOSAL_FIELDS
            or contract["output_contract"]["proposal_type"] != "PRODUCT_REQUIREMENT_PROPOSAL"):
        _reject("PROD-01 proposal contract mismatch.")
    if (not contract["permissions"] or any(value is not False for value in contract["permissions"].values())):
        _reject("PROD-01 contract must not contain execution or system permissions.")
    if contract["knowledge"] != {"allowed_output_state": "WORKING", "self_approval": False,
                                  "self_publication_eligibility": False}:
        _reject("PROD-01 knowledge-state contract mismatch.")
    return parse_json(canonical_json(contract))


def contract_digest():
    return digest(load_contract())


def _reference(value):
    _exact_fields(value, REFERENCE_FIELDS, "reference")
    if value["reference_type"] not in REFERENCE_TYPES:
        _reject("Unknown PROD-01 input reference type.")
    if not _REFERENCE_ID.fullmatch(value["reference_id"]):
        _reject("Invalid bounded PROD-01 reference identity.")
    if not valid_format("sha256", value["digest"]):
        _reject("PROD-01 reference requires a SHA-256 digest.")
    required_state = "DIRECT_FOUNDER" if value["reference_type"] == "FOUNDER_DIRECTION" else "APPROVED_INTERNAL"
    if value["knowledge_state"] != required_state:
        _reject("PROD-01 input is not at the required knowledge level.")
    return parse_json(canonical_json(value))


def _references(values, field):
    limit = load_contract()["input_contract"]["max_references"]
    if type(values) is not list or len(values) > limit:
        _reject(f"Invalid bounded PROD-01 reference list: {field}.")
    return [_reference(value) for value in values]


def validate_product_task(value):
    """Validate a non-executable PROD-01 task description; create no Task record."""
    load_contract()
    _exact_fields(value, TASK_FIELDS, "task")
    if value["agent_id"] != "PROD-01" or not valid_format("task-id", value["task_id"]):
        _reject("PROD-01 task identity mismatch.")
    if value["task_class"] not in TASK_CLASSES:
        _reject("Unknown PROD-01 task class.")
    result = parse_json(canonical_json(value))
    result["objective"] = _safe_text(value["objective"], "objective")
    result["input_references"] = _references(value["input_references"], "input_references")
    return parse_json(canonical_json(result))


def validate_product_proposal(value):
    """Validate WORKING proposal output; approval and authority fields are invalid."""
    contract = load_contract()
    _exact_fields(value, PROPOSAL_FIELDS, "proposal")
    if (value["agent_id"] != "PROD-01" or not valid_format("task-id", value["task_id"])
            or not valid_format("uuid", value["proposal_id"])):
        _reject("PROD-01 proposal identity mismatch.")
    if value["proposal_type"] != contract["output_contract"]["proposal_type"]:
        _reject("Unknown PROD-01 proposal type.")
    predecessor = value["predecessor_proposal_id"]
    if predecessor is not None and (not valid_format("uuid", predecessor)
                                    or predecessor == value["proposal_id"]):
        _reject("Invalid PROD-01 predecessor proposal identity.")
    if value["knowledge_state"] != "WORKING":
        _reject("PROD-01 cannot self-promote proposal knowledge.")
    if value["priority_recommendation"] not in PRIORITIES:
        _reject("Invalid PROD-01 priority recommendation.")
    result = parse_json(canonical_json(value))
    for field in ("title", "problem_user_need", "objective", "proposed_requirement"):
        result[field] = _proposal_text(value[field], field)
    maximum = contract["output_contract"]["max_list_items"]
    for field in LIST_FIELDS:
        items = value[field]
        if type(items) is not list or len(items) > maximum:
            _reject(f"Invalid bounded PROD-01 list: {field}.")
        result[field] = [_proposal_text(item, f"{field}[]") for item in items]
    dependencies = value["dependencies"]
    if type(dependencies) is not list or len(dependencies) > maximum or any(
            not valid_format("task-id", item) for item in dependencies):
        _reject("Invalid PROD-01 task dependencies.")
    if len(set(dependencies)) != len(dependencies):
        _reject("Duplicate PROD-01 task dependency.")
    result["evidence_references"] = _references(value["evidence_references"], "evidence_references")
    return parse_json(canonical_json(result))
