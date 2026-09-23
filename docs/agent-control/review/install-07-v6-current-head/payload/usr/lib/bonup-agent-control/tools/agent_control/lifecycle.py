"""Explicit, authorized task operations. No runtime/Git/evidence execution here."""
from types import MappingProxyType

from .authority import ENGINEERS, require_context
from .records import (Approval, CandidateEvent, IntegrationCandidate, Record, Task,
                      TestEvidence, SPEC_FIELDS, task_spec_digest)
from .schema import timestamp, valid_format
from .types import ApprovalAction, AuthorityError, Role, TaskState, ValidationError

A, F, Q = Role.ARCHITECT, Role.FOUNDER, Role.INTEGRATION_QA
E = ENGINEERS

_edges = {
    ("PROPOSED", "INSPECTING"): {A},
    ("INSPECTING", "SPEC_READY"): {A},
    ("SPEC_READY", "FOUNDER_APPROVED"): {F},
    ("FOUNDER_APPROVED", "ASSIGNED"): {A},
    ("ASSIGNED", "IN_PROGRESS"): E,
    ("IN_PROGRESS", "READY_FOR_QA"): E,
    ("READY_FOR_QA", "QA_REVIEW"): {Q},
    ("QA_REVIEW", "CHANGES_REQUESTED"): {Q},
    ("CHANGES_REQUESTED", "IN_PROGRESS"): E,
    ("QA_REVIEW", "QA_PASSED"): {Q},
    ("QA_PASSED", "FOUNDER_APPROVED_FOR_INTEGRATION"): {F},
    ("FOUNDER_APPROVED_FOR_INTEGRATION", "INTEGRATED"): {F},
    ("INTEGRATED", "PUSHED"): {F},
    ("PUSHED", "CLOSED"): {F},
    ("ASSIGNED", "BLOCKED"): E | {A},
    ("IN_PROGRESS", "BLOCKED"): E | {A},
    ("QA_REVIEW", "BLOCKED"): {Q, A},
    ("IN_PROGRESS", "CONTRACT_CONFLICT"): E | {A},
    ("QA_REVIEW", "CONTRACT_CONFLICT"): {Q, A},
    ("IN_PROGRESS", "INTERRUPTED"): E | {A},
    ("QA_REVIEW", "INTERRUPTED"): {Q, A},
    ("BLOCKED", "INSPECTING"): {A},
    ("CONTRACT_CONFLICT", "INSPECTING"): {A},
    ("INTERRUPTED", "INSPECTING"): {A},
    ("INSPECTING", "ASSIGNED"): {A},
}
for _state in ("PROPOSED", "BLOCKED", "CONTRACT_CONFLICT", "INTERRUPTED", "CHANGES_REQUESTED", "QA_PASSED"):
    _edges[(_state, "ABANDONED")] = {F}
TRANSITIONS = MappingProxyType({(TaskState(a), TaskState(b)): frozenset(roles) for (a, b), roles in _edges.items()})
del _edges, _state


def validate_transition(source, target, context):
    try:
        edge = TaskState(source), TaskState(target)
    except (ValueError, TypeError):
        raise ValidationError("Unknown task state.") from None
    if edge not in TRANSITIONS:
        raise ValidationError("Illegal task transition.")
    require_context(context, roles=TRANSITIONS[edge])


def _identity(task, context):
    require_context(context)
    if context.role in ENGINEERS and context.actor_id not in task["owner_agents"]:
        raise AuthorityError("Engineer is not an owner of this task.")
    if context.role == A and context.actor_id != task["architect_agent"]:
        raise AuthorityError("Architect is not assigned to this task.")
    if context.role == Q and context.actor_id != task["qa_agent"]:
        raise AuthorityError("QA is not independently assigned to this task.")


def _now(task, now):
    if not valid_format("utc-time", now) or timestamp(now) < timestamp(task["updated_at"]):
        raise ValidationError("Operation needs a monotonic UTC timestamp.")


def _approval(approval, task, action, candidate=None):
    if type(approval) is not Approval:
        raise AuthorityError("Verified approval record required.")
    approval.assert_binding(task, action=action, candidate=candidate)


def _candidate(candidate, task):
    if type(candidate) is not IntegrationCandidate:
        raise ValidationError("Exact finalized candidate required.")
    candidate.assert_task_binding(task)
    if candidate["candidate_id"] not in task["integration_candidates"]:
        raise ValidationError("Candidate is not a submitted task candidate.")


def _qa(event, task, candidate, state, evidence):
    if type(event) is not CandidateEvent:
        raise AuthorityError("Independent candidate QA event required.")
    event.assert_binding(candidate)
    if event["state"] != state or event["actor"]["actor_id"] != task["qa_agent"]:
        raise AuthorityError("QA event does not match assigned reviewer/state.")
    if state != "QA_PASSED":
        return
    for test in candidate["required_tests"]:
        matching = []
        for item in evidence:
            if type(item) is not TestEvidence:
                raise ValidationError("Validated test evidence required.")
            d = item.to_dict()
            if (d["evidence_id"] in event["evidence"] and d["command_id"] == test["command_id"]
                    and d["test_definition_digest"] == test["definition_digest"]):
                item.assert_binding(task_id=task["task_id"], candidate_id=candidate["candidate_id"],
                    tested_commit=candidate["prepared_integration_commit"], tested_tree=candidate["prepared_tree"],
                    spec_digest=task["spec_digest"], test_definition_digest=test["definition_digest"],
                    execution_id=d["execution_id"], environment_profile_digest=d["environment_profile_digest"])
                if d["result"] == "PASS" and d["recorded_by"]["actor_id"] == task["qa_agent"]:
                    matching.append(item)
        if not matching:
            raise ValidationError("Required exact-candidate independent QA evidence is missing.")


