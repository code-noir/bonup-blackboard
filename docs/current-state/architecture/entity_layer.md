# Entity Layer Architecture

> Status: Current
> Source of truth: code first, this document second
> Updated: 2026-05-06

---

## 1. Purpose

The entity layer defines how a natural person or business becomes an operating actor inside bonUP.

It separates:
- natural human identity (`Soul`)
- system-level entity representation (`Entity`)
- personal operating surface (`SoulEntity`)
- business operating surface (`BusinessEntity`)

This layer is the foundation for future authority, contracts, delegation, and business-scoped system behavior.

---

## 2. Current Code Truth

Models are split across two apps.

### `backend/bonup/models.py`
- `Soul`
- `Entity`
- `SoulEntity`

### `backend/users/models.py`
- `BusinessEntity`

Key structure:
- `Soul` holds a `OneToOneField` to Django auth `User`.
- `BonUserProfile` also points to `User` and remains a separate concern for bonID and verification.
- `Soul` and `BonUserProfile` coexist.
- `Entity` is the core system-level representation with an `entity_type` discriminator.
- `SoulEntity` links `Soul` to an `Entity`. The model docstring states `entity_type` must equal `"soul_entity"`, but this is not enforced at the database level or in a `save()` override.
- `BusinessEntity` is primarily anchored by `owner` (`User` FK).
- `BusinessEntity` also carries a nullable `Entity` pointer as the bonUP entity-layer connection.

---

## 3. Core Concepts

### Soul

`Soul` represents the natural human actor.

It does not replace `User` or `BonUserProfile`.

### Entity

`Entity` is the system-level actor abstraction.

It supports entity typing for personal and business operating surfaces.

### SoulEntity

`SoulEntity` is the personal operating surface.

It holds:
- `entity → Entity`
- `soul → Soul`

There is one `SoulEntity` per `Soul`.

### BusinessEntity

`BusinessEntity` is the business operating surface.

Its primary anchor is:
- `owner → User`

It also carries:
- nullable `entity → Entity`

The nullable `Entity` pointer was added as the AG2b bridge into the bonUP entity layer.

---

## 4. Current Behavior

- Each `Soul` is linked to a Django auth `User`.
- `Soul` is distinct from `BonUserProfile`.
- `Entity` acts as the shared abstraction for personal and business operating surfaces.
- `SoulEntity` represents a `Soul` acting through a personal operating surface.
- `BusinessEntity` represents a business actor owned by a user.
- `BusinessEntity.entity` is nullable.
- Existing `BusinessEntity` rows were backfilled to link to `Entity` through migration `0010`.
- `BusinessEntity.save()` creates the corresponding `Entity` row whenever `entity_id` is falsy — not only on first save. This means the guard also fires if a `SET_NULL` cascade (e.g. from a deleted `Entity`) has nulled the pointer on a subsequent save.
- Losing the `Entity` pointer does not destroy the `BusinessEntity`.

---

## 5. Authority / Access Rules

- Full entity-layer authority is not implemented yet.
- `AuthorityHolder` is not implemented.
- `AppointedAuthority` is not implemented.
- `BusinessEntity.owner` remains the live business authority root.
- `Entity` is the future anchor for broader authority relationships.
- Business entity creation is gated through billing constraints.

---

## 6. Relationship to Other Domains

### `identity.md`

Identity provides the user, bonID, verification, and profile layer that `Soul` builds above.

### `authority.md`

Authority will eventually use `Entity` and `AuthorityHolder` to define who can act for a personal or business operating surface.

### `contract_pro.md`

Contract Pro currently works through business-level authority and `BusinessEntity`.

Future Contract Pro authority migration depends on the entity/authority foundation.

### `contract_lifecycle.md`

Contracts currently distinguish personal and business context through existing contract fields.

Future contract entity migration is deferred.

---

## 7. Current Gaps / Deferred Work

- `AuthorityHolder` model is not implemented.
- `AppointedAuthority` model is not implemented.
- Contract Pro still anchors to `BusinessEntity`, not generalized `Entity`.
- Contract entity migration from flat personal/business context to `Entity` is deferred.
- Personal and business authority are not fully unified under the entity layer yet.

---

## 8. Update Rule

Update this file when:
- `Soul`, `Entity`, `SoulEntity`, or `BusinessEntity` changes
- entity migration steps are added or completed
- authority relationships are introduced
- business ownership or entity linkage behavior changes
- contract or Contract Pro anchoring changes