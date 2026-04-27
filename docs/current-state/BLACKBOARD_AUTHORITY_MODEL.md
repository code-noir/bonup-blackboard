# BLACKBOARD_AUTHORITY_MODEL.md

> Status: Working draft — A1 complete, A2 complete, A3 complete, A4 complete
> Scope: Blackboard phase-one authority baseline — code truth only
> Purpose: Record what the backend actually implements for contract authority today; separate from vision and from future design work

This document records authority model truth as it exists in the backend code now.
It is not a design document. It does not prescribe future architecture.
It is a stable reference for A3 (Contract Pro delegated access).

---

## 1. Current Backend Authority Truth

### Contract roles — what exists in code

Every contract has exactly two roles. Nothing else is implemented.

| Role | How stored | Where enforced |
|---|---|---|
| **initiator** | `Contract.initiator` — FK to `settings.AUTH_USER_MODEL` | multiple views: `contract.initiator_id == request.user.pk` |
| **counterparty** | `Contract.counterparty_email` — EmailField | multiple views: `contract.counterparty_email == request.user.email` |

Source: `backend/contracts/models.py` lines 34–44.

### Party check — `is_party()`

`backend/api/contracts/permissions.py`

```python
def is_party(user, contract) -> bool:
    return (
        contract.initiator_id == user.pk
        or contract.counterparty_email == user.email
    )
```

This is a strict binary. There is no third slot. Any user who is neither the initiator nor the email-matched counterparty is not a party to the contract.

### Full role-action map — enforced by live views

Three tiers of enforcement exist across all contract API views:

**Initiator-only** (`contract.initiator_id == request.user.pk`)

| Action | View |
|---|---|
| Create a new contract version | `ContractVersionCreateAPIView` |
| Confirm a role switch | `ContractRoleSwitchConfirmAPIView` |

**Counterparty-only** (`contract.counterparty_email == request.user.email`)

| Action | View |
|---|---|
| Sign a version | `ContractVersionSignAPIView` |
| Reject a version | `ContractVersionRejectAPIView` |
| Request a role switch | `ContractRoleSwitchRequestAPIView` |

**Any party** (`is_party()` only — initiator or counterparty)

| Action | View |
|---|---|
| View contract management summary | `ContractManagementSummaryAPIView` |
| View obligations | `ContractObligationsAPIView.get` |
| Create obligations | `ContractObligationsAPIView.post` |
| View / create approval requests | `ObligationApprovalRequestListCreateAPIView` |
| Approve an approval request | `ApprovalRequestApproveAPIView` |
| Reject an approval request | `ApprovalRequestRejectAPIView` |
| Resolve a service obligation | `ObligationResolveAPIView` |
| Resolve a payment obligation | `ContractPaymentResolveAPIView` |
| View / open execution sessions | `ObligationExecutionSessionListCreateAPIView` |
| All execution event operations | `execution_views.py` |

Note: approval approve/reject has a sub-check — if `requested_from` is set, only that specific user may decide. The base gate is still `is_party()`.

All checks are hard-coded per-request identity comparisons — not a role table, not a permission object.

### Signing identity — what is and is not recorded

`ContractVersion` has a `created_by` FK (who created this version).

`ContractVersion` does **not** have a `signed_by` FK. When a version is signed, the only record is `status = "signed"` written to the version row. The identity of who performed the signing is written to the activity log (`log_activity`) but is not stored as a FK on the version itself.

Source: `backend/contracts/models.py` lines 145–219; `backend/api/contracts/version_views.py` lines 162–171.

### Business entity — authority scoping

`BusinessEntity.owner` is a single FK to auth user. One owner per entity. There is no authorized-signers list, no representative role, and no mechanism to grant another user authority to act on behalf of a business entity.

When a contract is created under a business context, `Contract.entity` FK links to the `BusinessEntity` and `Contract.entity_type` is set to `"business"`. This scopes the contract to the entity but does not change who can sign — the counterparty email check is still the only signing authority check.

Source: `backend/users/models.py` lines 386–428; `backend/contracts/models.py` lines 60–72.

### Role switch

`ContractRoleSwitchRequest` exists: counterparty can request to swap roles with the initiator. On confirmation, the original contract is deleted and a new one is created with roles reversed.

