"""Immutable validated records. All inputs/exports are detached JSON values.

These definitions do not establish persistence uniqueness, authentic evidence,
Git ancestry, resource acquisition, or Unix authentication. Explicit binding and
authority functions must be used by the future trusted controller.
"""
from .authority import (ENGINEERS, authorize_resolution, authorize_resource,
                        phase_one_role, require_context, validate_actor,
                        validate_write_scope)
from .paths import PathRule, contained_by, overlaps, permits_write
from .schema import document, timestamp, validate_schema
from .serialization import canonical_json, digest, parse_json
from .types import ApprovalAction, AuthorityError, Role, TaskState, ValidationError

SPEC_FIELDS = (
    "task_id", "task_uuid", "title", "objective", "acceptance_criteria", "priority",
    "spec_version", "policy_digest", "source_base_commit", "allowed_write_paths",
    "read_only_paths", "forbidden_paths", "dependencies", "required_resources",
    "required_tests", "budget",
)


def _walk(data):
    if type(data) is dict:
        if set(data) == {"kind", "path"}:
            if PathRule.from_dict(data).to_dict() != data:
                raise ValidationError("Record path rules must be normalized.")
        if set(data) == {"status", "old_path", "new_path", "old_blob", "new_blob", "old_mode", "new_mode"}:
            old = [data[k] for k in ("old_path", "old_blob", "old_mode")]
            new = [data[k] for k in ("new_path", "new_blob", "new_mode")]
            old_ok = all(v is None for v in old) if data["status"] == "ADD" else all(v is not None for v in old)
            new_ok = all(v is None for v in new) if data["status"] == "DELETE" else all(v is not None for v in new)
            if not old_ok or not new_ok:
                raise ValidationError("Change metadata must identify complete before/after sides.")
            if data["status"] == "RENAME" and old[0] == new[0]:
                raise ValidationError("Rename requires different paths.")
            if data["status"] in {"MODIFY", "TYPE_CHANGE"} and old[0] != new[0]:
                raise ValidationError("Path change must be represented as a rename.")
        if set(data) == {"actor_id", "role"}:
            validate_actor(data)
        for value in data.values():
            _walk(value)
    elif type(data) is list:
        for value in data:
            _walk(value)


def _ordered(data, *fields):
    values = [timestamp(data[k]) for k in fields if data[k] is not None]
    if values != sorted(values):
        raise ValidationError("Record timestamps are out of order.")


def _rules(data, key):
    return [PathRule.from_dict(p) for p in data[key]]


def _same(data, **expected):
    if any(data[key] != value for key, value in expected.items()):
        raise ValidationError("Record binding does not match the exact subject.")


def _candidate_task(candidate_id, task_id):
    if candidate_id is not None and candidate_id.rsplit("-", 1)[0] != "IC-" + task_id:
        raise ValidationError("Candidate belongs to another task.")


def _resource(data):
    configured = document("policy.json")["resources"][data["resource_type"]]
    if data["mode"] != configured["mode"] or data["units"] != 1:
        raise ValidationError("Phase I resources require exclusive single-unit reservations.")


def task_spec_digest(data):
    return digest({key: data[key] for key in SPEC_FIELDS})


class ImmutableRecord:
    __slots__ = ("_payload",)
    schema_name = ""

    def __init__(self, data, *, context=None):
        detached = parse_json(canonical_json(data))
        validate_schema(self.schema_name, detached)
        _walk(detached)
        self._validate(detached, context)
        object.__setattr__(self, "_payload", canonical_json(detached))

    def __setattr__(self, name, value):
        raise ValidationError("Records are immutable; use an authorized domain operation.")

    def __delattr__(self, name):
        raise ValidationError("Records are immutable.")

    def _validate(self, data, context):
        pass

    def to_dict(self):
        return parse_json(self._payload)

    def canonical_json(self):
        return self._payload

    def __getitem__(self, key):
        return self.to_dict()[key]