def transition_task(task, target, context, *, now, approval=None, candidate=None,
                    qa_event=None, evidence=(), recovery=None, reason=None):
    """Return a new Task; facts needing OS/Git validation remain future-controller inputs."""
    validate_transition(task["state"], target, context)
    _identity(task, context)
    _now(task, now)
    source, target = TaskState(task["state"]), TaskState(target)
    data = task.to_dict()
    if target == TaskState.SPEC_READY:
        data["spec_frozen"] = True
    if target == TaskState.FOUNDER_APPROVED:
        _approval(approval, task, ApprovalAction.APPROVE_SPEC)
        data["approved_by"] = context.actor()
        data["founder_approval"] = approval["approval_id"]
    if target == TaskState.ASSIGNED:
        _approval(approval, task, ApprovalAction.APPROVE_SPEC)
        if task["founder_approval"] != approval["approval_id"] or not task["assignments"] or set(task["owner_agents"]) != {a["owner_agent"] for a in task["assignments"]}:
            raise ValidationError("Assignment requires all owners and the current approval.")
    if source in {TaskState.BLOCKED, TaskState.CONTRACT_CONFLICT, TaskState.INTERRUPTED} or (source == TaskState.INSPECTING and target == TaskState.ASSIGNED):
        if type(recovery) is not Record or recovery["kind"] != "DECISION" or recovery["status"] != "RESOLVED" or recovery["task_id"] != task["task_id"]:
            raise AuthorityError("Explicit resolved recovery/inspection decision required.")
        if recovery["record_id"] not in data["decisions"]:
            data["decisions"].append(recovery["record_id"])
    if target in {TaskState.BLOCKED, TaskState.CONTRACT_CONFLICT, TaskState.INTERRUPTED, TaskState.ABANDONED} and (type(reason) is not str or not reason.strip()):
        raise ValidationError("Exceptional transitions require an explicit reason.")
    if target == TaskState.READY_FOR_QA and (not task["owner_agents"] or set(task["owner_agents"]) != {c["agent_id"] for c in task["commits"]}):
        raise ValidationError("Every owner must have submitted commit metadata.")
    if target in {TaskState.QA_REVIEW, TaskState.CHANGES_REQUESTED, TaskState.QA_PASSED, TaskState.FOUNDER_APPROVED_FOR_INTEGRATION, TaskState.INTEGRATED, TaskState.PUSHED}:
        _candidate(candidate, task)
    if target in {TaskState.CHANGES_REQUESTED, TaskState.QA_PASSED}:
        _qa(qa_event, task, candidate, target.value, evidence)
    if target in {TaskState.FOUNDER_APPROVED_FOR_INTEGRATION, TaskState.INTEGRATED}:
        _qa(qa_event, task, candidate, "QA_PASSED", evidence)
        _approval(approval, task, ApprovalAction.APPROVE_INTEGRATION, candidate)
        if target == TaskState.INTEGRATED and task["integration_approval"] != approval["approval_id"]:
            raise ValidationError("Integration approval was replaced.")
        data["integration_approval"] = approval["approval_id"]
    if target == TaskState.PUSHED:
        _approval(approval, task, ApprovalAction.APPROVE_PUSH, candidate)
    if target in {TaskState.CLOSED, TaskState.ABANDONED}:
        if type(reason) is not str or not reason.strip():
            raise ValidationError("Terminal transitions require a close reason.")
        data["close_reason"] = reason
    data["state"] = target.value
    data["record_revision"] += 1
    data["updated_at"] = now
    return Task(data)


def revise_spec(task, changes, context, *, now):
    """Architect creates a new unfrozen version; never edits an approved version in place."""
    require_context(context, roles={A}, actor_id=task["architect_agent"])
    _now(task, now)
    if task["state"] not in {"PROPOSED", "INSPECTING", "SPEC_READY", "BLOCKED", "CONTRACT_CONFLICT", "INTERRUPTED", "CHANGES_REQUESTED"}:
        raise AuthorityError("Stop/reconcile active work before revising its specification.")
    allowed = set(SPEC_FIELDS) - {"task_id", "task_uuid", "spec_version"}
    if type(changes) is not dict or not changes or not set(changes) <= allowed:
        raise ValidationError("Invalid specification revision fields.")
    data = task.to_dict()
    data.update(changes)
    data.update(spec_version=data["spec_version"] + 1, spec_frozen=False,
                founder_approval=None, integration_approval=None, approved_by=None,
                state="INSPECTING", updated_at=now, record_revision=data["record_revision"] + 1)
    data["spec_digest"] = task_spec_digest(data)
    return Task(data)