This is a role swap mechanism, not an authority delegation mechanism. It does not create a third actor or a delegated authority — it reassigns the two fixed slots.

Source: `backend/contracts/models.py` lines 807–852.

---

## 2. Missing / Not Yet Implemented

These concepts appear in the Founder's Vision and the Gap Map. None have backend representation today.

**Authorized representative**
No schema slot. No enforcement path. There is no way to record that person B is authorized to sign on behalf of person A.

**Delegated signing authority**
No concept in the permissions module or in any version view. The counterparty check is a direct email identity match only — whoever holds that email address is treated as the counterparty. There is no explicit signing authority grant, no written-authorization record, and no audit trail for delegation.

**Signer distinct from owner**
The system does not distinguish "the person who signs" from "the person who owns the account or business." The counterparty is identified by email. If a different person holds that email, they can sign. If the intended counterparty delegates to a representative, the backend has no way to represent that.

**Business-level signing authority**
`BusinessEntity` has one owner FK. There is no authorized-signers list and no mechanism to grant signing rights to another user on behalf of the entity.

**Contract Pro role**
Not started as a backend concept. No model, no permission class, no route, no schema field.

**Negotiator role as distinct from signer**
Not separated from counterparty. See section 4.

---

## 3. A3 — Contract Pro Delegated-Access Model

> Standalone implementation-ready spec: `docs/current-state/BLACKBOARD_CONTRACT_PRO_SPEC.md`

### Current backend truth

There is no Contract Pro concept in the backend today. No model, no permission class, no grant record, no route, and no schema field. The backend has no delegated-access mechanism of any kind. The only authority model in code is the two-role initiator/counterparty system described in Section 1.

Everything in this section is the approved phase-one model definition. None of it is implemented yet. Implementation belongs to a later sprint.

---

### Approved phase-one model

#### 3.1 Contract Pro tier and account prerequisite

Contract Pro is a paid tier, not a free role.

- The user must already hold a bonUP/Blackboard account.
- Full Contract Pro activation requires subscription to the Contract Pro plan ($499).
- A user who has a standard Blackboard account but has not subscribed to Contract Pro cannot be activated as a full Contract Pro.

The billing system already supports subscription gating. Contract Pro plan gating is a named dependency for implementation but is not designed here.

#### 3.2 Owner/business cardinality

Phase-one cardinality rules:

- One active full Contract Pro per business at any time.
- No two full Contract Pros may be active in the same business simultaneously in phase one.
- One owner may own multiple businesses.
- Different businesses under the same owner may have different Contract Pros — there is no constraint that the same person serves as Contract Pro across all of an owner's businesses.
- Phase one does not support multi-owner Contract Pro operation (two owners sharing one business with separate Contract Pros is out of scope).

Enforcement of these cardinality rules requires a grant record that can be queried at the business level. The grant record is named as a required implementation artifact in 3.11 below.

#### 3.3 Temp / training exception

Temp is a narrow exception within the same business, distinct from full Contract Pro.

Rules for temp:

- Temp is per-contract only, not business-wide.
- The temp user must be on the low-tier personal Blackboard plan. Temp does not require the Contract Pro plan.
- While a full Contract Pro is active on a given contract, temp may work only on a different contract within the same business. Temp and full Contract Pro may not hold active delegation on the same contract simultaneously.
- Temp compensation is commission-only. Commission is held until the return/refund policy window passes before release.

Promotion path from temp to full Contract Pro:

1. Owner revokes the temp relationship.
2. The user upgrades to the Contract Pro plan.
3. Owner activates the full Contract Pro relationship.

Temp cannot be promoted by upgrading the plan alone. The revocation step is required to clear the temp grant before a full activation can occur.

#### 3.4 Access grant model and relationship lifecycle

Access is always explicit. There is no implicit access from messaging, session participation, subscription status, or ordinary user status.

The relationship lifecycle has four statuses:

| Status | Meaning |
|---|---|
| **pending** | Owner has initiated a grant; Contract Pro has not yet accepted |
| **active** | Grant is accepted and the Contract Pro has live delegated access |
| **declined** | Contract Pro declined the pending grant |
| **revoked** | Owner revoked an active or pending grant |

Grant scope has two levels:

- **Business-wide** — the Contract Pro is granted access across the business, subject to the permission matrix.
- **Selected-contract** — the Contract Pro is granted access only on specific named contracts.

