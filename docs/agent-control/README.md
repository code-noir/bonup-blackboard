# bonUP Agent Control — policy and schema core

Document ID: AGENT-CONTROL-CORE. Version: 1. Status: accepted definitions only.
Owner: founder. Scope: Phase I / Milestone 1. Updated/reviewed: 2026-09-11.
Review due: before the next control-layer milestone or any authority change.
Inspected application baseline: `6020850cb41c8a94e451c254b5497b0cda523225`.
Verified runtime enforcement commit: none (this milestone defines behavior only).
Approval reference: founder's explicit “Phase I / Milestone 1 — Policy, Schema &
Authority Core” implementation instruction. No runtime Approval record exists.
Supersedes/superseded by: none. Dependencies: the founder-approved foundation
rules, this milestone's instructions, and the version 1 policy/schema files.

This is the authoritative entry point for **managed** Agent Control policy.
It does not activate managed execution or change ordinary repository permissions.

## Files and use

- `policy.json`: the four enabled identities, role capabilities, protected paths,
  resource definitions and founder distinction. This is the versioned policy;
  there is no second roles/resources configuration to drift.
- `schemas.json`: version 1 JSON Schema definitions for all domain records and
  nested values. Every object field is explicit; nullable values must be supplied
  as `null`. Unknown fields, invalid IDs/enums and noncanonical paths are rejected.
- `document-authority.json`: authority hierarchy and future freshness metadata.
- `tools/agent_control/`: standard-library Python validation and pure operations.
- `tests/agent_control/`: synthetic unit tests. No application database imports.

Run from the repository root:

```sh
python3 -B -m unittest discover -s tests/agent_control -v
```

`schema.validate_schema(name, data)` validates the structural schema. Construct
`records.Task`, `AgentRecord`, `ExecutionGrant`, `Reservation`, `Record`,
`IntegrationCandidate`, `Approval`, `TestEvidence`, `AuditEvent` or
`CandidateEvent` to apply semantic checks as well. Use `assert_task_binding` or
`assert_binding` before relating records. Structural validation alone does not
prove authority, exact bindings or authentic execution.

The bundled schema validator implements only the JSON Schema keyword subset
used here, with custom formats treated as assertions. It is not a general schema
engine. There are no remote references, package dependencies or network reads.
Policy/schema reads are explicit, cached per process, and returned as detached
values. Future long-lived processes must pin versions and restart/reload through
a controlled policy change; this module is not a hot-reload service.

## Authority and existing instruction conflict

The founder is a human authority, not an agent or execution role to launch.
`ARCH-01` coordinates and proposes/revises specifications; no application edits,
merge or push by default. `FE-01` and `BE-01` write only their assigned scope,
within role boundaries. `QA-01` reads/tests sanitized inputs and reports findings;
it cannot repair application code, redefine the ATS or approve its specification.
Only the founder can approve a specification or exact integration candidate.
Only independent assigned QA can produce a task's `QA_PASSED` transition.
Future organizational roles may record recommendations; they receive no Phase I
grants and cannot resolve binding decisions independently.

The inspected legacy instructions conflict: AGENTS.md “Owner Authority” allows
Git actions when explicitly instructed by the owner, while CLAUDE.md section
19.3 says agents must refuse commits even when asked. Neither file is rewritten.
For founder-authorized **managed executions**, this operating policy is the
explicit scoped exception: engineers may make focused **local** commits only
when their ExecutionGrant has `can_commit_local=true`. No normal Phase I grant
can permit push or merge. Founder-controlled integration/push actions require
separate exact approvals; they are not worker grant escalation. Unmanaged
sessions retain their existing instructions and explicit owner authorization.
This milestone's requested local commit is directly owner-authorized; it does
not create a grant or enable any future runtime Git authority.

An ExecutionGrant is validated metadata, not filesystem confinement. The future
trusted controller must bind it to an approved task, authenticated identity,
workspace, current lease/fencing epoch and process. A caller may not deserialize
an authenticated context from request JSON.

