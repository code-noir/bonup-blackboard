# Contract Lifecycle Architecture

> Status: Current
> Source of truth: code first, this document second
> Updated: 2026-05-06

---

## 1. Purpose

The contract lifecycle defines how agreements are created, negotiated, versioned, and finalized between two parties.

It governs:
- contract creation
- version iteration
- signing and rejection
- role switching between parties

The lifecycle ends at signing. Post-signing behavior belongs to the obligations lifecycle.

---

## 2. Current Code Truth

Core models live in:

### `backend/contracts/models.py`

- `Contract`
- `ContractVersion`
- `ContractRoleSwitchRequest`
- `RequestChange` (not wired to API)

---

### Contract

Key fields:

- `initiator` → FK to User
- `counterparty_email` → EmailField (no FK)
- `entity_type` → personal | business
- `entity` → FK to BusinessEntity (nullable)
- `max_versions` → version cap
- `state` → no formal choices defined on the field; values `active`, `fulfilled`, `at_risk` are set only by `refresh_state()`, which is never called from any API view
- `status` → draft | sent | active | completed | archived (not used in API)
- `is_active` → Boolean (not updated by API)
- `version` → counter field (not used)

---

### ContractVersion

- Immutable snapshot model
- Fields:
  - `version_number`
  - `created_by`
  - `previous_version`
  - `status` → draft | sent | negotiating | signed | superseded | archived | rejected
  - `content_snapshot`
- After creation:
  - only `status` and `superseded` can change

---

### ContractRoleSwitchRequest

- Handles role switching between initiator and counterparty
- Status:
  - pending | confirmed | expired
- TTL:
  - 7 days

---

### RequestChange

- Defined but not connected to API
- Represents negotiation intent
- Currently not used in live lifecycle

---

## 3. Core Concepts

### Version-Based Negotiation

- Contracts evolve through versions
- Each version is immutable after creation
- New versions supersede previous ones

---

### Binary Party Model

- Initiator (User FK)
- Counterparty (email match)

No third role exists.

---

### Personal vs Business Context

- `entity_type` determines contract context
- Business contracts link to `BusinessEntity`
- Personal contracts rely only on initiator

---

## 4. Current Behavior

### Contract Creation

- Billing gate enforced
- Initiator always set to request user
- Business contracts require ownership of `BusinessEntity`
- Contract starts with no versions

---

### Version Creation

- Initiator-only action
- Contract Pro edit gate enforced
- Cannot create version if a signed version exists
- Cannot exceed `max_versions`
- Previous version marked as `superseded`
- New version created as `draft`

---

### Signing Flow

- Counterparty-only action
- Version must not be in terminal state
- Sets `version.status = "signed"`
- Does NOT create obligations

---

### Rejection Flow

- Counterparty-only action
- Sets `version.status = "rejected"`
- Emits warnings near version limits

---

### Role Switching

Two-step process:

1. Request (counterparty)
   - Creates request
   - One pending request allowed

2. Confirm (initiator)
   - Deletes original contract
   - Creates new contract with swapped roles
   - No versions or obligations carried over

---

### Version Status Behavior

Defined state machine exists but is NOT used by API.

Live transitions in practice:
- draft → signed
- draft → rejected
- any active → superseded (on new version)

These are accurate in practice because `sent` and `negotiating` are never set by the API. However, the code enforces only "not in a terminal state" before allowing signing or rejection — both transitions are technically permitted from any non-terminal status.

Statuses `sent` and `negotiating` are defined but unused.

---

## 5. Authority / Access Rules

All authority is enforced inline:

- View contract:
  - initiator OR counterparty email match

- Create version:
  - initiator-only

- Sign / reject:
  - counterparty-only

- Update contract:
  - initiator-only + Contract Pro edit gate

- Role switch request:
  - counterparty-only

- Role switch confirm:
  - initiator-only

No centralized permission system.

---

## 6. Relationship to Other Domains

### authority.md

- Lifecycle relies on:
  - initiator authority
  - counterparty email match
- Contract Pro affects editing rights only

---

### contract_pro.md

- Contract Pro enforces editing exclusivity
- Does not affect signing authority

---

### entity_layer.md

- Business contracts link to `BusinessEntity`
- Not yet migrated to full entity-based authority

---

### obligations_lifecycle.md

- Contract lifecycle ends at signing
- Obligations lifecycle begins after signing
- No automatic transition currently enforced

---

## 7. Current Gaps / Deferred Work

- `Contract.status` not used by API
- `Contract.state` not triggered
- `Contract.is_active` not updated
- `Contract.version` not used
- `RequestChange` not wired to API
- Engine state machine not used
- No transition to `sent` or `negotiating`
- No `counterparty_user` FK
- No `signed_by` FK on versions
- Signing identity only recorded in activity logs
- No automatic obligation creation after signing
- Role switch deletes and recreates contract (destructive flow)

---

## 8. Update Rule

Update this file when:
- contract or version models change
- lifecycle transitions are added or modified
- authority enforcement changes
- engine state machine becomes active
- obligations integration is wired to signing
