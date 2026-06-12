# Contract System Architecture

## Core Models

Contract system models live primarily in `backend/contracts/models.py`.

## Contract Container

`Contract` stores the agreement container:

- `initiator`: Django user who creates the contract.
- `counterparty_name`: optional display name.
- `counterparty_email`: email used for counterparty authority.
- `structure_type`: `ONE_TIME`, `ONGOING`, `COLLABORATIVE`, or `RESOLUTION`.
- `max_versions`: defaults to `3`.
- `currency`: defaults to `USD`.
- `entity_type`: `personal` or `business`.
- `entity`: optional `BusinessEntity`.
- metadata fields such as `title`, `contract_type`, `language`, `start_date`, `end_date`, `contract_value`, `jurisdiction`, `governing_law`, `confidentiality`, `dispute_resolution`, and `description`.
- `status`, `state`, `is_active`, and `version` fields.

Important implementation observation: `status`, `state`, `is_active`, and `version` exist, but current architecture docs note that not all are actively maintained by API flows.

## Contract Versions

`ContractVersion` stores immutable snapshots:

- `contract`
- `version_number`
- `created_by`
- `previous_version`
- `superseded`
- `status`
- `content_snapshot`
- `created_at`

Version statuses:

- `draft`
- `sent`
- `negotiating`
- `signed`
- `superseded`
- `archived`
- `rejected`

The model blocks general updates after creation. Only `status` and `superseded` can be updated through `save(update_fields=[...])`.

## Version Limit

Blackboard contracts have a maximum of 3 versions. This is enforced in `backend/api/contracts/version_views.py`:

- Creating a version checks `existing_count >= contract.max_versions`.
- Previous open version is marked `superseded`.
- The new version number is `existing_count + 1`.
- Warnings are returned for second-to-last and final allowed versions.

```text
v1 -> v2 -> v3
           |
           no v4 on same contract
```

After version 3, the parties need a new contract.

## Clause Handling

There is no dedicated clause model in the current inspected contract system. Contract text is stored as full text in `ContractVersion.content_snapshot`.

AI counter-contract output can include clause-level fields:

- `clause_reference`
- `concern`
- `counter_language`

Those clause objects are returned by `/api/ai/counter-contract/` and shown in `frontend/src/pages/ContractReview.tsx`, but they are not persisted as first-class backend clause records.

## Negotiation Handling

Live backend negotiation is version-based:

- Initiator creates a version.
- Counterparty signs or rejects a version.
- Creating a new version supersedes the previous open version.
- Signed contracts are locked from version creation.
- Rejected versions stop that version but may allow another version until the cap.

`RequestChange` exists as a model for structured negotiation intent, but the current architecture docs and code inspection show it is not wired to live API routes.

## Canonical Contract Structure

The current canonical structure is:

```text
Contract
  ContractVersion[]
  ContractObligation[]
  ContractServiceObligation[]
  ContractActivity[]
  ContractDocument[]
  ContractApprovalRequest[]
  ContractValueAdjustment[]
  ContractRoleSwitchRequest[]
```

Text itself is not normalized into sections/clauses server-side. The protected frontend editor in `frontend/src/pages/CreateContract.tsx` has section/tool concepts, but the backend persists version text snapshots.

## Initiator And Counterparty

Current party model:

- Initiator is a user foreign key.
- Counterparty is an email string.
- Counterparty authority is checked by comparing `contract.counterparty_email` to `request.user.email`.

There is no `counterparty_user` foreign key on `Contract`.

## Permissions

Permissions are enforced mostly inline:

- List/retrieve: user must be initiator or email-matching counterparty.
- Create contract: authenticated user becomes initiator; billing gate is checked.
- Update/delete contract: initiator only.
- Create version: initiator only.
- Sign/reject version: counterparty only.
- Request role switch: counterparty only.
- Confirm role switch: initiator only.
- Obligations/execution actions: either party.

Contract Pro delegation can block owner editing for business contracts through `ContractProEditingService`.

## Lifecycle States

Important state fields:

- `Contract.status`: `draft`, `sent`, `active`, `completed`, `archived`.
- `Contract.state`: free text defaulting to `active`; `refresh_state()` can set `fulfilled` or `at_risk`.
- `ContractVersion.status`: used for version decisions.
- `ContractObligation.state`: `active`, `due`, `grace`, `overdue`, `defaulted`, `resolved`.
- `ContractServiceObligation.state`: `active`, `due`, `overdue`, `resolved`.

Current behavior is strongest around `ContractVersion.status`. Contract container status/state are less actively managed.

## Current Gaps

- No clause table.
- No rich change request API.
- No counterparty user FK.
- No signed-by field on `ContractVersion`.
- Signing does not automatically generate obligations.
- Contract state/status fields are not fully synchronized with workflow transitions.
- Role switch deletes the original contract and creates a fresh one without carrying versions or obligations.