Business-level permission settings override contract-level settings. A contract-level permission cannot grant more than the business-level ceiling.

Grant is initiated by the owner from the Oversight surface. Owner-initiated means there is no self-grant path for a Contract Pro.

#### 3.5 Permission model

Permissions are defined as a matrix with per-action accessible/blocked states. Permissions exist at two levels:

- **Business level** — set by the owner; applies across all contracts in the business unless a contract-level setting is more restrictive.
- **Contract level** — set by the owner per contract; may further restrict but not expand beyond business level.

Each business has its own independent permission matrix.

**Default state — mostly open for contract work:**

| Action | Default |
|---|---|
| Create new contracts | Accessible |
| Edit delegated contract workspace | Accessible |
| View contract content | Accessible |
| Create obligations | Accessible |
| View obligations | Accessible |
| Create execution sessions | Accessible |
| View activity on delegated contracts | Accessible |
| Message owner via Oversight | Accessible |

**Default state — blocked unless owner explicitly unlocks:**

| Action | Default |
|---|---|
| Sign on behalf of owner | Blocked |
| Trigger payment request | Blocked |
| Change payout / banking destination | Blocked |
| Approve payment release | Blocked |
| Modify business-level settings | Blocked |

Payment-related permissions are broken into separate items. There is no single "payment flag." Each payment action (trigger request, approve release, change destination) is a distinct permission item the owner can independently configure.

Owner can change permission settings at any time. A change takes effect for future actions; it does not retroactively alter completed actions.

#### 3.6 Contract work and editing exclusivity

While a Contract Pro holds active delegation on a contract:

- Only the Contract Pro edits the delegated workspace.
- Owner may read, comment, request changes, message, join a session, sign where needed, and revoke.
- Owner may not co-edit while Contract Pro delegation is active.

If the owner wants direct editing control, the owner must revoke the Contract Pro delegation first. After revocation, the owner regains direct editing access.

If the owner later assigns a new Contract Pro to the same contract, the owner again loses direct in-place editing while the new delegation is active.

This is an intentional design constraint: delegation is exclusive editing authority, not shared editing authority.

#### 3.7 Counterparty visibility

The counterparty does not see Contract Pro or temp labels.

- The role is internal.
- Internal uses: permission enforcement, Oversight display, activity/audit records, compensation tracking.
- External presentation to the counterparty uses whatever public-facing identity the owner configures.

This applies to both full Contract Pro and temp.

#### 3.8 Payment and money safety

Payment safety rules are non-negotiable defaults:

- Business-owned payment rails only. Contract Pro has no custody of business money.
- Changing the payout or banking destination is blocked by default and requires explicit owner permission to unlock.
- Triggering a payment request is blocked by default.
- Approving a payment release is blocked by default.

These defaults exist to prevent a compromised or unauthorized Contract Pro from redirecting business funds. Owner may unlock individual payment permissions from the permission matrix, but the default is always locked.

#### 3.9 Compensation model

Full Contract Pro:

- Compensation structure is flexible and defined per the broader product spec.
- Compensation terms are set at the time of the grant relationship, not by the permission matrix.

Temp:

- Commission-only. No other compensation structure is available for temp.
- Commission is held until the return/refund policy window closes before it is released.

Compensation tracking is a named dependency for implementation. The compensation model is not designed further here.

#### 3.10 Communication and Oversight

Owner visibility requirements:

- Owner must be able to see all Contract Pro activity on delegated contracts through the Oversight surface.
- Oversight is the canonical owner view of delegated work — not a secondary or optional surface.

Communication requirements:

- Owner and Contract Pro need both async and sync communication support.
- Small coordination between owner and Contract Pro should not require entering Boardroom for every exchange.
- A lighter communication channel within the Oversight surface is a named requirement. Its implementation is deferred.

---

### What is deferred beyond phase one or to later implementation

The following are explicitly out of scope for A3 and for phase-one model definition:

