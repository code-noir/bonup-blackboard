# BLACKBOARD_AUTHORITY_MODEL.md

> Status: Working draft — A1 complete, A2 complete, A3 pending
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

## 3. Follow-On Gaps for A3

**A3 — Contract Pro delegated-access model**
No delegated-access concept exists in the backend. A3 will need to define from scratch how Contract Pro access is granted, what it permits, and what it does not permit. This cannot be derived from current code — there is no existing delegation mechanism to extend.

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

## Summary

The current backend authority model is a two-role system: initiator and counterparty.
Role assignment is by FK (initiator) and by email field (counterparty).
The counterparty role conflates negotiation behavior (reject — non-binding) with signing authority (sign — binding, irreversible) under a single identity check.
Separating these rights requires schema and permission changes deferred to a later implementation sprint.
No authorized representative, no delegated signer, no Contract Pro, and no business-level authority scoping exists in backend code today.
