"""Deterministic human-readable projection of an authoritative Agent Control task.

The projection is deliberately not a control record.  It cannot authorize work,
change task state, or replace registry, audit, approval, grant, or evidence data.
"""
import re

from .records import Task
from .schema import timestamp, valid_format
from .serialization import canonical_json
from .types import ValidationError

_FIELDS = (
    "background", "inputs", "plan", "work_performed", "artifacts",
    "validation", "result", "evidence_references", "started_at", "completed_at",
)
_LIST_FIELDS = {"inputs", "plan", "work_performed", "artifacts", "validation"}
_MAX_TEXT = 4096
_MAX_ITEMS = 100
_MAX_REFERENCES = 100
_REFERENCE_KEYS = {"kind", "identifier", "digest", "path"}

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|ghp|xox[baprs])-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?im)^\s*[A-Za-z_][A-Za-z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY)[A-Za-z0-9_]*\s*=\s*\S+"),
    re.compile(r"(?i)\b(?:password|api[_ -]?key|private[_ -]?key|client[_ -]?secret)\s*[:=]\s*\S+"),
)

_DOCUMENT_STATUS = {
    "PROPOSED": "CREATED",
    "INSPECTING": "CREATED",
    "SPEC_READY": "CREATED",
    "FOUNDER_APPROVED": "CREATED",
    "ASSIGNED": "CREATED",
    "IN_PROGRESS": "IN_PROGRESS",
    "READY_FOR_QA": "IN_PROGRESS",
    "QA_REVIEW": "IN_PROGRESS",
    "CHANGES_REQUESTED": "IN_PROGRESS",
    "QA_PASSED": "IN_PROGRESS",
    "FOUNDER_APPROVED_FOR_INTEGRATION": "IN_PROGRESS",
    "INTEGRATED": "IN_PROGRESS",
    "PUSHED": "IN_PROGRESS",
    "BLOCKED": "BLOCKED",
    "CONTRACT_CONFLICT": "BLOCKED",
    "INTERRUPTED": "BLOCKED",
    "CLOSED": "COMPLETED",
    "ABANDONED": "FAILED",
}


def _text(value, location, *, optional=False):
    if value is None and optional:
        return None
    if type(value) is not str or not value.strip() or len(value) > _MAX_TEXT:
        raise ValidationError(f"Invalid bounded task document field: {location}.")
    value = value.strip()
    if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
        raise ValidationError("Task documents cannot contain secrets or raw environment data.")
    return value


def _items(value, location):
    if type(value) is not list or len(value) > _MAX_ITEMS:
        raise ValidationError(f"Invalid bounded task document field: {location}.")
    return [_text(item, f"{location}[]") for item in value]


def _references(value):
    if type(value) is not list or len(value) > _MAX_REFERENCES:
        raise ValidationError("Invalid bounded task document evidence references.")
    result = []
    for reference in value:
        if type(reference) is not dict or set(reference) != _REFERENCE_KEYS:
            raise ValidationError("Malformed task document evidence reference.")
        item = {key: _text(reference[key], f"evidence_references[].{key}", optional=True)
                for key in sorted(_REFERENCE_KEYS)}
        if item["identifier"] is None or all(item[key] is None for key in ("digest", "path")):
            raise ValidationError("Evidence reference needs an identifier and digest or path.")
        if item["digest"] is not None and not valid_format("sha256", item["digest"]):
            raise ValidationError("Evidence reference digest must be SHA-256.")
        result.append(item)
    return sorted(result, key=lambda item: canonical_json(item))


def _bullet_section(title, values):
    body = "\n".join(f"- {value}" for value in values) if values else "None recorded."
    return f"## {title}\n\n{body}"


def _rule_text(label, rules):
    return [f"{label}: {rule['kind']} `{rule['path']}`" for rule in rules]


def render_task_document(task, summary):
    """Return Markdown; never persist or mutate authoritative state."""
    if type(task) is not Task:
        raise ValidationError("A validated authoritative Task record is required.")
    if type(summary) is not dict or set(summary) != set(_FIELDS):
        raise ValidationError("Task document summary fields are incomplete or unexpected.")

    data = task.to_dict()
    # agent_id is intentionally absent from accepted summary keys: ownership is
    # projected from the authoritative task, never asserted by document input.
    owners = data["owner_agents"] or [data["architect_agent"]]
    normalized = {}
    for field in _FIELDS:
        if field in _LIST_FIELDS:
            normalized[field] = _items(summary[field], field)
        elif field == "evidence_references":
            normalized[field] = _references(summary[field])
        elif field in {"started_at", "completed_at"}:
            normalized[field] = _text(summary[field], field, optional=True)
            if normalized[field] is not None and not valid_format("utc-time", normalized[field]):
                raise ValidationError("Task document timestamps must be UTC timestamps.")
        else:
            normalized[field] = _text(summary[field], field)

    started, completed = normalized["started_at"], normalized["completed_at"]
    if completed is not None and started is None:
        raise ValidationError("Completed task documents require a start timestamp.")
    if completed is not None and timestamp(completed) < timestamp(started):
        raise ValidationError("Task document timestamps are out of order.")
    if completed is not None and data["state"] not in {"CLOSED", "ABANDONED"}:
        raise ValidationError("Only terminal authoritative tasks may be completed.")

    for value in (data["title"], data["objective"]):
        _text(value, "authoritative_task")
    status = _DOCUMENT_STATUS[data["state"]]
    metadata = {
        "agent_ids": owners,
        "authoritative_state": data["state"],
        "document_status": status,
        "record_revision": data["record_revision"],
        "schema_version": 1,
        "spec_digest": data["spec_digest"],
        "spec_version": data["spec_version"],
        "task_id": data["task_id"],
        "task_uuid": data["task_uuid"],
    }
    refs = [f"- {r['kind']}: {r['identifier']}"
            + (f" (sha256:{r['digest']})" if r["digest"] else "")
            + (f" — `{r['path']}`" if r["path"] else "")
            for r in normalized["evidence_references"]]
    constraints = [
        f"Authoritative policy digest: `{data['policy_digest']}`",
        *_rule_text("Allowed write", data["allowed_write_paths"]),
        *_rule_text("Read only", data["read_only_paths"]),
        *_rule_text("Forbidden", data["forbidden_paths"]),
        "This document grants no authority; authoritative task, grant, fencing, approval, audit, and evidence records control execution.",
    ]
    sections = [
        "<!-- bonUP agent task document metadata\n" + canonical_json(metadata) + "\n-->",
        f"# {data['task_id']} — {data['title']}",
        "**HUMAN-READABLE PROJECTION — NOT EXECUTION AUTHORITY**",
        f"**Agent:** {', '.join(owners)}  \n**Document status:** {status}  \n**Authoritative task state:** {data['state']}  \n**Started at:** {normalized['started_at'] or 'Not recorded'}  \n**Completed at:** {normalized['completed_at'] or 'Not recorded'}",
        f"## Objective\n\n{data['objective']}",
        f"## Background / Why\n\n{normalized['background']}",
        _bullet_section("Inputs", normalized["inputs"]),
        _bullet_section("Authority / Constraints", constraints),
        _bullet_section("Plan", normalized["plan"]),
        _bullet_section("Work Performed", normalized["work_performed"]),
        _bullet_section("Artifacts", normalized["artifacts"]),
        _bullet_section("Validation / Tests", normalized["validation"]),
        f"## Result\n\n{normalized['result']}",
        "## Evidence References\n\n" + ("\n".join(refs) if refs else "None recorded."),
    ]
    return "\n\n".join(sections) + "\n"