- **Multi-owner Contract Pro operation** — two owners in one business each managing separate Contract Pros is deferred.
- **Automated promotion from temp** — system-triggered promotion on plan upgrade is deferred; phase one requires manual revoke-then-activate.
- **Audit trail depth and structure** — the requirement is named (owner must see all Contract Pro activity); the auditability design is deferred to A4.
- **Compensation engine design** — the compensation terms model is deferred to a later implementation sprint.
- **Counterparty disclosure edge cases** — scenarios where a counterparty legally requires disclosure of a representative are deferred.
- **Schema design** — record structure for grant records, permission matrices, and relationship lifecycle is deferred to the implementation sprint.
- **Permission matrix UI** — the Oversight interface for owner-side permission configuration is deferred to UI design.
- **Communication channel implementation** — the lightweight owner/Contract Pro communication channel within Oversight is deferred.
- **Billing integration** — wiring the Contract Pro plan subscription gate to the grant activation flow is deferred.

---

### Required record families (named for implementation, not yet designed)

Implementation will require at minimum:

- **Grant record** — links owner, business, Contract Pro user, scope (business-wide or per-contract), status, and timestamps.
- **Permission matrix** — per-business and per-contract permission states; keyed to a defined action list.
- **Relationship status history** — append-only log of status transitions (pending → active, active → revoked, etc.) with timestamps and acting user.

These are named at the model-definition level only. Schema design and migration belong to the implementation sprint.

---

## 4. A2 — Negotiator vs Signer Distinction

### What the code conflates

The counterparty role currently bundles two qualitatively different behaviors under a single identity check:

| Action | Nature | Effect |
|---|---|---|
| Reject a version | Negotiation behavior | Non-binding. Signals the offer is not acceptable. Initiator may create another version (up to `max_versions`). Contract is not locked. |
| Sign a version | Signing authority | Binding. Locks the contract permanently. All future version creation is blocked. State is irreversible. |

Both are enforced by the identical check:

```python
if contract.counterparty_email != request.user.email:
    return Response({"error": "..."}, status=HTTP_403_FORBIDDEN)
```

There is no sub-distinction. Whoever is the counterparty by email identity has both negotiation rights and signing authority simultaneously. There is no configuration, no grant, and no schema field that separates them.

### Why this matters

Rejection is a non-binding negotiation signal. Signing is a final binding commitment. In the current model, any user who holds the counterparty email address can do both — there is no mechanism to say "this person may negotiate on my behalf but may not bind me." This is the core gap the Founder's Vision identifies when it distinguishes negotiator from signer.

### Current constraint — stated as fact

Separating negotiation rights from signing authority in the backend is not possible without:

1. A schema change — either a new role or permission field, or an explicit signing-authority grant record
2. A permission change — two distinct checks in `ContractVersionSignAPIView` and `ContractVersionRejectAPIView` instead of the same counterparty email match

Neither change is made here. This is a documented constraint, not a resolved design. The implementation belongs to a later sprint.

### What is not ambiguous even in the current model

Even without a separated negotiator role, the following is structurally enforced today:

- Only the initiator can propose new contract terms (create versions).
- Only the counterparty can accept or refuse a proposal (sign or reject).
- Neither party can sign their own proposal — the initiator is explicitly blocked from signing.
- Signing locks the contract; rejection does not.
- These rules hold regardless of what the parties negotiated, agreed verbally, or intended — the backend enforces the role boundary.

The current model is not broken. It is coarse. Negotiation rights and signing authority are bundled into the counterparty slot. That bundling is the constraint A2 names and defers.

### What remains for later implementation

- A schema-level mechanism to separate negotiator rights from signing authority (e.g., an explicit signing-authority grant, a sub-role field, or a separate authorized-signer record)
- A permission-level change to enforce the distinction in `ContractVersionSignAPIView`
- Any associated audit trail for who held signing authority and when

These are not designed here. They are named so the implementation sprint starts from a clear problem statement, not from rediscovering this ambiguity.

---

## 5. A4 — Delegated-Access Auditability Requirements

### Purpose

This section defines the minimum auditability requirements for Contract Pro delegated access in phase one. It does not implement new backend infrastructure. It defines what must be recorded, what scope and field expectations apply to audit records, and what is explicitly deferred.

The goal: later implementation sprints have a clear audit target, not a vague requirement to "log things."

---

### 5.1 Current event implementation — anchored to code

Source: `backend/contract_pro/models.py`, `backend/contract_pro/services.py`, `backend/api/contracts/viewsets/contract_viewset.py`, `backend/api/contracts/version_views.py`

**Model: `ContractProOversightEvent`**

