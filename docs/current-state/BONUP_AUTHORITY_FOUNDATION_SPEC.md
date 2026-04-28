# BONUP_AUTHORITY_FOUNDATION_SPEC.md

> Status: Active spec — answers locked, build sequence defined
> Scope: bonUP-layer authority and governance foundation — pre-code design pass
> Purpose: Answer the five unresolved design questions before any model work begins; establish safe build sequence; prevent Contract Pro authority root breakage during platform expansion

This document is a spec, not a current-state description.
Nothing in this document is implemented in code yet unless explicitly noted.
Implementation sprints must reference this document and must not diverge from it without a recorded design decision.

---

## 1. Why This Spec Exists

Current repo truth (as of the inspection pass on 2026-04-28):

- `BusinessEntity.owner` is a live FK to `settings.AUTH_USER_MODEL` and is the authority root for Contract Pro grants. The `ContractProAccessGrant` derives owner via `grant.business.owner`.
- `Contract.entity_type` is a flat two-choice field: `personal` or `business`. No other entity types exist in code.
- `Trust` exists only as a `business_type` string value inside `BusinessEntity`. It is not a first-class entity type.
- No `Soul`, `Entity`, `AuthorityHolder`, `AppointedAuthority`, or `Operator` model exists anywhere in backend code.

Attempting code-first expansion of the authority layer without this spec risks:

- Breaking the Contract Pro `grant.business.owner` derivation chain
- Creating a `Soul` model whose relationship to `User` is wrong, forcing a destructive migration
- Building `AuthorityHolder` before its anchor (`Entity`) is defined
- Building `AppointedAuthority` before `AuthorityHolder` is stable
- Migrating `BusinessEntity.owner` prematurely and losing the current permission root

This spec answers the questions that must be settled before any of that work begins.

---

## 2. Structural Concept Definitions

These definitions are locked for the purposes of this spec and all implementation work that follows.

### User

The system account / bonID account.

`User` is the Django authentication identity. It holds credentials, email, bonID (via `BonUserProfile`), subscription state, and billing information. It is the authentication principal for all API requests.

`User` is **not** the natural human actor. It is the system representation of that actor.

Future FKs in the authority layer should not default to `User` when the intent is to reference a natural human or an operating entity. The appropriate anchor depends on what the FK is actually representing.

### Soul

The natural human actor.

`Soul` represents the real individual who is the human behind one or more system accounts, entities, or roles. A `Soul` is always a natural person. There is at most one `Soul` per natural person.

`Soul` is a bonUP-layer concept. It sits above any individual product (Blackboard, SOL, future verticals). Products do not own `Soul`.

Key properties:
- A `Soul` is linked to exactly one `User` account in the primary case. The direction of the FK is `Soul → User` (Soul holds the FK to User, not the reverse).
- In phase one, a `Soul` cannot exist without an associated `User`. The scope for representing a Soul who has not yet registered is deferred.
- `Soul` is the correct anchor for personal operating surfaces (personal contracts, personal obligations, personal bonID identity).
- `Soul` is **not** a business, trust, or legal entity. Those are `Entity` subtypes.

### Entity

The broader operating/legal actor class.

`Entity` is a supertype. It represents any actor that can hold contracts, own property, incur obligations, or exercise authority — whether that actor is a natural person acting in a personal capacity, a business, or another legal form.

Entity subtypes in phase one:

| Subtype | Maps to today | Notes |
|---|---|---|
| `soul_entity` | Personal contract context (`entity_type = "personal"`) | A natural person acting as an operating actor in their own right |
| `business_entity` | `BusinessEntity` | A formal business structure (LLC, Corp, Trust, etc.) |

`Entity` does not immediately replace `BusinessEntity` in code. The migration path is defined in Section 6. For now, `Entity` is the conceptual supertype; `BusinessEntity` remains the implementation anchor.