class Task(ImmutableRecord):
    __slots__ = ()
    schema_name = "Task"

    def _validate(self, d, context):
        _ordered(d, "created_at", "updated_at")
        if d["architect_agent"] != "ARCH-01" or d["qa_agent"] != "QA-01":
            raise AuthorityError("Task requires Phase I Architect and independent QA.")
        if any(owner not in {"FE-01", "BE-01"} for owner in d["owner_agents"]):
            raise AuthorityError("Task owners must be Phase I engineers.")
        if task_spec_digest(d) != d["spec_digest"]:
            raise ValidationError("Task specification digest mismatch.")
        if d["approved_by"] is not None and d["approved_by"]["role"] != "FOUNDER":
            raise AuthorityError("Only founder may be the task approver.")
        if any(dep["task_id"] == d["task_id"] for dep in d["dependencies"]):
            raise ValidationError("Task cannot depend on itself.")
        for dep in d["dependencies"]:
            _candidate_task(dep["accepted_candidate_id"], dep["task_id"])
        for candidate in d["integration_candidates"]:
            _candidate_task(candidate, d["task_id"])
        for field, prefix in [("findings", "FINDING-"), ("conflicts", "CONFLICT-"), ("decisions", "DECISION-")]:
            if any(not value.startswith(prefix) for value in d[field]):
                raise ValidationError("Record reference kind mismatch.")
        for request in d["required_resources"]:
            _resource(request)
        if len({a["owner_agent"] for a in d["assignments"]}) != len(d["assignments"]):
            raise ValidationError("Duplicate task assignment.")
        for assignment in d["assignments"]:
            owner = assignment["owner_agent"]
            if owner not in d["owner_agents"]:
                raise AuthorityError("Assignment owner is not a task owner.")
            role = document("policy.json")["agents"][owner]
            scope = _rules(assignment, "allowed_write_paths")
            validate_write_scope(scope, phase_one_role(owner, role))
            for rule in scope:
                if not any(contained_by(rule, parent) for parent in _rules(d, "allowed_write_paths")):
                    raise AuthorityError("Assignment exceeds approved task scope.")
                if any(overlaps(rule, deny) for deny in _rules(d, "forbidden_paths") + _rules(d, "read_only_paths")):
                    raise AuthorityError("Assignment overlaps a denied scope.")
            _same(assignment, branch=d["branch"].get(owner), worktree=d["worktree"].get(owner))
        for index, assignment in enumerate(d["assignments"]):
            for other in d["assignments"][index + 1:]:
                if any(overlaps(a, b) for a in _rules(assignment, "allowed_write_paths")
                       for b in _rules(other, "allowed_write_paths")):
                    raise AuthorityError("Assignments must have exclusive writable scopes.")
        if (d["approved_by"] is None) != (d["founder_approval"] is None):
            raise ValidationError("Task approver and approval reference must be paired.")
        for mapping in (d["branch"], d["worktree"]):
            if set(mapping) != {a["owner_agent"] for a in d["assignments"]}:
                raise ValidationError("Task workspace maps must match assignments.")
        if any(c["agent_id"] not in d["owner_agents"] for c in d["commits"]):
            raise AuthorityError("Commit metadata belongs to another owner.")
        if d["state"] == "CLOSED" and not d["close_reason"]:
            raise ValidationError("Closed task needs a close reason.")
        if d["state"] not in {"PROPOSED", "INSPECTING", "BLOCKED", "CONTRACT_CONFLICT", "INTERRUPTED", "ABANDONED"} and not d["spec_frozen"]:
            raise ValidationError("Task state requires a frozen specification.")


class AgentRecord(ImmutableRecord):
    __slots__ = ()
    schema_name = "AgentRecord"

    def _validate(self, d, context):
        policy = phase_one_role(d["agent_id"], d["role"])
        if not set(d["capabilities"]) <= set(policy["capabilities"]):
            raise AuthorityError("Agent capability escalation.")
        if d["max_concurrency"] != 1 or d["policy_version"] != document("policy.json")["policy_version"]:
            raise AuthorityError("Agent concurrency/policy version is not enabled.")
        validate_write_scope(_rules(d, "default_write_scope"), policy)
        if d["status"] in {"ASSIGNED", "RUNNING", "INTERRUPTED"} and d["current_task"] is None:
            raise ValidationError("Active agent must identify its task.")
        if any(s["agent_id"] != d["agent_id"] for s in d["session_ids"]):
            raise AuthorityError("Session belongs to another agent.")


class ExecutionGrant(ImmutableRecord):
    __slots__ = ()
    schema_name = "ExecutionGrant"

    def _validate(self, d, context):
        policy = phase_one_role(d["agent_id"], d["role"])
        for capability in ("can_commit_local", "can_push", "can_merge", "can_change_task_spec"):
            if d[capability] and not policy[capability]:
                raise AuthorityError("Execution capability escalation.")
        validate_write_scope(_rules(d, "can_write"), policy)

    def assert_task_binding(self, task):
        d, t = self.to_dict(), task.to_dict()
        _same(d, task_id=t["task_id"], spec_version=t["spec_version"], spec_digest=t["spec_digest"])
        if not t["spec_frozen"] or not t["founder_approval"]:
            raise AuthorityError("Execution requires an approved frozen specification.")
        if d["role"] in {r.value for r in ENGINEERS}:
            assignment = next((a for a in t["assignments"] if a["owner_agent"] == d["agent_id"]), None)
            if assignment is None:
                raise AuthorityError("Engineer has no task assignment.")
            _same(d, branch=assignment["branch"], worktree=assignment["worktree"])
            for rule in _rules(d, "can_write"):
                if not any(contained_by(rule, parent) for parent in _rules(assignment, "allowed_write_paths")):
                    raise AuthorityError("Grant exceeds assigned scope.")
        elif d["agent_id"] not in {t["qa_agent"], t["architect_agent"]}:
            raise AuthorityError("Grant is not assigned to this task.")
        if not set(d["reserved_resources"]) <= set(t["resource_reservations"]):
            raise AuthorityError("Grant contains an unbound reservation.")


