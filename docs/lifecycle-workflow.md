# Lifecycle Workflow

## Scope

Lifecycle workflow covers what happens after or around contract creation: obligations, execution, proof, approvals, adjustments, reminders/notifications, payment tracking, and operational continuity.

Core files:

- `backend/contracts/models.py`
- `backend/api/contracts/obligations_views.py`
- `backend/api/contracts/execution_views.py`
- `backend/api/contracts/approval_views.py`
- `backend/api/contracts/proof_views.py`
- `backend/api/contracts/resolve_views.py`
- `backend/api/contracts/services/*`
- `backend/api/payments/`
- `backend/api/notifications/`

## Obligations

Two live obligation models exist:

- `ContractObligation` for payments.
- `ContractServiceObligation` for services/work/delivery.

There is also an `Obligation` template/definition model, but existing architecture docs note no live expansion path was found from that model into lifecycle instances.

## Creating Obligations

Contract-scoped route:

```text
POST /api/contracts/<contract_id>/obligations/
```

Behavior:

- caller must be a party.
- requires `obligor_id`, `obligee_id`, `due_date`, and `type`.
- `type` must be `payment` or `service`.
- `ContractLifecycleService` loads the latest contract version.
- if no version exists, creation fails.
- service/payment engine primitives are persisted through a repository.

Important: creation does not require a signed version in the inspected service.

## Execution Sessions

Execution sessions can be opened under payment or service obligations:

```text
POST /api/contracts/obligations/<type>/<obligation_id>/execution-sessions/
```

The session status starts as `active`. Sessions can later be closed.

## Execution Items

Execution item route:

```text
POST /api/contracts/execution-sessions/<session_id>/execution-items/
```

The request records:

- task
- observation
- summary
- estimated duration
- estimated cost
- planned execution time
- metadata

The service then:

- builds an engine `ExecutionItem`.
- runs `ExecutionEvaluator`.
- creates `ObligationExecutionEvent`.
- creates approval request if required.

The current evaluator always requires approval.

## Approvals

Approval routes:

- `POST /api/contracts/approval-requests/<approval_id>/approve/`
- `POST /api/contracts/approval-requests/<approval_id>/reject/`

Approval can trigger:

- additional value adjustment if billing mode is `separate_charge`.
- side obligation promotion if the evaluator suggests it.

Rejection updates the approval request state and does not create those follow-on records.

## Payment Tracking

Payment tracking exists in `backend/payments/` and `backend/api/payments/`. Existing architecture docs note payment confirmation/refund can update payment obligation `amount_paid`.

The contract lifecycle and payment lifecycle are related but separate modules.

## Reminders And Notifications

Notifications exist as a backend domain:

- list
- unread count
- mark read
- mark all read

The inspected lifecycle routes do not prove a complete reminders scheduler. Notification APIs are present, but automatic due-date reminder generation should not be assumed without inspecting future scheduler/task code.

## Timeline And Audits

Timeline evidence:

- `ContractActivity` records are written through `backend/activity/log.py`.
- Contract routes log creation, version creation, signing, rejection, and role switching.
- Execution events and approvals also create operational history, though separate from activity logs.

## Operational Continuity

The intended continuity chain is:

```text
contract
  -> version
  -> obligation
  -> execution session
  -> execution event
  -> approval
  -> adjustment or promoted side obligation
  -> proof of work
```

The backend has most of these pieces. The frontend does not yet present a complete user workflow for this chain.

## Current Gaps

- Signing a contract does not automatically create obligations.
- Obligation due/overdue/default transitions are not fully scheduler-driven in inspected code.
- Notifications exist but automatic lifecycle reminder wiring is not established.
- Dashboard uses static or blank lifecycle summaries in places.
- Payment/service lifecycle states are not unified under a single state machine in the live API.

