# PROJECT_PLAN.md — bonUP Blackboard

---

## What Is bonUP

bonUP is a platform for managing contractual relationships between service providers and clients.
Its core premise: every agreement between two parties creates obligations — payment obligations and service obligations — and those obligations have lifecycle states that change over time.

bonUP tracks this in real time. It is not a document manager or an e-signature tool. It is an obligation engine.

---

## What Is Blackboard

Blackboard is the backend system that powers bonUP. It is a Django REST API that implements:

- Contract creation, versioning, and signing
- Obligation scheduling (installment-based, recurrence-based)
- Lifecycle state evaluation (ACTIVE → OVERDUE → DEFAULTED → BREACHED → RESOLVED)
- Payment tracking and obligation balance sync
- Execution session and event capture (proof of work)
- Value adjustments (lateness penalties, additional charges)
- Approval workflows for execution items
- Promotion of execution events into side obligations

---

## Architecture Principle

The codebase is split into two layers that must never mix:

**Engine layer** (`backend/engine/`) — pure Python, no Django, no ORM.
This layer owns all domain logic: state evaluation, obligation primitives, scheduling, lifecycle processing.

**Persistence + API layer** (`backend/contracts/`, `backend/payments/`, `backend/api/`) — Django ORM models and REST endpoints.
This layer stores state and exposes it. It delegates all business logic to the engine.

Bridging the two is the **infrastructure layer** (`backend/infrastructure/repositories/`), which implements the repository interfaces the engine uses.

---

## The 15 Domains

The API router exposes 15 domain namespaces. Their current state:

| # | Domain | Path | Status |
|---|--------|------|--------|
| 1 | **auth** | `/api/auth/` | Working — JWT token issue/refresh/verify |
| 2 | **contracts** | `/api/contracts/` | Working — CRUD, versioning, obligations, execution, approvals |
| 3 | **obligations** | `/api/obligations/` | Working — full CRUD + lifecycle operations |
| 4 | **payments** | `/api/payments/` | Working — CRUD + status transitions + summaries |
| 5 | **users** | `/api/users/` | Stub ViewSet — no real implementation |
| 6 | **workspace** | `/api/workspace/` | Stub ViewSet — no real implementation |
| 7 | **activity** | `/api/activity/` | Stub ViewSet — no real implementation |
| 8 | **billing** | `/api/billing/` | Stub ViewSet — no real implementation |
| 9 | **documents** | `/api/documents/` | Stub ViewSet — no real implementation |
| 10 | **notifications** | `/api/notifications/` | Stub ViewSet — no real implementation |
| 11 | **search** | `/api/search/` | Stub ViewSet — no real implementation |
| 12 | **sessions** | `/api/sessions/` | Stub ViewSet — no real implementation |
| 13 | **templates** | `/api/templates/` | Stub ViewSet — no real implementation |
| 14 | **tools** | `/api/tools/` | Stub ViewSet — no real implementation |
| 15 | **uploads** | `/api/uploads/` | Stub ViewSet — no real implementation |

---

## Version 1 vs Version 2

### Version 1 — Obligation Engine (current)

The goal of V1 is a working, reliable backend for the core contract lifecycle.

**In scope:**
- Contract creation and signing workflow
- Obligation scheduling (payment + service)
- Lifecycle state machine (active → overdue → defaulted → breached → resolved)
- Payment tracking with obligation balance sync
- Execution sessions and events (proof of work capture)
- Value adjustments and approval requests
- JWT authentication on all endpoints
- All engine bugs fixed and all tests passing

**Out of scope for V1:**
- Real payment gateway integration (mock only)
- Notification delivery
- Document management
- Search
- User workspace / multi-tenancy
- Template system
- External integrations

### Version 2 — Platform (planned)

V2 connects the engine to a real product surface:

- Real payment gateway (Stripe or equivalent)
- Push/email notification delivery
- Document attachments and proof uploads
- Template-based contract generation
- User workspace with team management
- Full-text search across contracts and obligations
- Activity feed and audit logging
- Mobile API compatibility
- bonID-based identity system across all entities

---

## Obligation Lifecycle States

```
ACTIVE → OVERDUE (past due date) → DEFAULTED (30+ days overdue) → BREACHED
                                                                     ↑
                                                              (escalation path)
ACTIVE → RESOLVED (fully paid / service completed)
OVERDUE → RESOLVED (late but completed)
DEFAULTED → RESOLVED (late but eventually completed)
```

The state transition engine lives in `backend/engine/lifecycle_core/state/evaluator.py`.
The single function `evaluate_obligation_state()` is the authoritative source of truth.

---

## bonID System

Each bonUP user has a 13-digit bonID (`BonUserProfile.bon_id`).
IDs are assigned sequentially. Numbers that are composed entirely of 0s and 1s are reserved (binary-only, e.g. `0000000000001`, `0000000000010`) and stored in `ReservedBonId`.

---

## Proof of Work (PBVD)

Execution events captured during service obligation sessions form a proof of work record.
This underpins bonUP's "Proof By Value Delivered" (PBVD) concept: the execution record is the evidence that a service obligation was fulfilled, not just a signature.

Events can be promoted into side obligations (via `ContractObligationPromotion`) when discovered work falls outside the original scope.
