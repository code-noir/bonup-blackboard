"""Read-only command for projecting an authoritative task to repository Markdown."""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from .registry import Registry
from .serialization import digest, parse_json
from .task_document import render_task_document
from .types import ValidationError

_TASK_ID = re.compile(r"ATS-(?:[0-9]{4}|[1-9][0-9]{4,})")
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCUMENT_ROOT = _REPO_ROOT / "docs" / "agent-tasks"
_METADATA_START = "<!-- bonUP agent task document metadata\n"
_METADATA_END = "\n-->"


def _validate_task_id(task_id):
    if type(task_id) is not str or not _TASK_ID.fullmatch(task_id):
        raise ValidationError("Malformed task ID.")
    return task_id


def _evidence_references(registry, task):
    data = task.to_dict()
    ids = list(data["validation_results"])
    if data["handoff"] is not None:
        ids.extend(data["handoff"]["validation"])
    references = []
    for evidence_id in sorted(set(ids)):
        evidence = registry.load("TestEvidence", evidence_id)
        if evidence["task_id"] != data["task_id"] or evidence["spec_digest"] != data["spec_digest"]:
            raise ValidationError("Evidence is not bound to the current task specification.")
        references.append({
            "kind": "TEST_EVIDENCE",
            "identifier": evidence_id,
            "digest": digest(evidence.to_dict()),
            "path": f"evidence/{evidence_id}.json",
        })
    return references


def _changed_paths(task):
    paths = []
    for change in task["changed_files"]:
        path = change["new_path"] if change["new_path"] is not None else change["old_path"]
        if path not in paths:
            paths.append(path)
    handoff = task["handoff"]
    if handoff is not None:
        for path in handoff["changed_files"]:
            if path not in paths:
                paths.append(path)
    return paths


def authoritative_summary(registry, task):
    """Build narrative solely from fields already carried by trusted records."""
    handoff = task["handoff"]
    evidence = _evidence_references(registry, task)
    completed = handoff["completed"] if handoff is not None else []
    current = handoff["current"] if handoff is not None else []
    remaining = handoff["remaining"] if handoff is not None else []
    validation = [f"{item['identifier']} (referenced authoritative evidence)" for item in evidence]
    if not validation:
        validation = []
    result = task["close_reason"] or "No authoritative result is recorded."
    return {
        "background": "No separate authoritative background is recorded; see the objective and acceptance criteria.",
        "inputs": [f"Source base commit: {task['source_base_commit']}"]
                  + [f"Dependency: {item['task_id']}" for item in task["dependencies"]],
        "plan": list(task["acceptance_criteria"]),
        "work_performed": list(completed) + [f"Current: {item}" for item in current]
                          + [f"Remaining: {item}" for item in remaining],
        "artifacts": _changed_paths(task),
        "validation": validation,
        "result": result,
        "evidence_references": evidence,
        "started_at": None,
        "completed_at": None,
    }


def _existing_metadata(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith(_METADATA_START):
        raise ValidationError("Existing task document lacks trusted projection metadata.")
    end = text.find(_METADATA_END, len(_METADATA_START))
    if end < 0:
        raise ValidationError("Existing task document metadata is malformed.")
    value = parse_json(text[len(_METADATA_START):end])
    required = {"task_id", "task_uuid", "record_revision", "spec_digest"}
    if type(value) is not dict or not required <= set(value):
        raise ValidationError("Existing task document binding is incomplete.")
    return value, text


def _safe_destination(root, task_id):
    root = Path(root)
    if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
        raise ValidationError("Task document directory cannot traverse symbolic links.")
    root.mkdir(parents=True, exist_ok=True)
    resolved = root.resolve(strict=True)
    destination = resolved / f"{task_id}.md"
    if destination.parent != resolved or destination.is_symlink():
        raise ValidationError("Unsafe task document destination.")
    return destination


def _write_projection(path, rendered, task):
    if path.exists():
        metadata, existing = _existing_metadata(path)
        if existing == rendered:
            return "UNCHANGED"
        if metadata["task_id"] != task["task_id"] or metadata["task_uuid"] != task["task_uuid"]:
            raise ValidationError("Existing task document belongs to another task identity.")
        if type(metadata["record_revision"]) is not int or metadata["record_revision"] >= task["record_revision"]:
            raise ValidationError("Refusing stale or conflicting task document overwrite.")
    temporary = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{task['task_id']}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValidationError("Unsafe task document destination.")
        os.replace(temporary, path)
        temporary = None
        return "WRITTEN"
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def project_task_document(registry, task_id, *, document_root=_DOCUMENT_ROOT):
    """Read trusted records and atomically write one bounded projection."""
    task_id = _validate_task_id(task_id)
    task = registry.get_task(task_id)
    if task["task_id"] != task_id:
        raise ValidationError("Loaded task identity does not match the request.")
    rendered = render_task_document(task, authoritative_summary(registry, task))
    destination = _safe_destination(document_root, task_id)
    outcome = _write_projection(destination, rendered, task)
    return {"status": outcome, "task_id": task_id,
            "record_revision": task["record_revision"],
            "spec_digest": task["spec_digest"],
            "path": f"docs/agent-tasks/{task_id}.md"}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tools.agent_control.task_document_project")
    parser.add_argument("--state", required=True, help="Explicit authoritative Agent Control registry path")
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args(argv)
    try:
        with Registry(args.state) as registry:
            if registry.verify()["status"] == "BLOCKED":
                raise ValidationError("Registry is blocked.")
            result = project_task_document(registry, args.task_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValidationError, sqlite3.DatabaseError, OSError, KeyError, TypeError):
        print(json.dumps({"status": "BLOCKED", "error": "Task document projection rejected."}),
              file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
