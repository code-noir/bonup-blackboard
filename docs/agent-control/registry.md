# bonUP Agent Control — durable registry and publication

Document ID: AGENT-CONTROL-REGISTRY. Version: 1. Owner: founder.
Status: current implementation, Phase I / Milestone 2; no operational activation.
Scope: local control-state persistence, publication, inspection and synthetic tests.
Updated/reviewed: 2026-09-11. Review due: before Milestone 3 or a storage/authority change.
Inspected baseline: `7bcf61eaa51696168d0b4629f4068931955dfe71`.
Verified source: the accompanying registry implementation and focused test results
in this commit; no claim of deployed controller verification.
Approval reference: founder's explicit Milestone 2 implementation instruction.
Supersedes: Milestone 1 README statements that persistence/publication are not yet
implemented. Its role, authority and schema rules continue to apply.
Superseded by: none. Dependencies: policy.json, schemas.json, Milestone 1 domain
validation, Python 3.11+ standard library, local Git supporting `core.fsync=committed`.

## Architecture and limits

SQLite is authoritative mutable control state. A **separate local bare Git
repository** publishes human-readable JSON as secondary audit history. Publication
may lag without losing the authoritative mutation or its obligation to publish.
There is no daemon, scheduler, socket, agent launcher, real resource acquisition,
application Git integration, push command or migration of the application database.
There are no configured production paths and no implicit initialization on import.

All paths are explicit. Runtime paths inside working Git repositories, symlinked
control paths and database/history nesting are rejected. Conceptual deployment
paths remain `/var/lib/bonup-agent-control/state.sqlite3` and a separate `records/`
repository, but this milestone does not create them. Tests use private temporary
directories and synthetic data; no application settings, database, credentials,
Codex state or network are needed.

A bare history repository avoids a second mutable checkout or index. Read records
with ordinary `git --git-dir=... show control-history:path/to/record.json` or browse
its commit history. Publisher commands use local plumbing only: hash-object,
mktree, commit-tree and compare-and-swap update-ref. No reset, checkout, push or
history rewriting occurs. There must be no remote and exactly the managed history
ref. Identity is bound to the SQLite registry UUID in a committed identity record.
Git commands isolate inherited Git configuration/environment, disable hooks and
signing, and request committed-object/reference fsync. The repository root is
private; no global or application Git configuration is changed.

## SQLite model

Schema version 1 uses these tables:

| Tables | Purpose |
|---|---|
| schema_versions, metadata | Control schema history, registry identity, pinned policy, history location |
| sequences | ATS, finding/conflict/decision and event numbering |
| tasks, task_specs | Current validated Task and durable immutable specification versions/freeze flag |
| agents | Four disabled organizational identities |
| executions | Dormant ExecutionGrant metadata; no sessions launched |
| records | Current Finding/Conflict/Decision envelope and revision |
| candidates | Immutable manifest plus separate invalidation flag |
| approvals, evidence, candidate_events | Immutable, exactly bound metadata and independent QA events |
| operations | Domain operation ID, canonical request digest and original result |
| audit_events | Append-only ordered events and digest chain |
| outbox | Immutable publication obligations, full source snapshots and projected publication payloads |
| publications | Unique publication acknowledgement, digest, commit OID, time and status |
| maintenance_operations | Idempotent publication/backup bookkeeping requests and results |

Every connection enables foreign keys, a 10-second busy timeout and FULL
synchronous behavior. Initialization enables WAL. Initial schema, metadata, agent
seeds, event, idempotency record and outbox are committed in one transaction.
There is an explicit control schema-version table; unsupported versions block.
No automatic database upgrade is implemented yet. A schema-initialization crash
before commit can leave an uninitialized file: it is blocked, never silently
reinitialized or deleted. A separate explicit operator recovery procedure is
needed for that exceptional case.

Task creation and record allocation use `BEGIN IMMEDIATE`. Sequence increments,
validated records, audit event, outbox and idempotency result commit together.
Display IDs are monotonic `ATS-0001`, `FINDING-0001`, `CONFLICT-0001`, `DECISION-0001`;
tasks also receive an independent UUID. No API deletes/recycles IDs. Gaps are
allowed. Failed rolled-back allocations were never issued and may be retried.
Numbering never depends on Git. Concurrent requests serialize in SQLite; the
bounded timeout produces a retryable SQLite busy failure rather than lost writes.

Every mutation requires a UUID operation ID. Its digest covers command kind,
canonical payload and trusted context (if required). Same key/same request returns
the original result with no new ID, event or publication. Different payload,
authority context, command or domain/maintenance use of the key is rejected.
Generated timestamps/IDs are in the original result, not recalculated on retry.
Timestamps are explicit UTC ISO strings generated once per committed operation;
array order is significant in canonical payloads. Callers must retry the same
logical request with its original key, and new work with a new key.

