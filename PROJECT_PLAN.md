# PROJECT_PLAN.md — bonUP Blackboard

---

## bonUP — The Ecosystem

bonUP is a platform for creating, tracking, and proving value between parties.

Its core concept is the **PBVD** — Proof Based Value Document. A PBVD is any document that proves something exists, occurred, or was agreed to. A contract is one type of PBVD. An invoice is another. A proof of delivery, a signed statement, a completed service record — all PBVDs.

bonUP does not belong to any single domain. It is a general infrastructure for obligation-based relationships. Multiple verticals live inside it, each addressing a different category of value exchange.

---

## The Lifecycle Engine

At the core of bonUP is a **generic Lifecycle Engine** — a pure Python domain layer that knows nothing about contracts, payments, or any specific vertical.

The engine owns:
- Obligation primitives (`PaymentObligation`, `ServiceObligation`)
- State evaluation (`active → overdue → defaulted → breached → resolved`)
- Scheduling (installment generation, recurrence)
- Lifecycle processing (`process_obligation_lifecycle`)
- Execution session and event primitives (proof capture)
- Value adjustment logic (lateness penalties, additional charges)

The engine has no Django dependency. It has no database. It holds no state. It receives facts, evaluates them against rules, and returns results. Any bonUP vertical can plug into it.

This repo's engine lives in `backend/engine/`.

---

## Blackboard — The Contract Vertical

**Blackboard** is the contract vertical inside bonUP. It is the only vertical implemented in this repository.

Blackboard uses the Lifecycle Engine to power a full contract management backend:

- Contract creation, versioning, and signing
- Obligation scheduling against signed contracts (payment + service installments)
- Lifecycle state tracking per obligation and per contract
- Payment recording and obligation balance sync
- Execution sessions and events (capturing proof of service delivery)
- Value adjustments and approval workflows
- Promotion of execution events into new side obligations

A contract in Blackboard is a specific type of PBVD: a bilateral agreement between two parties that generates obligations. The obligations are what the engine tracks.

---

## Architecture

Three layers. They must not mix.

**Engine** (`backend/engine/`) — pure Python, no Django, no ORM. All domain logic lives here. Verticals consume this layer, they do not extend it for their own persistence needs.

**Persistence + API** (`backend/contracts/`, `backend/payments/`, `backend/api/`) — Django ORM models and REST endpoints. Stores state. Exposes it. Delegates all business logic to the engine.

**Infrastructure** (`backend/infrastructure/repositories/`) — bridges the two. Concrete repository implementations that satisfy the engine's abstract interfaces.

---

## The 15 Domains

The API router exposes 15 domain namespaces. Their current state:

| # | Domain | Path | Status |
|---|--------|------|--------|
| 1 | **auth** | `/api/auth/` | Working — JWT token issue/refresh/verify |
| 2 | **contracts** | `/api/contracts/` | Working — CRUD, versioning, obligations, execution, approvals |
| 3 | **obligations** | `/api/obligations/` | Working — full CRUD + lifecycle operations |
| 4 | **payments** | `/api/payments/` | Working — CRUD + status transitions + summaries |
| 5 | **users** | `/api/users/` | Stub — no real implementation |
| 6 | **workspace** | `/api/workspace/` | Stub — no real implementation |
| 7 | **activity** | `/api/activity/` | Stub — no real implementation |
| 8 | **billing** | `/api/billing/` | Stub — no real implementation |
| 9 | **documents** | `/api/documents/` | Stub — no real implementation |
| 10 | **notifications** | `/api/notifications/` | Stub — no real implementation |
| 11 | **search** | `/api/search/` | Stub — no real implementation |
| 12 | **sessions** | `/api/sessions/` | Stub — no real implementation |
| 13 | **templates** | `/api/templates/` | Stub — no real implementation |
| 14 | **tools** | `/api/tools/` | Stub — no real implementation |
| 15 | **uploads** | `/api/uploads/` | Stub — no real implementation |

---

## Version 1 vs Version 2

### Version 1 — Obligation Engine (current)

The goal of V1 is a working, reliable backend for the core Blackboard contract lifecycle.

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

### Version 2 — Platform

V2 connects the engine to a real product surface and extends Blackboard toward the broader bonUP ecosystem.

- Real payment gateway (Stripe or equivalent)
- Push/email notification delivery
- Document attachments and PBVD uploads
- Template-based contract generation
- User workspace with team and role management
- Full-text search across contracts and obligations
- Activity feed and audit logging
- Mobile API compatibility
- bonID-based identity across all entities
- Groundwork for additional bonUP verticals beyond Blackboard

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
IDs are assigned sequentially. Numbers composed entirely of 0s and 1s are reserved (binary-only, e.g. `0000000000001`, `0000000000010`) and stored in `ReservedBonId`.

The bonID is a cross-vertical identity — it belongs to the bonUP ecosystem, not to Blackboard specifically.

---

## PBVD

A **Proof Based Value Document** is any document that proves something exists, occurred, or was agreed to.

Examples:
- A signed contract (Blackboard's domain)
- A completed service record
- A proof of delivery
- An invoice
- A payment receipt

In Blackboard, execution events captured during service obligation sessions form PBVD records — evidence that a service obligation was fulfilled, traceable back to the specific work performed, not just a signature on an agreement.

Events can be promoted into side obligations (`ContractObligationPromotion`) when work discovered during execution falls outside the original scope of the contract.