Fields currently implemented:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | auto-generated |
| `business` | FK → BusinessEntity | always required; CASCADE |
| `contract` | FK → Contract | nullable; CASCADE |
| `grant` | FK → ContractProAccessGrant | nullable; SET_NULL |
| `actor` | FK → AUTH_USER_MODEL | nullable; SET_NULL |
| `event_type` | CharField (choices) | from defined constants only |
| `created_at` | auto_now_add | never overridden |

**Event types implemented:**

| Event type | Trigger | Grant populated | Actor populated |
|---|---|---|---|
| `grant_activated` | `ContractProGrantService.activate_grant()` | Yes | No — service has no HTTP context |
| `owner_edit_blocked` | `ContractViewSet.update()` and `ContractVersionCreateAPIView.post()` on 403 path | No — not populated at call sites | Yes — `request.user` |

**Known gaps in the current implementation:**

- `owner_edit_blocked` events do not populate the `grant` FK. The active grant is not fetched at the call site to avoid an extra query. This is a gap relative to the minimum field requirements defined below.
- No `event_payload` or structured context field exists on the model. Events have scope (business, contract) but no content describing what specifically happened.
- `grant_activated` does not record the actor. Any future audit of "who activated this grant" requires inferring from the grant's `accepted_at` field rather than reading the event record directly.

---

### 5.2 Required minimum event coverage

The following event types are required at minimum for phase-one Contract Pro auditability. Not all are implemented today. The implementation status is noted for each.

#### 5.2.1 Grant lifecycle events

| Event | When | Implemented |
|---|---|---|
| Grant created (invite sent) | Owner creates a pending grant | No |
| Grant activated | CP accepts; grant moves to active | Yes — `grant_activated` |
| Grant declined | CP declines the pending invite | No |
| Grant revoked | Owner revokes an active or pending grant | No |
| Grant scope changed | Owner changes business-wide ↔ selected scope on an existing grant | No |
| Grant permission rule changed | Owner adds, changes, or removes a permission rule on an existing grant | No |

The grant created event is the origin record for the entire delegated-access lifecycle. It must record who created the grant, for which business, for which CP user, and at what time.

Revocation is the critical safety event. It must be recorded regardless of the grant's prior state, and it must be visible in Oversight immediately.

#### 5.2.2 Editing and control events

| Event | When | Implemented |
|---|---|---|
| Owner edit blocked | Owner attempts to edit a contract while active delegation controls it | Yes — `owner_edit_blocked` |
| Contract assigned to grant | A contract is explicitly assigned to a selected-scope grant | No |
| Contract unassigned from grant | A contract is removed from a selected-scope grant | No |
| Editing authority restored | Delegation revoked; owner regains direct editing access | No — derivable from revocation but must be surfaced |

The editing authority restored event may be derived from the revocation record but should be surfaced as a distinct visible signal so the owner can confirm that editing control has returned.

#### 5.2.3 Contract-work events

These events record actions taken by the delegated CP on contracts under delegation.

| Event | When | Implemented |
|---|---|---|
| Contract created under delegation | CP creates a contract on a business the grant covers | No |
| Contract version created under delegation | CP creates a new version on a delegated contract | No |
| Contract updated under delegation | CP makes a significant field update on a delegated contract | No |
| Owner review requested | CP requests owner sign-off or review | No |
| Counterparty signed — delegated contract | Counterparty signs a contract that is under active CP delegation | No |
| Owner signed — delegated contract | Owner signs a contract that is under active CP delegation | No |

"Significant update" in practice means a save that changes contract-level fields, not every keystroke. The implementation sprint will define the threshold. The requirement is that the owner can see what content changed and when.

#### 5.2.4 Session events — requirements level

Session infrastructure is not yet implemented. The following records are named at the requirements level. Implementation belongs to the session build sprint.

| Event | When | Notes |
|---|---|---|
| Session started | CP or owner starts a Boardroom or External Session linked to a delegated contract | Must record session type, who started, linked contract |
| Participant joined | Any participant joins the session | Must record role (owner / contract_pro / counterparty) |
| Session extended | Any authorized participant extends the session | Must record who extended, by how much, extension policy at time |
| Recording started | Recording is activated | Must record who triggered |
| Recording stopped | Recording ends | Must record who triggered |
| Signature occurred in session | A version is signed during a live session | Must link to version and contract |
| Payment request triggered in session | A payment request is triggered during a live session | Must link to contract and amount |