class Reservation(ImmutableRecord):
    __slots__ = ()
    schema_name = "Reservation"

    def _validate(self, d, context):
        _resource(d)
        authorize_resource(d["resource_type"], context)
        _ordered(d, "acquired_at", "renewed_at", "lease_expires_at")
        if timestamp(d["lease_expires_at"]) <= timestamp(d["renewed_at"]):
            raise ValidationError("Reservation lease must extend beyond renewal.")


class Record(ImmutableRecord):
    __slots__ = ()
    schema_name = "Record"

    def _validate(self, d, context):
        if not d["record_id"].startswith(d["kind"] + "-"):
            raise ValidationError("Record ID/kind mismatch.")
        require_context(context)
        if d["type"] not in {"TECHNICAL", "INTERFACE"} and d["decision_scope"] != "POLICY":
            raise AuthorityError("Scope/product/security/budget decisions require policy authority.")
        if d["status"] == "OPEN":
            require_context(context, actor_id=d["raised_by"]["actor_id"])
            if any(d[k] is not None for k in ("resolution", "resolved_by", "resolved_at")):
                raise ValidationError("Open recommendation cannot claim a resolution.")
        else:
            authorize_resolution(d, context)
            if not d["resolution"] or not d["resolved_at"] or d["resolved_by"] != context.actor():
                raise AuthorityError("Resolution must identify its authenticated resolver.")
            _ordered(d, "created_at", "resolved_at")


class IntegrationCandidate(ImmutableRecord):
    __slots__ = ()
    schema_name = "IntegrationCandidate"

    def _validate(self, d, context):
        _candidate_task(d["candidate_id"], d["task_id"])
        body = {k: v for k, v in d.items() if k != "manifest_digest"}
        if digest(body) != d["manifest_digest"]:
            raise ValidationError("Candidate manifest digest mismatch.")
        owners = []
        for implementation in d["implementations"]:
            phase_one_role(implementation["agent_id"], implementation["role"])
            owners.append(implementation["agent_id"])
            if implementation["commit_ids"][-1] != implementation["tip_commit"]:
                raise ValidationError("Implementation tip must be the final submitted commit.")
        if len(set(owners)) != len(owners):
            raise ValidationError("Duplicate candidate implementation owner.")

    @classmethod
    def finalize(cls, body):
        if "manifest_digest" in body:
            raise ValidationError("Finalization accepts an undigested manifest only.")
        data = parse_json(canonical_json(body))
        data["manifest_digest"] = digest(data)
        return cls(data)

    def assert_unchanged(self, other):
        if type(other) is not IntegrationCandidate or self.canonical_json() != other.canonical_json():
            raise ValidationError("Finalized candidate cannot be replaced; allocate a new candidate ID.")

    def assert_task_binding(self, task):
        d, t = self.to_dict(), task.to_dict()
        _same(d, task_id=t["task_id"], spec_version=t["spec_version"], spec_digest=t["spec_digest"], policy_digest=t["policy_digest"], source_base_commit=t["source_base_commit"], required_tests=t["required_tests"])
        if not t["spec_frozen"] or not t["founder_approval"]:
            raise AuthorityError("Candidate requires an approved frozen specification.")
        if set(i["agent_id"] for i in d["implementations"]) != set(t["owner_agents"]):
            raise ValidationError("Candidate must include every implementation owner.")
        for change in d["changed_files"]:
            for path in (change["old_path"], change["new_path"]):
                if path is not None and not permits_write(path, _rules(t, "allowed_write_paths"), _rules(t, "read_only_paths"), _rules(t, "forbidden_paths")):
                    raise AuthorityError("Candidate changed a path outside the task scope.")


