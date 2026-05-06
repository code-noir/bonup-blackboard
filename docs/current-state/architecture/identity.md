# Identity Architecture

> Status: Current
> Source of truth: code first, this document second
> Updated: 2026-05-06

---

## 1. Purpose

The identity layer defines how users are created, verified, authenticated, and identified in the system.

It manages:
- user accounts (Django User)
- bonID identity system
- email verification
- signup and invitation flows
- authentication and session entry

This layer produces the base `User` record that the entity layer builds on top of.

---

## 2. Current Code Truth

Core identity models live in:

### `backend/users/models.py`

- `PendingSignup`
- `BonUserProfile`
- `AssignedBonId`
- `ReservedBonId`
- `UserBillingInfo`
- `UserInvitation`

Key structure:

- `User` (Django auth) is the base identity record.
- `BonUserProfile` is a `OneToOneField` to `User` and holds:
  - bonID (assigned once, immutable)
  - email verification state
  - contact and profile fields
- `AssignedBonId` is the permanent ledger of all issued bonIDs.
- `ReservedBonId` stores disallowed IDs (binary-only strings).
- `PendingSignup` is a temporary pre-user staging model.
- `UserInvitation` creates users directly (bypasses staging).
- `UserBillingInfo` stores billing address only.

---

## 3. Core Concepts

### User

Django auth user is the root identity record.

All authentication is anchored to this model.

---

### BonUserProfile

Holds:
- bonID (external identity)
- email verification state
- profile data

bonID is assigned once during creation and never changed.

---

### PendingSignup

Temporary record used during two-stage signup.

User does not exist until verification completes.

---

### AssignedBonId

Permanent, append-only ledger of issued bonIDs.

Used as the source of sequence truth.

---

### ReservedBonId

Stores IDs that must never be assigned (binary-only patterns).

---

### UserInvitation

Invitation-based onboarding:
- bypasses PendingSignup
- creates User directly
- email is pre-verified

---

### UserBillingInfo

Stores billing address only.

Not part of authentication or identity logic.

---

## 4. Current Behavior

### Signup (two-stage flow)

1. `/api/users/register/`
   - creates `PendingSignup`
   - sends verification email

2. `/api/users/verify-pending/`
   - creates `User`
   - creates `BonUserProfile`
   - assigns bonID
   - sets `email_verified = True`
   - deletes `PendingSignup`

---

### Invitation Flow

- User created directly (no PendingSignup)
- Email is automatically verified

---

### Email Verification

Two separate flows:

1. **Initial signup**
   - uses `PendingSignup.token`

2. **Email change**
   - uses `BonUserProfile.email_verification_token`

---

### Authentication

Two login endpoints exist:

- `/api/auth/token/`
  - accepts email or username
  - enforces `email_verified = True`

- `/api/users/login/`
  - default SimpleJWT
  - does NOT enforce verification

---

### Password Reset

- always returns 200 (no user enumeration)
- uses uid/token flow

---

## 5. Authority / Access Rules

- Authentication via `/api/auth/token/` requires `email_verified = True` (with an exception for admin users without a `BonUserProfile`). The parallel `/api/users/login/` endpoint uses unmodified SimpleJWT and does NOT enforce this gate — see section 7.
- No bonID-level permissions exist yet
- No role-based identity permissions implemented
- Identity layer does not manage business or contract authority

---

## 6. Relationship to Other Domains

### entity_layer.md

- Identity creates the `User`
- Entity layer builds on top of it:
  - `Soul` ← User
  - `SoulEntity` ← Soul + Entity
  - `BusinessEntity` ← owned by User

Identity does NOT define:
- Soul
- Entity
- authority

It only produces the base user.

---

## 7. Current Gaps / Deferred Work

- Duplicate login endpoints create verification bypass risk
- `Soul` is not auto-created on user creation
- `SoulEntity` is not auto-created
- Identity and entity layers are not fully wired
- Two separate verification token systems (signup vs email change)
- Invitation path bypasses staging flow

---

## 8. Update Rule

Update this file when:
- identity models change
- signup or login flows change
- bonID assignment logic changes
- verification rules change
- authentication endpoints change