## Authority and record APIs

`Registry.create_task` accepts a narrow proposal and always creates PROPOSED.
Unapproved proposal intake may omit authenticated context. `requested_by` then
remains a declaration, not authenticated founder approval; its audit reason is
`UNAUTHENTICATED_LOCAL_INTAKE`. The ARCH-01 audit label on this local intake is a
coordination attribution, not evidence that an Architect session ran. No authority
is inferred from it. CLI users cannot construct an authenticated founder context.

Other changes require Milestone 1's trusted in-process AuthenticatedContext.
`revise_task` creates a new specification version; `attach_dependencies` follows
that same approval-invalidating revision path and rejects dependency cycles.
`assign_metadata` records approved path/workspace assignment metadata without
creating a branch/worktree or enabling an agent. `checkpoint` records structured
handoff; `submit_commit_metadata` accepts the assigned engineer's OID while the
task is IN_PROGRESS. Actual Git content/ancestry validation is not claimed.

`transition` and `freeze_spec` reuse Milestone 1's allowlist, ownership checks,
exact approvals and QA evidence. Recovery requires an explicit stored resolution.
INTEGRATED/PUSHED operations are deliberately unavailable until real trusted Git
receipts exist. Their event vocabulary remains defined, but this milestone never
fabricates successful integration/push. No public arbitrary task replacement API
exists. Specification versions cannot change their digest in place; freezing is
one-way. Old versions and publication snapshots remain durable.

`create_record`, `resolve_record`, and SUPERSEDED resolution allocate and preserve
record revisions. A replacement must explicitly name the record it supersedes.
Architect may resolve ordinary technical matters, not security/product/scope or
material-budget policy. Future role recommendations remain nonbinding.

`put_metadata` handles validated candidates, approvals, dormant executions,
evidence and candidate events. Reusing an existing immutable record ID through a
new operation fails. Candidates bind exact specs/commits/trees; approvals bind
frozen specs and exact candidate/target/result. Evidence binds a registered dormant
execution and its actor/spec, and candidate commit/tree/test-definition where
applicable. Unknown counts stay null. New spec versions and changed submitted
commit metadata invalidate prior candidates. Revoked/superseded approvals cannot
be used as active authorization. Historical approvals remain structurally valid
history rather than disappearing when superseded.

All four seeded AgentRecords remain DISABLED, with no Unix identity or sessions
and zero token allowance. Other status names remain in the Milestone 1 schema;
this registry does not provide an operation that activates them. Dormant
ExecutionGrant records are metadata only and reject sessions or real reservations.
There is no runtime resource reservation table or resource-control code here.

Stored context is validated provenance owned by the registry, not a new way to
authenticate requests from JSON. Unix peer authentication and protected callers
remain Milestone 3. Anyone able to execute arbitrary Python or modify the SQLite
file as its owner is outside this milestone's technical security boundary.

## Events, outbox and publication

Every domain mutation appends one event and all required immutable snapshots in
the same transaction. Events have increasing sequence, operation ID, previous
event digest and their own canonical digest. Outbox source snapshots bind to the
event's record digests; projected publication payloads bind to those snapshots.
Triggers reject ordinary UPDATE/DELETE of events, immutable metadata, outbox and
acknowledgements. The application API exposes no history deletion or rewriting.
Hash chaining is a consistency check, not protection against root/controller
compromise or someone able to replace an entire database and trusted checkpoint.

Publication paths include:

```text
tasks/ATS-0001/spec-v001/definition.json
tasks/ATS-0001/spec-v001/frozen.json
tasks/ATS-0001/revisions/000001.json
findings/FINDING-0001/v001.json
conflicts/CONFLICT-0001/v001.json
decisions/DECISION-0001/v001.json
candidates/IC-ATS-0001-01.json
approvals/<approval-uuid>.json
evidence/<evidence-uuid>.json
candidate_events/<event-uuid>.json
events/000000000001.json
```

Each snapshot has one focused commit, fixed publication identity/time, a stable
message binding publication ID/digest and stable readable JSON. Parent commit is
part of the commit identity, so concurrency/order can affect OIDs; payload and
semantic publication identity remain deterministic. Conditional ref updates
preserve competing publications. Existing identical path/content is acknowledged
using its original creation commit; a conflicting path/content blocks.

