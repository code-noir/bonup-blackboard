# Negotiation Workflow

## Current Implementation

Negotiation is implemented through contract versions, signing/rejection, and role switching.

Core files:

- `backend/contracts/models.py`
- `backend/api/contracts/version_views.py`
- `backend/api/contracts/role_switch_views.py`
- `backend/api/contracts/permissions.py`
- `backend/api/contracts/urls.py`

## Two-User Model

The current system supports two parties:

- Initiator: `Contract.initiator`
- Counterparty: `Contract.counterparty_email`

The counterparty is not stored as a foreign key. Authority is based on matching the authenticated user's email to `counterparty_email`.

## Send / Receive Flow

There is no explicit "send version" API transition in the inspected live version flow. `ContractVersion` supports `sent` and `negotiating` statuses, but the active API creates new versions as `draft`.

The practical flow is:

```text
Initiator creates contract
Initiator creates version
Counterparty signs or rejects version
Initiator may create another version if rejected and cap not reached
```

## Response Handling

Counterparty responses:

- `POST /api/contracts/<contract_id>/versions/<version_id>/sign/`
- `POST /api/contracts/<contract_id>/versions/<version_id>/reject/`

Signing:

- requires the caller to be the counterparty.
- blocks terminal versions.
- sets version status to `signed`.
- logs activity.

Rejection:

- requires the caller to be the counterparty.
- blocks terminal versions.
- sets version status to `rejected`.
- logs activity.
- returns warning near/final version cap.

## Pending States

Implemented pending-like state:

- `ContractRoleSwitchRequest.status = pending`

Defined but not practically used in live API:

- `ContractVersion.status = sent`
- `ContractVersion.status = negotiating`
- `RequestChange.status = pending`

## Notifications

Notification APIs exist under `backend/api/notifications/`, but the inspected version/sign/reject/role-switch flows log activity rather than creating notifications directly.

Notification functionality currently supports:

- list notifications
- unread count
- mark all read
- mark one read

This is a notification surface, not evidence of complete negotiation notification automation.

## Approvals / Rejections

There are two separate approval concepts:

1. Contract version acceptance:
   - sign version
   - reject version

2. Execution approval:
   - approve/reject `ContractApprovalRequest` for execution items.

These should not be confused. Version signing is agreement acceptance. Approval requests belong to obligation execution and post-creation workflow.

## Initiator Transfer / Role Switching

Role switch flow:

```text
Counterparty requests role switch
  -> pending request expires in 7 days
Initiator confirms
  -> original contract is deleted
  -> new contract is created with roles swapped
```

Constraints:

- counterparty must be registered to become new initiator.
- signed contracts cannot role switch.
- only one pending request per contract.
- confirmation does not carry over versions, obligations, or content.

This is a destructive fresh-start flow, not a non-destructive ownership transfer.

## Current Gaps

- No structured two-sided comment thread.
- No live `RequestChange` API.
- No clause-level accept/reject.
- No explicit send transition despite `sent` status existing.
- No `negotiating` transition in live API.
- No counterparty user FK.
- No automatic notification creation found in version routes.
- Role switching deletes history instead of preserving it.