A `soul_entity` is not the same as a `Soul`. A `Soul` is the natural person. A `soul_entity` is that person acting as an operating actor (contracting, owning obligations, etc.). In practice, a `Soul` will have exactly one corresponding `soul_entity` for their personal operating surface.

### AuthorityHolder

The top acting authority for an entity.

`AuthorityHolder` is the person or role that holds primary authority to act for a given `Entity`. For a business, this is the owner or principal. For a soul entity, this is the `Soul` themselves.

`AuthorityHolder` is not a free-floating concept. It is always attached to exactly one `Entity`.

In the current backend, `BusinessEntity.owner` is the functional equivalent of `AuthorityHolder` for business entities. The migration path (Section 6) defines how this transitions.

Properties:
- One primary `AuthorityHolder` per `Entity` at any point in time.
- An `AuthorityHolder` may appoint `AppointedAuthority` roles under themselves.
- An `AuthorityHolder` may also act as `AuthorityHolder` for multiple entities (one person owning multiple businesses is already supported today).

### AppointedAuthority

An authority role appointed by an `AuthorityHolder` to act on behalf of an `Entity`, within defined bounds.

`AppointedAuthority` is the generalization of the Contract Pro role. The current `ContractProAccessGrant` is the first concrete implementation of what will eventually be called an `AppointedAuthority` grant.

Properties:
- Always appointed by an `AuthorityHolder`.
- Always scoped to a specific `Entity` (and optionally to specific contracts within that entity).
- Scope and permissions are bounded by the `AuthorityHolder`'s grant — no self-elevation.
- Multiple `AppointedAuthority` roles may exist under one `AuthorityHolder` for different entities or different purposes, subject to cardinality rules per entity.

In phase one, only one concrete `AppointedAuthority` role exists: Contract Pro. Future roles (e.g., Legal Representative, Financial Manager) are deferred.

### Operator

A delegated worker role that sits under an `AuthorityHolder` or `AppointedAuthority`.

`Operator` is not implemented in phase one. It is named here to complete the hierarchy definition.

An `Operator` handles execution-level work (tasks, sessions, obligation resolution) under the direction of either an `AuthorityHolder` or an `AppointedAuthority`. An `Operator` does not hold authority to sign contracts or make structural decisions unless explicitly granted.

**Implementation of `Operator` is explicitly deferred until `AuthorityHolder` and `AppointedAuthority` are fully implemented and stable.**

---

## 3. The Five Resolved Design Questions

### Q1 — What is the exact relationship between `User` and `Soul`?

**Answer: One-to-one. Soul holds the FK to User. Soul cannot exist without a User in phase one.**

Full ruling:

- `Soul` has a one-to-one FK to `User` (`Soul.user = OneToOneField(AUTH_USER_MODEL)`).
- The FK direction is `Soul → User` (not `User → Soul`). This keeps the `User` model clean and avoids Django auth model extension.
- A `Soul` requires a `User` account to exist in phase one. The scope of representing a person who has been named in a contract but has not registered yet is deferred. That scenario belongs to the counterparty invitation flow and will be addressed in the counterparty identity gap sprint (Gap 1 and Gap 2 in BLACKBOARD_AUTHORITY_MODEL.md A5).
- `Soul` is a bonUP-layer model, not a Blackboard-layer model. It should live in a new app (`bonup/` or `identity/`), not in `backend/users/`.
- Existing `BonUserProfile` is not replaced by `Soul`. `BonUserProfile` holds bonID state and email verification state. `Soul` holds human-actor identity at the bonUP layer. They coexist as separate concerns.
- Future FKs that want to reference the natural human actor should point to `Soul`, not to `User` and not to `BonUserProfile`.

**FK direction summary:**

```
Soul ──FK──> User (one-to-one)
BonUserProfile ──FK──> User (one-to-one, already exists)
```

### Q2 — What is `Entity`?

**Answer: `Entity` is a conceptual supertype in this spec. It does not immediately replace `BusinessEntity` in code. `BusinessEntity` remains the implementation anchor for Contract Pro grants in phase one.**

