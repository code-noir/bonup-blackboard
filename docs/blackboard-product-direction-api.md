# bonUP Blackboard Product Direction API — M1

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
