# CLAUDE.md — Instructions for Claude Code

This file is the authoritative guide for how Claude Code should work in this repository.
Read it before making any changes.

---

## Project Identity

- **Repo**: `bonup-blackboard`
- **Product**: bonUP Blackboard — a contract lifecycle management backend
- **Stack**: Django 6.0.2, Django REST Framework 3.16.1, PostgreSQL, Python 3.12
- **Branch convention**: feature work happens off `main`; current working branch is `restore-before-break`

---

## How to Run Tests

```bash
source venv/bin/activate
python -m pytest backend/ -v --ds=backend.core.settings
```

All tests must pass before committing. The test suite currently has 11 tests — all green.
There are no API-layer tests yet; all existing tests cover the engine layer.

---

## Project Structure

```
backend/
├── engine/                        Pure Python — no Django ORM
│   ├── lifecycle_core/            Primitives: PaymentObligation, ServiceObligation, evaluator
│   ├── contracts/                 Contract domain services, scheduler, coordinator
│   ├── automation/                Lifecycle automation runner and factory
│   └── payments/                  PaymentGateway interface, PaymentService, MockPaymentGateway
├── contracts/                     Django ORM models for contracts domain
├── payments/                      Django ORM models for payments domain
├── users/                         BonUserProfile, ReservedBonId models
├── infrastructure/
│   └── repositories/              Concrete repository implementations
├── api/
│   ├── router.py                  Wires all 15 domain URLs
│   ├── auth/                      JWT token endpoints (simplejwt)
│   ├── contracts/                 ContractViewSet + contract-scoped obligation/execution endpoints
│   ├── obligations/               Obligation-scoped endpoints (1429 lines of views)
│   └── payments/                  Payment CRUD + status transition + summary endpoints
└── core/
    ├── settings.py                Django settings
    └── urls.py                    Root URL configuration
```

### Layering Rules

The engine layer (`backend/engine/`) must never import from Django ORM models.
The API layer imports from both engine and ORM models.
The infrastructure layer bridges the two via repositories.

---

## Coding Conventions

- **Datetime**: always use `timezone.now()` from `django.utils`. Never use `datetime.utcnow()`.
- **Decimal**: always coerce with `Decimal(str(value))`, never `Decimal(float)`.
- **Transactions**: wrap all multi-save API operations in `transaction.atomic()`.
- **Error handling**: use `get_object_or_404` or explicit `try/except DoesNotExist` in all views. No naked `.objects.get()`.
- **State transitions**: always validate current state before allowing a transition.
- **Repository pattern**: engine services receive repository instances via dependency injection. Never instantiate repos inside engine code.

---

## What Not to Touch

| File / Component | Reason |
|------------------|--------|
| `lifecycle_core/obligations/primitives.py` | Stable. PaymentObligation and ServiceObligation are the canonical primitives. |
| `lifecycle_core/state/evaluator.py` | Single source of truth for obligation state. Change carefully. |
| `contracts/obligations/lifecycle.py` | `process_obligation_lifecycle()` is the authoritative lifecycle processor. |
| `lifecycle_core/scheduler/obligation_scheduler.py` | Safe scheduler. The only scheduler to use. |
| `contracts/domain/contract.py` | Core aggregate. Changes break many things downstream. |
| `contracts/models.py` (ContractVersion) | Immutable — its `save()` enforces this at the ORM level. |

### Dead / Deprecated Files

Do not use or extend:
- `lifecycle_core/instances/obligation_instance.py` — superseded by `primitives.py`
- `contracts/obligations/entity.py`, `evaluator.py`, `recurrence.py` — empty placeholders
- `contracts/services/import_service.py` — empty placeholder

---

## Authentication

All endpoints require JWT authentication. Tokens are issued at `/api/auth/token/`.

`DEFAULT_AUTHENTICATION_CLASSES` and `DEFAULT_PERMISSION_CLASSES` are set globally in `settings.py`.
Do not override them per-view unless there is a specific reason.

---

## Open Issues

See `AUDIT.md` for the full bug registry (BUG-1 through BUG-16).
See `DONE_AND_NOT_DONE.md` for feature completion status.
See `API_LEDGER.md` for endpoint inventory.