Full ruling:

- `Entity` as a Django model supertype will be introduced in a dedicated migration sprint — not in the Soul introduction sprint.
- The implementation approach for `Entity` as a Django model is an open design decision to be resolved at the Entity migration sprint. Two viable approaches exist — concrete base model with multi-table inheritance, or a content-type–linked abstract anchor — and they are not equivalent. They have different migration implications for existing FKs pointing to `BusinessEntity`. This spec does not choose between them. The Entity migration sprint must open with a design decision on this point before any model is written. `BusinessEntity` will be the first concrete entity subtype wired to whichever approach is chosen.
- `soul_entity` (the personal operating surface for a `Soul`) will be the second subtype.
- Until the `Entity` migration sprint runs: the current `Contract.entity_type = "personal" | "business"` flat field remains as-is. It is stale design but safe to leave until the entity layer exists.
- Until the `Entity` migration sprint runs: Contract Pro grants continue to anchor to `BusinessEntity` directly.
- `Trust` should become a `business_entity` subtype with a `legal_form = Trust` attribute — not a separate entity type. Its current position as a `business_type` choice value in `BusinessEntity` is consistent with this decision.

**Entity type map (post-migration):**

| Entity subtype | legal_form values | Replaces |
|---|---|---|
| `soul_entity` | n/a (natural person) | `entity_type = "personal"` on Contract |
| `business_entity` | LLC, Corp, Partnership, Non-Profit, Trust, S-Corp, C-Corp, Sole Proprietor, Other | `entity_type = "business"` + `BusinessEntity` |

### Q3 — What is `AuthorityHolder`?

**Answer: `AuthorityHolder` is the replacement for `BusinessEntity.owner` in the target architecture. It does not replace it immediately — the transition happens in the Entity migration sprint, not the Soul sprint.**

Full ruling:

- In the target architecture: `AuthorityHolder` is a relation record that links a `Soul` to a specific `Entity`, with a role of primary authority. In phase one, the authority-holding actor is always a `Soul`. Entity-held authority (one entity holding authority over another) is explicitly deferred — see Section 8.
- In phase one (before the Entity migration sprint): `BusinessEntity.owner` continues to serve as the functional `AuthorityHolder` for business entities. This must not be touched until the migration sprint explicitly replaces it.
- When the migration sprint runs: `BusinessEntity.owner` will be migrated to point to an `AuthorityHolder` record (or removed in favor of the `AuthorityHolder` relation). The Contract Pro `grant.business.owner` derivation will be updated to `grant.business.authority_holder` or equivalent.
- The cardinality rule (one primary `AuthorityHolder` per entity at any time) mirrors the current single `owner` FK.
- For personal operating surfaces (`soul_entity`): the `AuthorityHolder` is always the `Soul` themselves. There is no separate appointment.

**Interim authority root (phase one):**

```
BusinessEntity.owner (FK to User)  ←  still live; do not change until migration sprint
```

**Target authority root (post-migration):**

```
AuthorityHolder.soul (FK to Soul) + AuthorityHolder.entity (FK to Entity)
```

### Q4 — What should Contract Pro eventually anchor to?

**Answer: Staged. Contract Pro anchors to `BusinessEntity` now. After the Entity migration sprint, it anchors to `Entity`. After the AuthorityHolder migration sprint, owner derivation anchors to `AuthorityHolder`.**

Full ruling:

**Stage 1 (now — current code):**
- `ContractProAccessGrant.business` → FK to `BusinessEntity`
- Owner derived via `grant.business.owner`
- No change to this in the Soul sprint

**Stage 2 (Entity migration sprint):**
- `ContractProAccessGrant.business` → FK to `Entity` (with `BusinessEntity` as the subtype)
- OR: `ContractProAccessGrant.entity` replaces `.business` FK with broader entity anchor
- Owner still derived via `grant.entity.owner` until Stage 3

