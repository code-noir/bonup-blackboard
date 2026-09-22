# bonUP Blackboard Product Direction API — M1/M2

## Scope

M1 provides the application boundary for submitting product-direction input
from the bonUP Operator Console. It creates an application record only. It does
not invoke PROD-01, create an Agent Control task, persist a proposal, perform
Founder review, approve knowledge, route to ARCH, or create execution authority.

The application record is separate from Agent Control authority records. A
future trusted runtime milestone may populate `agent_control_task_id` after
Agent Control accepts a validated task.

## Authentication

All endpoints require the existing operator-scoped JWT and `IsOperator`.
Operator authentication grants application access only. It is not Founder
cryptographic authentication and cannot create `APPROVED_INTERNAL`.

## Endpoints

### `POST /api/product-direction/tasks/`

The request body is exactly:

```json
{"objective":"Define the product direction."}
```

The objective is required, trimmed, limited to 4096 characters, and checked
for obvious credential/private-key material. Unknown fields are rejected.
The client cannot provide model, endpoint, credentials, tools, retries,
knowledge state, Founder decision, or ARCH destination.

Creation returns `201` with an application task in `SUBMITTED` status.

### `GET /api/product-direction/tasks/`

Returns the operator-visible task list using the existing bounded page shape:

```json
{"count":1,"page":1,"page_size":50,"results":[]}
```

### `GET /api/product-direction/tasks/<task_id>/`

Returns the safe task representation for one application task.

## Safe response fields

- `task_id`
- `agent_control_task_id` (currently `null`)
- `agent_id` (`PROD-01`)
- `objective`
- `status`
- `proposal_artifact_id`
- `proposal_id`
- `proposal_digest`
- `review_id` (nullable bounded provenance)
- `review_digest` (nullable bounded provenance)
- `runtime_failure_reason`
- bounded creator identity
- `created_at`
- `updated_at`

No provider envelope, model credential, transport/session material, proposal,
Founder decision, or execution authority is represented.

## Application statuses

The status vocabulary is an application workflow projection, not an Agent
Control authority state machine:

`SUBMITTED`, `RUNNING`, `WORKING_PROPOSAL`, `AWAITING_FOUNDER_REVIEW`,
`APPROVED_INTERNAL`, `REJECTED`, `CHANGES_REQUESTED`, and `BLOCKED`.

M1 creates only `SUBMITTED`. Later milestones must derive transitions from
trusted runtime/review evidence rather than allowing browser-supplied status.

## M2 trusted runtime submission

M2 adds a separate submit action:

```text
POST /api/product-direction/tasks/<task_id>/submit/
```

The request body must be empty. The action accepts no model, endpoint, tools,
retry, credential, prompt, Founder, knowledge-state, or ARCH fields.

On the first submission, the application derives one stable Agent Control task
identity (`ATS-` followed by the decimal value of the application UUID), sets
the application projection to `RUNNING`, and sends only the bounded task
projection to the trusted PROD-01 runtime. A second submission for a task that
is `RUNNING`, `WORKING_PROPOSAL`, or `BLOCKED` is rejected; no automatic retry
is performed.

The trusted runtime is responsible for `validate_product_task()`, fixed
PROD-01 routing, the fixed model/provider policy, zero tools, one request,
zero retries, proposal validation, and mandatory immutable artifact
persistence. Its transport owns the provider credential. Django stores only
bounded result identity (`proposal_artifact_id`, `proposal_id`, and
`proposal_digest`) and never receives a provider envelope or credential.

Successful execution transitions `SUBMITTED → RUNNING → WORKING_PROPOSAL`.
Unavailable or failed runtime execution transitions `SUBMITTED → RUNNING →
BLOCKED` with a bounded application reason. M2 does not perform Founder review,
set `APPROVED_INTERNAL`, route to ARCH, or create execution authority.

The current non-provisioned application composition fails closed with
`RUNTIME_UNAVAILABLE`. A future trusted controller/runtime composition must
replace that seam; it must not be configured from browser input or ordinary
task fields.

## M3 proposal read

```text
GET /api/product-direction/tasks/<task_id>/proposal/
```

The endpoint is operator-authenticated and read-only. For `WORKING_PROPOSAL`,
it loads the proposal by the already-bound proposal identity from the fixed
trusted `ProposalArtifactStore`, verifies the artifact, task, agent, proposal,
digest, and `WORKING` bindings, and returns only the validated product
proposal projection. `AWAITING_FOUNDER_REVIEW`, `APPROVED_INTERNAL`,
`REJECTED`, and `CHANGES_REQUESTED` may continue to read the same immutable
artifact after later milestones. `SUBMITTED`, `RUNNING`, and `BLOCKED` return
`PROPOSAL_NOT_AVAILABLE`.

The response contains the application task ID, Agent Control task ID, agent ID,
proposal ID/digest, knowledge state, title, `problem_user_need`, objective,
`proposed_requirement`, acceptance intent, dependencies, assumptions,
`risks_open_questions`, priority recommendation, and evidence references.
Evidence references are displayed as validated bounded metadata only; they are
never dereferenced by this endpoint.

Safe failure reasons include `ARTIFACT_MISSING`, `ARTIFACT_INVALID`,
`ARTIFACT_BINDING_MISMATCH`, `TASK_BINDING_MISMATCH`,
`PROPOSAL_BINDING_MISMATCH`, `PROPOSAL_DIGEST_MISMATCH`, and
`KNOWLEDGE_STATE_INVALID`. No path, provider envelope, credential, reasoning,
request metadata, Founder session material, or authority record is returned.

Reading the artifact does not mutate the task, proposal, knowledge state, or
authority system. Operator read access is separate from the future Founder
review operation.