`AuthenticatedContext` is a separate, frozen in-process input expected from a
trusted authentication adapter. Approval rejects absent contexts, dictionaries,
engineer contexts and mismatched authenticated UID, even if the payload says
`actor_id="FOUNDER"`. **Constructing this object in arbitrary Python is not Unix
authentication.** Actual peer authentication belongs to Milestone 3. These
classes are not a boundary against hostile code in the same interpreter.

## Task lifecycle and field ownership

`lifecycle.TRANSITIONS` is the explicit allowlist. Normal progression is:

```text
PROPOSED -> INSPECTING -> SPEC_READY -> FOUNDER_APPROVED -> ASSIGNED
-> IN_PROGRESS -> READY_FOR_QA -> QA_REVIEW -> QA_PASSED
-> FOUNDER_APPROVED_FOR_INTEGRATION -> INTEGRATED -> PUSHED -> CLOSED
QA_REVIEW -> CHANGES_REQUESTED -> IN_PROGRESS
```

Architect performs inspection, specification readiness and assignment. Assigned
engineers submit work. Assigned QA reviews and requests changes/passes. Founder
approves specifications, integration and push, and closes the accepted path.
`CLOSED` is reachable only from `PUSHED`, with an explicit reason. `ABANDONED` is
a separate founder-only terminal outcome; it does not imply integration.

Active assignment/implementation or QA may enter the declared exceptional paths.
BLOCKED, CONTRACT_CONFLICT and INTERRUPTED require explicit reasons; recovery
returns through INSPECTING with a resolved Decision record and matching task.
Reassignment requires reconciliation plus the current exact specification
approval. No direct exceptional-to-IN_PROGRESS shortcut exists. Transitions
outside the enumerated table are rejected; new routes require policy review.

Records are immutable values. `transition_task` returns a new revision with an
explicit actor and timestamp. `revise_spec` permits only the assigned Architect,
requires active work to stop/reconcile first, increments the version, recomputes
the digest and clears approvals. QA and engineers cannot use it. Runtime loading
of a Task is structural reconstitution, **not evidence its historical state was
authorized**. The future registry must admit initial tasks as PROPOSED and apply
only authenticated operations thereafter, retaining events and preventing
record replacement. This milestone does not implement generic record mutation.

The ATS digest binds objective, acceptance criteria, priority, approved paths,
dependencies, tests, resources, budget, base and policy. Assignment/workspace,
sessions, progress, usage and approvals are operational fields; their future
updates require authorized controller operations rather than spec mutation.
Progress belongs to assigned owners; validation to authenticated evidence
producers; assignment/recovery to Architect; approval to founder. Budget/scope,
security policy, product and major architecture decisions require founder
resolution. Engineers may resolve their own implementation findings/decisions;
Architect resolves ordinary technical/interface matters within approved scope.
Decisions cannot be made ordinary by labeling policy impacts “TECHNICAL”: the
explicit `decision_scope` and revision-impact fields are also checked. Correct
classification still requires independent review; software cannot infer intent.

## Paths and resources

PathRule has FILE, DIRECTORY and GLOB types. Paths are repository-relative,
NFC-normalized and unambiguous; absolute paths, traversal, dot segments, repeated
slashes, backslashes, encoded separators, controls and unsupported syntax fail.
A directory's single trailing slash is normalized on construction; serialized
records must already be canonical. Globs support literal directory prefixes,
optional terminal `**` (or `**` before a basename), and basename `*`. No character
classes, braces, negation or `?`. Overlap uses conservative literal-prefix
envelopes, so disjoint suffix globs can deliberately conflict. Denies/read-only
rules take precedence. Assignment scopes must fit approved scope and cannot
overlap each other. Coordinated shared ownership is not enabled implicitly;
future explicit coordination records must precede any policy extension.