**Stage 3 (AuthorityHolder migration sprint):**
- Owner derivation updated from `grant.entity.owner` to `grant.entity.authority_holder`
- The `AppointedAuthority` generalization may replace `ContractProAccessGrant` at this stage, or `ContractProAccessGrant` may become a concrete subtype of `AppointedAuthority`

No stage 2 or stage 3 work is approved until the respective sprint is scheduled. Stage 1 remains live and protected.

### Q5 — What should `AppointedAuthority` anchor to?

**Answer: `AppointedAuthority` anchors to `Entity` and is appointed by an `AuthorityHolder`. It cannot be built until both `Entity` and `AuthorityHolder` are implemented. In phase one, `ContractProAccessGrant` is the concrete implementation of this concept.**

Full ruling:

- The correct anchor for `AppointedAuthority` is `Entity` (not `BusinessEntity` directly, and not `User`).
- `AppointedAuthority` is appointed by an `AuthorityHolder` — there is no self-grant path.
- Before `Entity` and `AuthorityHolder` exist as models, `AppointedAuthority` as a generalized model cannot and should not be built.
- In phase one, `ContractProAccessGrant` continues to serve as the sole concrete implementation of the `AppointedAuthority` concept. It is not renamed or restructured in this sprint. It remains anchored to `BusinessEntity` as per Stage 1 above.
- When `AuthorityHolder` and `Entity` are stable, `ContractProAccessGrant` will either:
  - become a concrete subtype of a new `AppointedAuthorityGrant` base model, or
  - be migrated to anchor directly to `Entity` and reference `AuthorityHolder` as the granting principal
  That decision belongs to the AppointedAuthority implementation sprint, not to this spec.

---

## 4. Personal vs Business Operating Surfaces

These are the two primary operating surfaces for a bonUP user in phase one.

### Personal operating surface

- The `Soul` is acting in their own right as a natural person.
- Contracts, obligations, and sessions on this surface are personal.
- The identity anchor for this surface is `soul_entity` (post-Entity-migration) or `entity_type = "personal"` (current).
- There is no `AppointedAuthority` delegation on the personal surface in phase one. On the personal surface, no `AuthorityHolder` relation record is created — the `Soul` acts with implicit self-authority over their own `soul_entity`. This is a structural simplification, not an identity claim: it does not mean the `Soul` model and the `AuthorityHolder` model are the same thing.
- Temp / Contract Pro roles do not apply to the personal surface. They are a business-entity feature only.

### Business operating surface

- The `Soul` is acting as `AuthorityHolder` for a `BusinessEntity`.
- Contracts, obligations, and sessions on this surface are owned by the entity.
- `AppointedAuthority` (currently: Contract Pro) may be granted on this surface.
- The identity anchor for this surface is `BusinessEntity` (current) or `business_entity` subtype of `Entity` (post-migration).
- All authority and delegation rules from BLACKBOARD_AUTHORITY_MODEL.md Section 3 apply here.

### Blackboard's position

Blackboard consumes this surface structure. Blackboard is not the owner of the `Soul` model, the `Entity` supertype, or the `AuthorityHolder` concept. Those belong to the bonUP layer. Blackboard builds on top of them.

---

## 5. Entity Type Migration Impact on Contract

The current `Contract.entity_type` field (`personal | business`) will be superseded when the Entity migration sprint runs.

**Post-migration target:**

```python
entity = ForeignKey("bonup.Entity", null=True, blank=True, ...)
```

Where `Entity` resolves to either a `soul_entity` or a `business_entity` subtype.

**Before migration:**
- `Contract.entity_type = "personal"` continues to mean personal operating surface.
- `Contract.entity_type = "business"` + `Contract.entity (FK to BusinessEntity)` continues to mean business operating surface.
- These fields must not be removed or changed until the Entity migration sprint.

**After migration:**
- `Contract.entity` FK points to `Entity` (supertype).
- `Contract.entity_type` is retired.
- The distinction between personal and business surfaces is encoded in the `Entity` subtype.