Source snapshots contain schema-limited control metadata only. Publication
omits argv, raw Unix/process/session identifiers and authenticated UID. It never
copies environment, SQLite files, Codex state, prompts or arbitrary log artifacts.
Free-text objective/finding/handoff fields still need sanitized author input:
field projection cannot recognize every secret embedded in text. Do not submit
credentials, raw prompts or customer contents even to authoritative SQLite.
Evidence uses reviewed command IDs and digests; no tool output is copied.

Publication acknowledgement is **transport bookkeeping**, not a new domain fact:
it records publication ID/outbox/record/digest/OID/time/status without generating
another publishable event. Maintenance requests have durable idempotency records.
This prevents an infinite acknowledgement-publication loop. No domain mutation
can bypass its event/outbox transaction by using maintenance operations.

## Startup, recovery and backup

Registry opening computes `startup_report`; `verify()` can repeat it. Verification
uses a stable SQLite transaction while comparing history. Writes verify the
SQLite authoritative records before accepting a mutation; publication and CLI
operations also check history. Consumers of the Python API must honor a BLOCKED
startup report; there is no daemon or automatic agent launcher to bypass it.

- **HEALTHY:** authoritative state, events, snapshots and all publications agree.
- **DEGRADED:** authoritative state is sound and publication obligations remain.
- **BLOCKED:** schema/foreign keys/digests/IDs/events/bindings/identity/acknowledged
  commits conflict, published payload differs, or state cannot be reconciled.

Checks include integrity_check, foreign_key_check, sequence sanity, task/spec and
candidate digests, approval/evidence bindings, current snapshot correspondence,
event gaps/chaining, operation/outbox completeness, repository identity/no remote,
acknowledged OID ancestry and exact published bytes. Unsupported schema raises a
blocked error before normal opening. BLOCKED state is reported, not auto-repaired.

Crash windows:

1. SQLite commits before Git: outbox remains pending. Reconciliation publishes it.
2. Git commits before acknowledgement: reconciliation finds the same path/digest,
   verifies its original commit and acknowledges it without duplicate publication.
3. Publication fails: authoritative state remains committed; pending work retries.
4. Conflicting payload/identity or missing acknowledged commit: BLOCKED; no reset,
   deletion, guessed repair or history rewrite.

Acknowledgements are individually transactional. Two publishers may retry the
same item; unique acknowledgement keys plus Git conditional ref updates prevent
semantic duplicates. Successful reconcile requests replay their original result;
a new invocation for newly queued work needs a new operation ID. `status` always
reports current state rather than an old idempotent result.

`Registry.backup(destination, operation_id=...)` uses SQLite's backup API, an
exclusive new destination with mode 0600, integrity/foreign-key/registry checks,
and a recorded file digest. It never shells out a SQL dump or replaces an existing
file. A successfully acknowledged retry verifies the same backup. An interrupted
backup that left a destination without acknowledgement fails closed; it does not
guess that a partial file is complete. A backup is an independent SQLite snapshot,
not a new registry identity, and still references its original secondary history.
No scheduled backup, automatic restore, historical database recreation from Git,
or production backup is implemented.

## Minimal operator interface

No installed executable is needed. All commands require an explicit external
`--state` path. The CLI offers no --actor/--uid impersonation flags and no approval,
launch, scheduler, resource acquisition, integration or push commands.

```text
python3 -B -m tools.agent_control --state PATH --history PATH registry init --operation-id UUID
python3 -B -m tools.agent_control --state PATH registry status
python3 -B -m tools.agent_control --state PATH task create --operation-id UUID --input sanitized-proposal.json
python3 -B -m tools.agent_control --state PATH task show ATS-0001
python3 -B -m tools.agent_control --state PATH task list
python3 -B -m tools.agent_control --state PATH finding list [--task-id ATS-0001] [--unresolved]
python3 -B -m tools.agent_control --state PATH history verify
python3 -B -m tools.agent_control --state PATH publication status
python3 -B -m tools.agent_control --state PATH publication reconcile --operation-id UUID
```

Proposal input minimally contains title, objective and source_base_commit; stdin
is supported with `--input -`. Status output is JSON. BLOCKED/rejected operations
exit 2 without dumping raw exceptions, SQL or Git stderr. There is no default
production path and no live registry initialized by the test suite.

## Validation

Run only the combined control-layer suites:

```sh
python3 -B -m unittest discover -s tests/agent_control -v
```

Tests use TemporaryDirectory, independent SQLite connections and bounded spawned
process pools. They cover sequential/concurrent IDs, racing retries, transactional
rollback, persisted authority and QA metadata, both publication crash windows,
corruption, disabled agents, backups and CLI behavior. Synthetic history has no
remote; tests never push, import application settings or access customer data.
