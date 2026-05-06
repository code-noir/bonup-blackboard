# Contract Pro Architecture

> Status: Current
> Source of truth: code first, this document second
> Updated: 2026-05-06

---

## 1. Purpose

Contract Pro is the delegated authority system that allows a business owner to grant another user controlled access to act on contracts.

It provides:
- delegated contract editing authority
- scoped access (business-wide or selected contracts)
- permission rules per action
- oversight tracking of delegated actions

Contract Pro extends business authority. It does not replace it.

---

## 2. Current Code Truth

Core models live in:

### `backend/contract_pro/models.py`

- `ContractProAccessGrant`
- `ContractProContractAssignment`
- `ContractProPermissionRule`
- `ContractProOversightEvent`
- `ContractProAction` (constants only)

---

### ContractProAccessGrant

- Links:
  - `business → BusinessEntity`
  - `contract_pro_user → User`

Fields:
- `access_kind`: full_contract_pro | temp_contract_pro
- `access_scope`: business_wide | selected_contracts_only
- `access_status`: pending | active | declined | revoked

Constraints:
- Only one active full_contract_pro per business (DB + service enforcement)
- temp_contract_pro must use selected_contracts_only

---

### ContractProContractAssignment

- Links contracts to a grant
- Used only when scope is `selected_contracts_only`
- `unassigned_at` determines active vs historical

---

### ContractProPermissionRule

- Defines per-action permission:
  - accessible
  - blocked

Scope:
- business-level (contract = null)
- contract-level (contract FK set)

Constraints:
- unique per grant + action + contract
- unique per grant + action when contract IS NULL (business-level rules); two different grants can hold conflicting business-level rules for the same action

---

### ContractProOversightEvent

- Audit record tied to a business
- Optional:
  - contract
  - grant
  - actor

Current event types:
- `grant_activated`
- `owner_edit_blocked`

---

### ContractProAction

Defines all possible actions:
- 5 sensitive (blocked by default)
- 10 accessible (allowed by default)

---

## 3. Core Concepts

### Delegated Authority

- Authority originates from `BusinessEntity.owner`
- Delegation is granted via `ContractProAccessGrant`

---

### Scope

- business-wide → applies to all contracts
- selected-contracts-only → limited to assigned contracts

---

### Editing Exclusivity

- When delegation is active:
  - owner may be blocked from editing
  - the service layer identifies the grant as the active editor, but the `contract_pro_user` does NOT gain API-level editing rights — they are not the contract initiator, and no code path bypasses the initiator check in the contract or version views

---

### Permission Matrix

- Defined via `ContractProPermissionRule`
- Evaluated by `ContractProPermissionService`
- Applies business-level ceiling over contract-level rules

---

## 4. Current Behavior

### Grant Activation

- Only pending → active transition allowed
- Full grants limited to one per business
- Activation records `grant_activated` event

---

### Editing Enforcement

Enforced in:
- `ContractViewSet.update()`
- `ContractVersionCreateAPIView.post()`

Flow:
- check `owner_editing_allowed()`
- if blocked:
  - record `owner_edit_blocked` (only when `contract.entity_id` is not None; personal contracts are blocked but no event is recorded)
  - return 403

---

### Active Editor Resolution

Resolved by:
- `ContractProEditingService.get_active_editor_for_contract()`

Priority:
1. selected-contract assignment
2. business-wide grant

---

### Permission Evaluation

- Implemented in `ContractProPermissionService.get_effective_state()`
- Default:
  - sensitive actions → blocked
  - others → allowed

⚠️ Not wired to API enforcement yet

---

## 5. Authority / Access Rules

- Contract Pro authority derives from business ownership
- Delegated users act under grant scope and rules
- Owner authority is temporarily restricted when delegation is active
- No DRF-level permission classes — enforcement is service + inline checks

---

## 6. Relationship to Other Domains

### authority.md

- Contract Pro is the only implemented delegated authority system
- Extends `BusinessEntity.owner` authority

---

### entity_layer.md

- Still anchored to `BusinessEntity`
- Not yet migrated to `Entity`-based authority

---

### identity.md

- Requires authenticated `User`
- Delegated user must be a valid system user

---

## 7. Current Gaps / Deferred Work

- Permission matrix not enforced at API layer
- No grant lifecycle API (accept, decline, revoke)
- No oversight read API
- Only 2 oversight event types implemented
- No billing plan gate enforcement
- No temp vs full conflict guard at assignment level
- Oversight events incomplete:
  - missing grant linkage in some cases
  - not recorded for personal contracts
- No compensation system
- No session or payment event tracking
- Not migrated to entity-layer authority

---

## 8. Update Rule

Update this file when:
- Contract Pro models change
- delegation logic changes
- permission enforcement is wired to API
- oversight system expands
- authority migrates to entity layer