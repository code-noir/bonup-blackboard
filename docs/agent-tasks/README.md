# bonUP Agent Task Documents

Status: contract version 1. Scope: human-readable projections of Agent Control
records. Development task documents live at `docs/agent-tasks/<TASK-ID>.md`.

## Purpose and authority boundary

An Agent Task Document lets a contractor understand what an agent was assigned,
why, who owned it, the constraints, work performed, artifacts, validation,
result, and evidence references. It is a deterministic Markdown projection, not
an execution record. Editing a document cannot create identity, grants, fencing,
authorization, approvals, audit events, or security evidence.

The immutable Agent Control `Task` and its durable registry revisions remain the
authority for task identity, ATS specification, ownership, and state. Validated
`AgentRecord`, `ExecutionGrant`, reservation/fencing, approval, candidate,
`TestEvidence`, execution, and `AuditEvent` records remain authoritative for
their respective facts. Documents reference those records; they do not copy raw
logs or replace them.

## Contract

`tools.agent_control.task_document.render_task_document()` requires a validated
`Task` plus bounded summary fields: background, inputs, plan, work performed,
artifacts, validation, result, evidence references, and optional start/completion
times. Title, objective, agent ownership, task ID/UUID, task revision, spec
version/digest, policy digest, and authoritative state come only from the Task.
Machine metadata is canonical JSON with sorted keys so identical input produces
identical Markdown.

Each evidence reference has exactly `kind`, `identifier`, `digest`, and `path`.
The identifier is required and either a SHA-256 digest or repository/registry
path must be present. References should point to trusted records such as test
evidence, executions, audit events, candidates, approvals, or publication
receipts.

## Lifecycle mapping

The displayed document status is only a summary of the existing task state:

- `CREATED`: `PROPOSED` through `ASSIGNED`
- `IN_PROGRESS`: active implementation, QA, approval, integration, or pushed states
- `BLOCKED`: `BLOCKED`, `CONTRACT_CONFLICT`, or `INTERRUPTED`
- `COMPLETED`: `CLOSED`
- `FAILED`: `ABANDONED`

No transition is performed by rendering. The Agent Control lifecycle remains the
only task state machine.

## Security and use by future agents

Fields and lists are bounded. Unknown fields and malformed evidence references
are rejected. Known credential/private-key patterns and raw secret environment
assignments are rejected. Documents must never contain credentials, API keys,
private keys, customer secrets/content, full environments, prompts, or unbounded
raw logs. Store sensitive evidence in its approved system and reference only its
sanitized identifier/digest.

Future bonUP agents may render this document after trusted records are updated,
using their explicit authoritative agent IDs (for example `ARCH-01`, `FE-01`,
`BE-01`, or `QA-01`). This contract does not define or activate the 12-agent
roster. A future bonUP Speaker may consume founder-approved documents as bounded
summaries, but Speaker integration, approval policy, and publication are outside
this contract.

## Projection command

From the repository root, project one task from an explicitly selected Agent
Control registry:

```sh
python3 -m tools.agent_control.task_document_project \
  --state /absolute/path/to/state.sqlite3 \
  --task-id ATS-0001
```

The command uses the registry's validated `Task` snapshot and loads only
`TestEvidence` records already referenced by that task or its authoritative
handoff. It renders evidence identifiers, payload digests, and registry paths;
it never copies argv, environments, logs, credentials, or evidence contents.
Objective, ownership, state, policy/specification bindings, acceptance criteria,
handoff work, changed paths, and close result come from authoritative records.
Missing narrative is explicitly shown as not recorded.

Output is fixed at `docs/agent-tasks/<TASK-ID>.md`. The task ID is validated and
cannot select an arbitrary path. Symlink destinations are rejected. Writes use a
same-directory temporary file and atomic replacement, with temporary cleanup on
failure. Identical projections are left unchanged. A different projection may
replace an older revision of the same task UUID, but equal/newer revisions,
identity conflicts, or documents without valid binding metadata fail closed.
The command accepts no agent, status, grant, result, evidence-content, policy, or
specification override. It does not invoke registry mutation APIs and cannot
change task state or execution authority. Future members of the 12-agent system
can use the same read/project operation after their authoritative records exist.