---

## 6. Named Implementation Gaps Created by This Spec

These gaps are named here for future sprint planning. None are to be worked in the Soul introduction sprint.

| Gap ID | Description | Depends On |
|---|---|---|
| AG1 | Introduce `Soul` model in new bonUP-layer app | This spec |
| AG2 | Introduce `Entity` supertype; migrate `BusinessEntity` as subtype | AG1 complete |
| AG3 | Migrate `Contract.entity_type` flat field to `Contract.entity` FK pointing to `Entity` | AG2 complete |
| AG4 | Introduce `AuthorityHolder` relation model | AG2 complete |
| AG5 | Migrate `BusinessEntity.owner` → `AuthorityHolder` record | AG4 complete |
| AG6 | Migrate Contract Pro grant anchor from `BusinessEntity` to `Entity` | AG2, AG4 complete |
| AG7 | Generalize `ContractProAccessGrant` as `AppointedAuthority` subtype or migrate it to anchor to `AuthorityHolder` + `Entity` | AG4, AG5, AG6 complete |
| AG8 | Introduce `soul_entity` as the personal operating surface record | AG2 complete |
| AG9 | Introduce `Operator` role model under `AuthorityHolder` / `AppointedAuthority` | AG4, AG7 complete |

---

## 7. Safe Build Sequence

```
Step 0 (this document)
  Spec pass complete. Five questions answered. Build sequence locked.

Step 1 — Soul model introduction (AG1)
  - Create new Django app: bonup/ (or identity/)
  - Add Soul model: one-to-one FK to AUTH_USER_MODEL
  - Migration only — no changes to existing models
  - No FKs back from Contract, ContractPro, or BusinessEntity yet
  - Tests: verify Soul can be created for an existing User; verify one-to-one constraint
  - Outcome: bonUP-layer identity anchor exists; nothing in Blackboard changes

Step 2 — Entity supertype (AG2, AG8)
  - Introduce Entity model with discriminated subtype field
  - Wire BusinessEntity as a business_entity subtype
  - Introduce soul_entity record for personal operating surface
  - Migration: BusinessEntity gains a back-link to Entity; no FK changes yet
  - Tests: verify entity subtype creation; verify BusinessEntity↔Entity link
  - Outcome: Entity layer exists; Contract Pro and Blackboard continue using BusinessEntity FK unmodified

Step 3 — AuthorityHolder model introduction (AG4)
  - Introduce AuthorityHolder model: Soul FK + Entity FK
  - Additive only — does not touch BusinessEntity.owner yet
  - Migration creates the new table; no existing FKs changed
  - Tests: verify AuthorityHolder record can be created for a Soul + Entity pair
  - Outcome: AuthorityHolder relation exists in code; nothing in Blackboard is affected

Step 4 — BusinessEntity.owner migration (AG5)  ← highest-risk step
  - Migrate BusinessEntity.owner to be derived from / replaced by AuthorityHolder record
  - Update Contract Pro grant.business.owner derivation to use AuthorityHolder
  - Full Contract Pro permission regression test run required before merge
  - Tests: verify Contract Pro grant derivation still resolves correctly after migration
  - Outcome: BusinessEntity.owner is migrated; Contract Pro permission root is now AuthorityHolder

Step 5 — Contract Pro anchor migration (AG6)
  - Migrate ContractProAccessGrant.business FK to Entity FK
  - Tests: verify existing Contract Pro grants resolve correctly through Entity→BusinessEntity
  - Outcome: Contract Pro is no longer hard-wired to BusinessEntity; it uses Entity

Step 6 — AppointedAuthority generalization (AG7)
  - Decide: migrate ContractProAccessGrant to AppointedAuthorityGrant subtype, or add abstract base
  - Tests: verify grant lifecycle still works
  - Outcome: AppointedAuthority concept exists in code; future authority types can use the same base

Step 7 — Operator (AG9)
  - Deferred. Not started until Step 6 is stable.

Step 8 — Contract entity_type migration (AG3)
  - Migrate Contract.entity_type flat field to FK on Entity
  - Tests: verify existing contracts resolve entity correctly
  - Outcome: entity_type flat field is retired
```