These are lexical checks. They do not resolve symlinks, mount points, alternate
Git directories, hard links or process writes. Later confinement and actual Git
diff verification must enforce those boundaries and match complete changed-file
metadata, including both sides of renames and mode/blob identities.

All ten MVP resource types are defined in policy.json. EXCLUSIVE and CAPACITY
are typed modes; current resources allow only EXCLUSIVE/one unit. Reservations
bind task, execution, fencing epoch, timestamps and recovery metadata. No lock is
acquired. GIT_INTEGRATION and PRODUCTION_DEPLOYMENT are denied to normal agents.
Lease expiry is metadata, never permission to steal an uncertain live resource.
Capacity scheduling, renewal, liveness and stale-lock recovery are later work.

## Immutable candidates, approvals and evidence

A candidate manifest binds exact specification/policy digests, source base,
expected target, implementation commits, prepared commit/tree, changed paths,
diff digest, tests and evidence references. `finalize` detaches and hashes the
manifest. Public mutation fails; exports cannot mutate it. `assert_unchanged`
rejects replacement, including an updated manifest with the same candidate ID.
A future registry must enforce ID uniqueness and require a new candidate whenever
implementation changes. Git ancestry, actual diff completeness, branch movement
and expected-target comparison are not inspected by these definitions.

QA/approval events are separate immutable records. A task QA pass requires the
assigned QA's exact-candidate event and passing evidence for every required test
on the prepared commit/tree and current specification. Later execution adapters
must verify execution/environment identities, truthful results, candidate
invalidation, approval revocation and ordering from durable history. Domain
`INTEGRATED`/`PUSHED` transitions require exact approvals but do not execute Git
or prove Git operations happened; trusted operation receipts are still required.

APPROVE_SPEC binds task/version/digest. APPROVE_INTEGRATION and APPROVE_PUSH
add candidate ID/digest, expected target and approved result commit. Partial
bindings fail. REJECT and REVOKE are records; revocation requires a reason and
superseded approval reference. Supersession/revocation history is not persisted.

Canonical JSON uses UTF-8, sorted string keys and compact separators, with
SHA-256 digests. It supports only JSON integers, booleans, strings, arrays,
objects and null; duplicate keys, floats, NaN and arbitrary Python objects fail.
Money is an explicit decimal string. This is a project serialization contract,
not a claim of RFC 8785 compliance. Manifest/event digest fields exclude their
own digest. Git object IDs are distinct from SHA-256 metadata digests.

Evidence binds task, optional candidate, commit/tree, spec, test definition,
execution, environment profile, timestamps and result. Unknown counts remain
null. Audit events store metadata/digests, not transcripts. Never include secrets,
raw prompts, customer contents or credentials in any free-text field or argv;
use allowlisted synthetic command identifiers and digest references. Schemas
cannot detect every secret embedded in otherwise valid text. Later adapters
must sanitize and limit collection. Hash chains detect changes only against a
trusted checkpoint; they are not authentication or durable storage themselves.

## Document authority

Follow document-authority.json in this order: current founder-approved ATS,
operating policy, accepted architecture, current domain architecture, verified
source/tests, historical documentation. Source/tests can prove an implementation
document stale; they cannot grant permission to violate approved policy. Record
a Finding/Conflict and pause dependent work rather than silently choosing.

Future documents require explicit version, owner, scope, review dates, verified
commit (or null for normative-only policy), approval and supersession links.
Missing metadata, changed referenced source or overdue review prompts inspection.
Legacy current-task/next-task and architecture documents remain discovery aids,
not automatically fresh truth. This milestone does not rewrite legacy docs.

## Scope boundary

No application source, migrations, runtime database, daemon, scheduler, Unix
users, worktrees, workers, Codex launches, sockets, actual reservations or real
application integration candidates are created. No packages or runtime config
are installed. No task IDs are allocated. Python fixtures use synthetic IDs,
paths and hashes only. Later milestones must provide persistence, authenticated
commands, confinement, atomic ownership, recovery and actual execution checks.