#### 5.2.5 Payment events

| Event | When | Notes |
|---|---|---|
| Payment request triggered by CP | CP triggers a payment request (requires owner permission) | Must record actor, contract, amount, permission state at time |
| Sensitive payment action blocked | CP attempts a blocked payment action | Must record actor, action attempted, contract |
| Sensitive payment action used | CP uses a payment action that owner explicitly unlocked | Must record actor, action, contract, permission state at time |

Payment events are high-trust events. They must always record the actor, the specific action, the contract context, and the permission state that allowed or blocked the action at the time the event occurred.

#### 5.2.6 Compensation and relationship visibility

The owner must be able to see the full compensation state for each Contract Pro relationship at any point.

Minimum requirement: compensation state transitions must be recorded and visible through Oversight.

| State transition | Must be visible |
|---|---|
| tracked → earned | Yes |
| earned → held | Yes |
| held → releasable | Yes |
| releasable → paid | Yes |
| Any state → reversed | Yes |
| Any state → disputed | Yes |

There is no hidden financial state between the owner and the delegated relationship. Any compensation that exists, is held, or has been paid must be visible to the owner. This is a hard requirement, not a nice-to-have.

Compensation events may use the same audit record family as grant and editing events, or a linked compensation-specific record. The implementation sprint will decide the record placement. The requirement is visibility, not a specific schema.

---

### 5.3 Minimum record structure requirements

These are the minimum field expectations for any delegated-access audit record.

| Field | Required | Notes |
|---|---|---|
| `id` | Always | Stable unique identifier for each event; UUID preferred |
| `business` | Always | Authority anchor; never null; identifies whose business context this event belongs to |
| `event_type` | Always | From a defined constant list; no free-text event types |
| `created_at` | Always | Set at insert time; never overridden by callers |
| `actor` | When a human actor exists | Null only for purely system-generated events; must be populated for any event triggered by a request |
| `contract` | When the event is contract-scoped | Null only for business-level events (e.g., scope changes, cardinality enforcement) |
| `grant` | When the event is grant-related | Must be populated wherever the grant is the subject of the event or is naturally available at the call site; not optional when the grant is known |
| `event_payload` | Always for minimum phase-one quality | Structured JSON context for the event. Content defined per event type. Minimum: what changed or was attempted, outcome, and enough context to support Oversight display and dispute review without reconstructing state from other tables |

**Specific gap to close from current implementation:**

The `grant` FK on `owner_edit_blocked` events is currently null because the call sites do not fetch the active grant before returning 403. This is below the minimum bar. The implementation sprint that adds `event_payload` should also populate the `grant` FK on this event type, even if it requires one additional query at the blocking call site.

---

### 5.4 Explicitly deferred beyond phase one

The following are out of scope for A4 and for phase-one minimum auditability. They must not be assumed in implementation planning unless explicitly scheduled.

| Item | Deferred to |
|---|---|
| Session event recording implementation (model, wiring, all call sites) | Session build sprint |
| Payment event recording implementation | Payment build sprint |
| Compensation event recording implementation | Compensation engine sprint |
| `event_payload` schema standardization — field-level content spec per event type | Implementation sprint |
| Oversight read API (owner-facing endpoint to query oversight events) | Oversight API sprint |
| Oversight UI surface for owner event review | UI design sprint |
| Notification delivery triggered by oversight events | Notification sprint |
| Dispute review surface using audit records | Post-phase-one |
| Retention policy and archive policy for oversight event records | Post-phase-one |
| Auditability requirements for non-Contract Pro delegated actions | Post-phase-one |

---

## Summary

The current backend authority model is a two-role system: initiator and counterparty.
Role assignment is by FK (initiator) and by email field (counterparty).
The counterparty role conflates negotiation behavior (reject — non-binding) with signing authority (sign — binding, irreversible) under a single identity check.
Separating these rights requires schema and permission changes deferred to a later implementation sprint.
No authorized representative or delegated signer exists in backend code today.
Contract Pro foundation code is implemented: access grants, permission matrix, editing exclusivity enforcement, and oversight event recording are in place. Business-level authority scoping exists via `ContractProAccessGrant` anchored to `BusinessEntity`. Full auditability coverage remains incomplete — minimum requirements are defined in Section 5.