class Approval(ImmutableRecord):
    __slots__ = ()
    schema_name = "Approval"

    def _validate(self, d, context):
        require_context(context, roles={Role.FOUNDER}, actor_id="FOUNDER")
        if d["authenticated_unix_uid"] != context.authenticated_unix_uid:
            raise AuthorityError("Approval Unix identity does not match authenticated context.")
        bound = ("candidate_id", "candidate_digest", "expected_target_commit", "approved_result_commit")
        if d["action"] == ApprovalAction.APPROVE_SPEC:
            if any(d[k] is not None for k in bound):
                raise ValidationError("Specification approval cannot claim a candidate binding.")
        elif d["action"] in {ApprovalAction.APPROVE_INTEGRATION, ApprovalAction.APPROVE_PUSH} or d["candidate_id"] is not None:
            if any(d[k] is None for k in bound):
                raise ValidationError("Approval requires the complete exact candidate binding.")
        elif any(d[k] is not None for k in bound):
            raise ValidationError("Partial approval binding is prohibited.")
        _candidate_task(d["candidate_id"], d["task_id"])
        if not d["scope"]:
            raise ValidationError("Approval scope cannot be empty.")
        if d["action"] == ApprovalAction.REVOKE and (not d["supersedes"] or not d["reason"]):
            raise ValidationError("Revocation must identify the approval and reason.")

    def assert_binding(self, task, *, action, candidate=None):
        d, t = self.to_dict(), task.to_dict()
        _same(d, action=action, task_id=t["task_id"], spec_version=t["spec_version"], spec_digest=t["spec_digest"])
        if candidate is not None:
            candidate.assert_task_binding(task)
            _same(d, candidate_id=candidate["candidate_id"], candidate_digest=candidate["manifest_digest"], expected_target_commit=candidate["expected_target_commit"], approved_result_commit=candidate["prepared_integration_commit"])
        elif d["candidate_id"] is not None or action != ApprovalAction.APPROVE_SPEC:
            raise ValidationError("This operation requires its exact candidate.")


class TestEvidence(ImmutableRecord):
    __slots__ = ()
    schema_name = "TestEvidence"

    def _validate(self, d, context):
        require_context(context, actor_id=d["recorded_by"]["actor_id"])
        _ordered(d, "started_at", "finished_at")
        _candidate_task(d["candidate_id"], d["task_id"])
        if d["result"] == "PASS" and (d["exit_code"] != 0 or any(d["counts"][k] not in (None, 0) for k in ("failed", "errors"))):
            raise ValidationError("Passing evidence contradicts its exit/count metadata.")

    def assert_binding(self, *, task_id, candidate_id, tested_commit, tested_tree,
                       spec_digest, test_definition_digest, execution_id,
                       environment_profile_digest):
        _same(self.to_dict(), task_id=task_id, candidate_id=candidate_id, tested_commit=tested_commit,
              tested_tree=tested_tree, spec_digest=spec_digest, test_definition_digest=test_definition_digest,
              execution_id=execution_id, environment_profile_digest=environment_profile_digest)


class AuditEvent(ImmutableRecord):
    __slots__ = ()
    schema_name = "AuditEvent"

    def _validate(self, d, context):
        require_context(context, actor_id=d["actor"]["actor_id"])
        if d["event_type"] in {"TASK_APPROVED", "FOUNDER_APPROVED", "APPROVAL_REVOKED", "INTEGRATED", "PUSHED"}:
            require_context(context, roles={Role.FOUNDER})
        if d["event_type"] == "QA_PASSED":
            require_context(context, roles={Role.INTEGRATION_QA})
        if digest({k: v for k, v in d.items() if k != "event_digest"}) != d["event_digest"]:
            raise ValidationError("Audit event digest mismatch.")
        if d["candidate_id"] is not None:
            if d["task_id"] is None:
                raise ValidationError("Candidate event must identify its task.")
            _candidate_task(d["candidate_id"], d["task_id"])

    @classmethod
    def finalize(cls, body, *, context):
        if "event_digest" in body:
            raise ValidationError("Audit finalization accepts an undigested event only.")
        data = parse_json(canonical_json(body))
        data["event_digest"] = digest(data)
        return cls(data, context=context)


class CandidateEvent(ImmutableRecord):
    __slots__ = ()
    schema_name = "CandidateEvent"

    def _validate(self, d, context):
        require_context(context, actor_id=d["actor"]["actor_id"])
        _candidate_task(d["candidate_id"], d["task_id"])
        if d["state"] in {"QA_REVIEW", "QA_PASSED", "CHANGES_REQUESTED"}:
            require_context(context, roles={Role.INTEGRATION_QA})
        elif d["state"] == "FOUNDER_APPROVED_FOR_INTEGRATION":
            require_context(context, roles={Role.FOUNDER})
            if not d["approval_id"]:
                raise ValidationError("Candidate approval event requires an approval reference.")
        else:
            require_context(context, roles={Role.ARCHITECT, Role.FOUNDER})

    def assert_binding(self, candidate):
        _same(self.to_dict(), candidate_id=candidate["candidate_id"], task_id=candidate["task_id"], candidate_digest=candidate["manifest_digest"])