Steps 1 through 8 are ordered by dependency. No step may begin until its predecessor is complete and verified. Step 4 is the highest-risk step because it migrates a live permission root.

---

## 8. Explicitly Deferred Beyond This Spec

The following are out of scope for this spec and for the Soul introduction sprint. They are listed here to prevent scope creep.

| Item | Deferred to |
|---|---|
| `Operator` model implementation | Step 6 / after AppointedAuthority stable |
| Trust as a first-class entity type with its own workflows | Deferred indefinitely — Trust is `business_entity` with `legal_form=Trust` |
| Multi-owner `AuthorityHolder` (two people jointly holding authority for one entity) | Post-phase-one |
| Soul existence without a User (unnamed counterparty, pre-registration person record) | Counterparty identity gap sprint (A5 Gap 1/2) |
| Permission surface changes for the personal operating surface | Post-Entity migration |
| UI / surface changes | Post-backend model stability |
| Billing integration for entity-level subscriptions | Separate billing sprint |
| AppointedAuthority for personal operating surface (personal-level delegation) | Not planned; deferred |
| Cross-entity authority grants (one Soul holding AuthorityHolder across multiple Entity types simultaneously) | Post-phase-one |
| Entity-held authority (one Entity holding an AuthorityHolder relation over another Entity, without a Soul as the direct holder) | Post-phase-one — not defined and not safe to assume in this spec |
| Counterparty identity FK gaps (`Contract.counterparty_user`, `ContractVersion.signed_by`) | Counterparty identity gap sprint (A5 Gap 1/2) |

---

## 9. Summary

The authority/governance model for bonUP is relational, not a strict tree.
`AuthorityHolder` and `AppointedAuthority` are relations (link records), not ownership nodes.

```
Core concepts
─────────────────────────────────────────────────────────
User            system account / bonID / auth credential
Soul            natural human actor  (Soul.user → User)
Entity          operating/legal actor
  soul_entity   — personal surface; one per Soul
  business_entity — formal business (currently: BusinessEntity)

Relations
─────────────────────────────────────────────────────────
AuthorityHolder
  .soul   ──→  Soul     (who holds primary authority)
  .entity ──→  Entity   (over which entity)
  reads: "this Soul holds primary authority for this Entity"

AppointedAuthority  (currently: ContractProAccessGrant)
  .granted_by  ──→  AuthorityHolder   (who appointed this role)
  .grantee     ──→  Soul              (who is appointed)
  .entity      ──→  Entity            (scoped to which entity)
  reads: "this AuthorityHolder has appointed this Soul to act for this Entity"

Operator  (deferred — not implemented)
  sits under AuthorityHolder or AppointedAuthority
```

Personal surface note: on the personal surface a `Soul` acts with implicit self-authority over their own `soul_entity`. No `AuthorityHolder` record is created for this case in phase one.

Current live implementation anchors:

| Concept | Current code anchor | Target anchor | Sprint |
|---|---|---|---|
| Business entity | `BusinessEntity` | `business_entity` subtype of `Entity` | AG2 |
| Entity authority root | `BusinessEntity.owner` (FK to User) | `AuthorityHolder.soul` (FK to Soul) | AG4/AG5 |
| Contract Pro grant anchor | `ContractProAccessGrant.business` (FK to BusinessEntity) | `ContractProAccessGrant.entity` (FK to Entity) | AG6 |
| Contract party context | `Contract.entity_type = "personal" | "business"` | `Contract.entity` FK to `Entity` | AG3 |
| Natural human actor | implied by `User` | `Soul` model | AG1 |

Nothing changes in code until the Soul introduction sprint (AG1) begins, and that sprint touches only the new app.
