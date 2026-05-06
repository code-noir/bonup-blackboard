# Authority Architecture

> Status: Current
> Source of truth: code first, this document second
> Updated: 2026-05-06

---

## 1. Purpose

The authority layer defines who is allowed to act in the system and under what conditions.

It governs:
- contract participation authority
- business ownership authority
- delegated authority through Contract Pro

Authority is currently enforced directly in code and services, not through a unified authority model.

---

## 2. Current Code Truth

Authority is implemented across multiple layers:

### Base contract authority
- `Contract.initiator` → FK to User
- `Contract.counterparty_email` → EmailField (no FK)

Authority checks:
- initiator: `contract.initiator_id == user.pk`
- counterparty: `contract.counterparty_email == user.email`

---

### Business authority
- `BusinessEntity.owner` → FK to User

Used as:
- authority root for business contracts
- authority root for Contract Pro delegation

---

### Contract Pro delegated authority
- `ContractProAccessGrant`
- `ContractProContractAssignment`
- `ContractProPermissionRule`
- `ContractProOversightEvent`

Services:
- `ContractProGrantService`
- `ContractProPermissionService`
- `ContractProEditingService`

---

## 3. Core Concepts

### Contract Party Authority

Binary system:
- Initiator (User FK)
- Counterparty (email match)

No third role.
No role table.

---

### Business Ownership Authority

- Rooted in `BusinessEntity.owner`
- Owner is the controlling authority for business contracts

---

### Delegated Authority (Contract Pro)

- Authority is delegated via `ContractProAccessGrant`
- Scoped as:
  - business-wide
  - selected contracts

Rules:
- One active full Contract Pro per business
- Temp access limited to selected contracts

---

### Permission Matrix (Contract Pro)

- Defined in `ContractProPermissionService`
- Actions categorized as:
  - sensitive (blocked by default)
  - accessible (allowed by default)

Not fully wired to API enforcement yet.

---

## 4. Current Behavior

### Contract-level authority

- Initiator-only actions:
  - create versions
  - confirm role switch

- Counterparty-only actions:
  - sign version
  - reject version
  - request role switch

- Either party:
  - view contract
  - create/view obligations
  - execution actions

All enforced via inline checks in API views.

---

### Business authority behavior

- Business contracts are controlled by `BusinessEntity.owner`
- Personal contracts fallback to `contract.initiator`

---

### Contract Pro behavior

- Delegated authority is active only when grant status is `active`
- Editing exclusivity enforced:
  - owner cannot edit if active delegation exists
- Selected-contract and business-wide scopes resolved in service layer
- Oversight events partially recorded

---

## 5. Authority / Access Rules

- No centralized authority model exists
- No `AuthorityHolder` model
- No role-based permission system
- All enforcement is:
  - inline checks
  - service-level logic

DRF-level permissions:
- only `IsAuthenticated`

---

## 6. Relationship to Other Domains

### identity.md

- Authority is anchored to `User`
- Authentication must succeed before authority is evaluated

---

### entity_layer.md

- Future authority will be based on:
  - `Entity`
  - `Soul`
  - `AuthorityHolder`

Currently:
- authority is NOT tied to entity layer models

---

### contract_pro.md

- Contract Pro is the only implemented delegated authority system
- It extends business authority

---

## 7. Current Gaps / Deferred Work

- No `AuthorityHolder` model
- No `AppointedAuthority` system
- No unified authority abstraction
- No `counterparty_user` FK
- No `signed_by` FK on contract versions
- Counterparty role conflates negotiation and signing
- Permission matrix not wired to API enforcement
- Oversight events incomplete:
  - missing grant linkage in some events
  - missing actor in some cases
- No Contract Pro plan gate enforcement
- No personal surface delegation system
- Contract still uses flat personal/business distinction instead of entity-based authority

---

## 8. Update Rule

Update this file when:
- authority models are introduced or modified
- contract permission logic changes
- Contract Pro enforcement changes
- authority is migrated to entity layer