## M5 authenticated Founder review

M5 keeps the Operator-versus-Founder boundary explicit. An operator JWT may
display a proposal and initiate a review challenge, but it is never accepted
as authorization for `ACCEPT`, `REJECT`, or `REQUEST_CHANGES`. The review
decision must come from the existing cryptographic Founder protocol:

```text
Operator API requests Founder review initiation
  -> trusted Agent Control bridge binds and requests Founder review
  -> Founder signs externally
  -> FounderTransport delivers the external signature to Agent Control
  -> one-use authenticated Founder session is consumed
  -> ProductionProductReviewAdapter writes Registry v2 ProductReviewRecord
  -> Registry atomically stores PRODUCT_REVIEW_COMPLETED v1 and its domain-event outbox obligation
  -> Product Direction consumes the verified event and stores review ID/digest projection
```

The application challenge endpoint is:

```text
POST /api/product-direction/tasks/<task_id>/review/challenge/
```

Its exact request body is `{"decision":"ACCEPT|REJECT|REQUEST_CHANGES",
"reason":"bounded reason"}`. The server derives the artifact ID, artifact
digest, Agent Control task ID, proposal ID, proposal digest, and
`PROD_PROPOSAL_REVIEW` purpose from the locked `ProductDirectionTask` and the
verified immutable artifact. Browser-supplied binding fields are rejected.
The application observes the trusted Agent Control result through:

```text
GET /api/product-direction/tasks/<task_id>/review/status/
```

The browser sends only `decision` and bounded `reason` to the initiation
endpoint. It never submits a signature or accepts a challenge, task ID,
proposal ID/digest, artifact identity, purpose, Founder identity, or session.
The provisioned Agent Control composition owns `FounderIntake`,
`FounderSessions`, `FounderTransport`, challenge freshness/replay protection,
external signature verification, one-use Founder session creation, and the
call to `ProductionProductReviewAdapter`. `SyntheticFounderReviewContext` and
arbitrary `AuthenticatedContext` values are not production application inputs.
The legacy `/review/submit/` action is disabled with `FOUNDER_EXTERNAL_ONLY`.

The current installation has no Founder Genesis, installed Founder root,
Generation-2 installation, or production Founder socket. The application
bridge therefore reports `FOUNDER_RUNTIME_UNAVAILABLE` and fails closed; it
does not provide an operator bypass, synthetic approval, or hardcoded Founder.
The UI says: “Founder authentication is not available on this installation.”

After durable `ProductReviewRecord` creation, Agent Control emits one immutable
`PRODUCT_REVIEW_COMPLETED` v1 fact. It contains only the safe review/task/agent/
artifact/proposal bindings, decision, knowledge states, event time, and
operation/correlation identifiers. It contains no Founder signature, challenge,
session, key, peer, path, or credential. Product Direction acknowledges the
event with a unique `(consumer_name, event_id)` inbox row in the same Django
transaction as its projection update. Duplicate delivery is a no-op; a failed
projection rolls back the inbox acknowledgement so the durable event can be
retried. Replaying the event rebuilds projections only and never invokes Founder
authentication or creates another `ProductReviewRecord`.

The application stores only bounded `review_id` and `review_digest` provenance.
Status transitions are:

- `ACCEPT`: `WORKING` knowledge state -> application `APPROVED_INTERNAL`.
- `REJECT`: immutable proposal retained; application `REJECTED`.
- `REQUEST_CHANGES`: immutable proposal retained; application
  `CHANGES_REQUESTED`; any future revision is a new predecessor-linked
  proposal.

No review can produce `PUBLICATION_ELIGIBLE`, create an ARCH task, route to
ARCH-01, create an AgentRecord or ExecutionGrant, activate an agent, modify a
repository, or publish. Application status is updated only after the EVENT-01
consumer receives the durably persisted review event. Persistence or binding
failure leaves the prior application status unchanged, and replay, duplicate,
stale, substituted, or already-reviewed requests return bounded safe reasons
without creating another review record.

The review result exposes only review ID/digest, decision, prior/resulting
knowledge state, proposal ID, and proposal digest. Founder signatures,
challenge contents, session material, registry internals, peer metadata,
filesystem paths, and exception details are never returned.

## Trusted Founder-facing review packet

The installed Agent Control Founder composition uses
`FounderReviewCoordinator` with the existing `FounderIntake`,
`FounderSessions`, `FounderTransport`, and
`ProductionProductReviewAdapter`. An application review request stores only
the canonical binding as a pending request. When the external Founder process
requests its challenge, Agent Control reloads and verifies the immutable
proposal artifact and returns two separate values:

```text
{
  "challenge": <canonical PROD_PROPOSAL_REVIEW challenge>,
  "review": <safe human-readable proposal display>
}
```

The `review` value contains the task, agent, artifact/proposal identities and
digests, all bounded proposal fields, requested decision, reason, resulting
knowledge state, and the notice that ACCEPT means `APPROVED_INTERNAL` product
direction only. It contains no path, provider envelope, credential, Founder
session, or private key material.

The proposal display is not copied into the signed challenge. The Founder
signs only the canonical challenge binding. Before challenge issuance and
again before `ProductionProductReviewAdapter.review()`, Agent Control reloads
the artifact and verifies that artifact ID/digest, proposal ID/digest, task,
decision, and reason are identical. A changed proposal or decision is denied.

On `SUBMIT_FOUNDER_SIGNATURE`, the existing one-use `FounderSessions` session
is consumed by `ProductionProductReviewAdapter`, which commits exactly one
`ProductReviewRecord` and its durable event. The application never receives
the signature or session. The Founder-facing packet is available only through
the trusted external Founder transport; the Operator browser remains an
initiation and observation surface.
