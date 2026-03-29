# Codebase Audit — March 2026

**Date**: 2026-03-29
**Scope**: Full backend — lifecycle engine, obligation domain, payment domain
**Branch**: `restore-before-break`

---

## Executive Summary

The architecture is well-conceived: layered, domain-driven, with a pure engine separated from persistence. The core obligation primitives and state evaluator are solid. But the implementation is incomplete in several places and has critical bugs that will cause crashes or silent data corruption. The services layer calls repository methods that don't exist in the interface. The escalation/defaulted path is structurally unreachable. The payment API never syncs to obligation balances. No endpoint has authentication.

**Status**: Core primitives functional. Services layer blocked by interface gaps. API layer open and partially broken.

---

## Directory Map

```
backend/
├── engine/
│   ├── automation/              execute.py, factory.py, runner.py, tasks.py
│   ├── contracts/
│   │   ├── domain/              contract.py  ← Contract aggregate
│   │   ├── obligations/         lifecycle.py, payments.py, account.py
│   │   │                        entity.py, evaluator.py, recurrence.py  ← ALL EMPTY
│   │   ├── services/            10 service files (see below)
│   │   ├── tests/
│   │   ├── state_machine.py, versioning.py, lifecycle.py
│   │   └── change_request.py   ← 4-line stub
│   ├── lifecycle_core/
│   │   ├── obligations/         primitives.py  ← PaymentObligation, ServiceObligation
│   │   ├── scheduler/           obligation_scheduler.py (safe), scheduler.py (crashes)
│   │   ├── state/               evaluator.py, escalation.py, constants.py
│   │   ├── execution/           primitives.py, evaluator.py, adjustments.py
│   │   ├── instances/           obligation_instance.py
│   │   └── lifecycle_manager.py
│   └── payments/                gateway.py, mock_gateway.py, payment_service.py
├── api/
│   ├── obligations/             views.py (1429 lines), serializers.py, urls.py
│   └── payments/                views.py, serializers.py, urls.py
├── contracts/                   models.py  ← Django ORM models
└── payments/                    models.py  ← Django ORM models
```

---

## Part 1: Lifecycle Engine

### 1.1 What's Solid

| Component | File | Notes |
|-----------|------|-------|
| `PaymentObligation` | `lifecycle_core/obligations/primitives.py` | Sound Decimal logic, correct overpayment cap |
| `ServiceObligation` | `lifecycle_core/obligations/primitives.py` | Lateness adjustment logic well-implemented |
| `evaluate_obligation_state()` | `lifecycle_core/state/evaluator.py` | Pure function, correct for the 3 states it handles |
| `ObligationScheduler` | `lifecycle_core/scheduler/obligation_scheduler.py` | Clean schedule generation, no crash bugs |
| `process_obligation_lifecycle()` | `contracts/obligations/lifecycle.py` | Has `@transaction.atomic`, follows right pattern |
| `Contract` aggregate | `contracts/domain/contract.py` | Pattern is sound |
| `contracts/state_machine.py` | — | Clean, explicit transition graph |
| `contracts/versioning.py` | — | Version number logic correct |
| `automation/` runner/factory | — | Clean patterns for scheduling |
| `payments/gateway.py` | — | Abstract interface well-defined |

### 1.2 Critical Bugs

#### BUG-1: `grace_days` constructor crash
**File**: `lifecycle_core/scheduler/scheduler.py:52,65`
`generate_obligation_schedule()` passes `grace_days=payment_grace` and `grace_days=service_grace` to `PaymentObligation` and `ServiceObligation` constructors — neither accepts that parameter.
**Effect**: `TypeError` crash on every obligation schedule generation.
**Fix**: Delete `scheduler.py` in favour of `obligation_scheduler.py`, or add `grace_days` to the primitive constructors and implement the logic.

#### BUG-2: `obligation.deadline()` doesn't exist
**File**: `lifecycle_core/state/escalation.py:26,29`
Calls `obligation.deadline()` but `PaymentObligation` has no such method.
**Effect**: `AttributeError` crash if escalation is ever reached.
**Fix**: Replace `obligation.deadline()` with `obligation.due_date`.

#### BUG-3: Escalation path is structurally unreachable
**File**: `lifecycle_core/state/escalation.py:23`
`evaluate_default_escalation()` is guarded by `if obligation.state != "defaulted": return`. But `evaluate_obligation_state()` only ever returns `ACTIVE`, `OVERDUE`, or `RESOLVED` — it never produces `"defaulted"`.
**Effect**: Escalation logic is dead code. No obligation will ever be escalated to `"breached"`.

#### BUG-4: Contract state can never reach "breached"
**File**: `contracts/domain/contract.py:80`
`_refresh_contract_state()` checks `if "breached" in states or "defaulted" in states` to mark the contract breached. Since neither state is ever produced (see BUG-3), contracts can never reach `"breached"`.
**Effect**: `reconstruction_service.py`'s rejection guard for breached contracts never fires. The full escalation arc (OVERDUE → DEFAULTED → BREACHED) is non-functional.

#### BUG-5: Five repository methods called but not defined in the interface
**File**: `contracts/interfaces.py`
The interface defines only: `get_latest()`, `count()`, `save()`. The service layer calls five additional methods that are absent:

| Method | Called In | Line |
|--------|-----------|------|
| `get_signed_version(contract)` | `contract_version_service.py` | 117 |
| `get_signed_version(contract)` | `contract_projection_service.py` | 67 |
| `list_candidates(contract_id, limit)` | `lifecycle_runner_services.py` | 66 |
| `update_state(obligation, state, time)` | `payment_service.py` | 56 |
| `update_state(obligation, state, time)` | `lifecycle_runner_services.py` | 88 |
| `get_all()` | `lifecycle_runner_services.py` | 31 |

**Effect**: `AttributeError` crash in any service path that touches version signing, lifecycle running, or payment processing.

#### BUG-6: `contract.apply_payment()` not defined
**File**: `engine/payments/payment_service.py`
`PaymentService.process_payment()` calls `contract.apply_payment(obligation, amount)` on the `Contract` domain object. That method does not exist on `Contract`.
**Effect**: `AttributeError` crash in `PaymentService`.

#### BUG-7: `Contract.refresh()` signature mismatch
**File**: `contracts/domain/contract.py`
`refresh(self, now, obligation_repo)` requires two positional arguments. Tests call it as `contract.refresh()` with no arguments.
**Effect**: Tests fail; calling convention is inconsistent across the codebase.

### 1.3 Design Issues

**Duplicate schedulers**
Two scheduler implementations exist side by side:
- `lifecycle_core/scheduler/scheduler.py` — crashes (BUG-1)
- `lifecycle_core/scheduler/obligation_scheduler.py` — safe

Only the second should be used. The first should be fixed or deleted.

**Parallel obligation class hierarchies**
Two unrelated obligation class systems exist:
- `lifecycle_core/obligations/primitives.py` — `PaymentObligation`, `ServiceObligation` (used in main code)
- `lifecycle_core/instances/obligation_instance.py` — `ObligationInstance` (different state constants: `COMPLETED` vs `RESOLVED`)

It is unclear which is canonical. Both are in use in different parts of the codebase.

**Timezone inconsistency**
`contracts/obligations/account.py:27` uses `datetime.utcnow()` (naive). The rest of the codebase uses `timezone.now()` (aware). This causes incorrect overdue comparisons in `PaymentObligation.is_past_due()`.

**MockPaymentGateway doesn't implement its interface**
`engine/payments/mock_gateway.py` does not inherit from `PaymentGateway`, returns a plain dict instead of `PaymentResult`, and ignores the `currency` and `metadata` parameters.

**Empty placeholder files**
The following files contain no code and serve no current purpose:
- `contracts/entities.py`
- `contracts/obligations/entity.py`
- `contracts/obligations/evaluator.py`
- `contracts/obligations/recurrence.py`
- `contracts/services/import_service.py`

**Malformed test file**
`contracts/tests/--init--.py` uses dashes in the filename. Python will not recognise it as a package init file.

---

## Part 2: Obligation Domain

### 2.1 Models

**`ContractObligation`** (payment instance)
Clean model. `amount_due`, `amount_paid` as Decimal, `installment_number`, `due_date`, `state`, `is_defaulted` flag. Ordered by `due_date`.

Issues:
- State choices include `"due"` and `"grace"` which the engine never produces.
- `is_defaulted` boolean duplicates the `"defaulted"` state field.
- No DB-level constraint that `amount_paid <= amount_due`.
- No methods — purely a data bag.

**`ContractServiceObligation`** (service instance)
Similar to above. Has `completed_at` field and a `mark_completed()` method, but the lateness adjustment feature from `ServiceObligation` primitive has no corresponding tracking here.

**`Obligation`** (template/definition model)
Has `recurrence_interval_days` and `recurrence_count` fields. No recurrence service is implemented. This model is effectively unused.

**Execution infrastructure**
`ObligationExecutionSession`, `ObligationExecutionEvent`, `ContractValueAdjustment`, `ContractApprovalRequest` all exist in models but are orphaned from the core lifecycle. They store data but no logic enforces or uses them.

### 2.2 API Layer

**File**: `api/obligations/views.py` (1429 lines)

Endpoints present: list, detail, execution session, execution events, approvals, timeline, next actions, dashboard summary, resolve, payment-resolve.

Issues:
- **No permission classes** — all endpoints are effectively open.
- **No error handling** — naked `ContractObligation.objects.get()` calls throughout; any missing record returns a 500.
- **No state transition validation** — `ObligationResolveAPIView` does not check current state before resolving.
- **No pagination** on list endpoints.
- Heavy manual JSON building instead of serializers.
- Zero API tests.

---

## Part 3: Payment Domain

### 3.1 Model

**`Payment`** model is comprehensive: status timestamps per transition (`confirmed_at`, `failed_at`, etc.), `metadata` JSON field, `payment_method`, link to both contract and specific obligation.

Issues:
- No link between `Payment.amount` and `ContractObligation.amount_paid` at the model level.
- No idempotency key for duplicate detection.
- No DB constraints preventing payment in a terminal state from being re-transitioned.

### 3.2 Services

**`ContractPaymentService.apply_payment()`**
`engine/contracts/services/payment_service.py` — follows the right pattern (mutate primitive → run engine → persist) but calls `obligation_repo.update_state()` which isn't in the interface (BUG-5).

**`PaymentService.process_payment()`**
`engine/payments/payment_service.py` — calls `contract.apply_payment()` which doesn't exist (BUG-6). Also has no `@transaction.atomic`.

### 3.3 API Layer

**File**: `api/payments/views.py`

Endpoints present: list/create, detail, confirm, fail, cancel, refund, reverse, contract payments, obligation payments, dashboard summary, contract summary, obligation summary.

#### Critical Issue: Payment API never updates obligation balances

When a payment is created or confirmed via the API, `ContractObligation.amount_paid` is never updated. Payments and obligation balances are completely decoupled. The state engine will never see payments made through the API.

Other issues:
- **No permission classes** — all endpoints open.
- **No `@transaction.atomic`** on create or status transitions — partial saves are possible.
- **No state transition validation** — can transition from `draft` to `refunded` directly.
- **Naive status clearing** — when marking confirmed, explicitly nulls out `failed_at`, `cancelled_at`, etc. Fragile pattern.
- **Naked `.get()` calls** — no try/except, any missing record returns 500.
- Zero API tests.

---

## Part 4: Cross-Cutting Concerns

### Authentication / Authorization

**Status: Absent.**

- No `DEFAULT_AUTHENTICATION_CLASSES` or `DEFAULT_PERMISSION_CLASSES` in `settings.py`.
- All API views have `AllowAny` or no permission class.
- No ownership checks — any request can read or modify any contract, obligation, or payment.
- No audit trail of who performed what action.

### Error Handling

**Status: Inconsistent, largely absent in API layer.**

Engine services have some validation (amount > 0, etc.). API views have almost none. Pattern throughout the API layer is bare `objects.get()` with no exception handling. No custom exception classes exist outside of `contracts/exceptions.py`.

### Transaction Boundaries

`process_obligation_lifecycle()` has `@transaction.atomic` — correct.
Payment creation and status transitions in the API have none — incorrect. Multiple saves in a single request are not atomic.

### Test Coverage

Engine has reasonable coverage:
- `engine/contracts/tests/test_full_contract_cycle.py`
- `engine/contracts/tests/test_reconstruction.py`
- `engine/payments/tests/test_payment_service.py`

Tests use fake/mock objects (e.g. `FakeContract`) rather than Django models, so mismatches between engine primitives and actual models aren't caught.

API layer: **zero tests**.

---

## Bug Registry

### Blockers (will crash at runtime)

| ID | Description | File | Line |
|----|-------------|------|------|
| BUG-1 | `grace_days` passed to constructors that don't accept it | `lifecycle_core/scheduler/scheduler.py` | 52, 65 |
| BUG-2 | `obligation.deadline()` doesn't exist | `lifecycle_core/state/escalation.py` | 26, 29 |
| BUG-3 | Escalation guard never passes (`"defaulted"` never produced) | `lifecycle_core/state/escalation.py` | 23 |
| BUG-4 | Contract never reaches `"breached"` state | `contracts/domain/contract.py` | 80 |
| BUG-5 | 5 repository methods called but absent from interface | `contracts/interfaces.py` | — |
| BUG-6 | `contract.apply_payment()` not defined | `engine/payments/payment_service.py` | — |
| BUG-7 | `Contract.refresh()` requires 2 args; tests pass 0 | `contracts/domain/contract.py` | 33 |

### High-Risk (silent data corruption or open access)

| ID | Description | File |
|----|-------------|------|
| BUG-8 | Payment API never updates `ContractObligation.amount_paid` | `api/payments/views.py` |
| BUG-9 | No authentication on any endpoint | `api/` |
| BUG-10 | No `@transaction.atomic` on payment creation/transitions | `api/payments/views.py` |
| BUG-11 | No state transition validation on obligation resolve | `api/obligations/views.py` |
| BUG-12 | Naked `objects.get()` throughout API layer | `api/obligations/views.py`, `api/payments/views.py` |

### Medium (incorrect behaviour, not crashes)

| ID | Description | File |
|----|-------------|------|
| BUG-13 | `datetime.utcnow()` mixed with `timezone.now()` | `contracts/obligations/account.py:27` |
| BUG-14 | `MockPaymentGateway` doesn't implement `PaymentGateway` | `engine/payments/mock_gateway.py` |
| BUG-15 | `is_defaulted` flag duplicates `state == "defaulted"` | `contracts/models.py` |
| BUG-16 | Model state choices include states the engine never produces | `contracts/models.py` |

---

## Missing Implementations

### Engine

- Grace period enforcement — parameter exists in scheduler, never stored or evaluated
- `"defaulted"` state production — time-based rule (e.g. 30+ days overdue) not implemented
- Recurrence service — `contracts/obligations/recurrence.py` is empty
- Import service — `contracts/services/import_service.py` is empty
- Change request system — `contracts/change_request.py` is a 4-line stub

### Obligations

- Recurrence expansion — `Obligation` template model has fields, no service uses them
- Service obligation lateness tracking in `ContractServiceObligation`
- Approval workflow enforcement
- Execution session closure logic

### Payments

- Payment → obligation balance sync (most critical missing piece)
- Real payment gateway implementation
- Idempotency key for duplicate prevention
- Refund/reversal behaviour (status set, but no obligation reversal)
- Payment reconciliation

### Cross-cutting

- Authentication and ownership checks
- Consistent error responses
- Pagination on list endpoints
- API-layer tests
- Audit logging

---

## Fix Priority

### Fix first (nothing works without these)

1. Add missing methods to `contracts/interfaces.py`: `get_signed_version`, `list_candidates`, `update_state`, `get_all`
2. Implement those methods in the concrete repository
3. Fix or delete `lifecycle_core/scheduler/scheduler.py` — use `obligation_scheduler.py` only

### Fix before any payment work

4. Add `@transaction.atomic` to payment creation and all status transitions
5. Implement payment → obligation balance sync in payment confirmation flow
6. Add exception handling (`get_object_or_404` or try/except) throughout API views

### Fix before any lifecycle work

7. Decide on the DEFAULTED state: implement it in the evaluator (e.g. overdue for N days = defaulted) or remove the dead escalation/breach path entirely
8. Fix `obligation.deadline()` → `obligation.due_date` in `escalation.py`
9. Fix `Contract.refresh()` signature to make `now` and `obligation_repo` optional

### Fix before any production use

10. Add JWT authentication and `IsAuthenticated` as defaults in `settings.py`
11. Add ownership permission checks to all API views
12. Replace `datetime.utcnow()` with `timezone.now()` in `account.py`

### Clean up

13. Delete `lifecycle_core/scheduler/scheduler.py` (after fixing above)
14. Delete or implement the 5 empty placeholder files
15. Rename `contracts/tests/--init--.py` to `__init__.py`
16. Fix `MockPaymentGateway` to inherit from `PaymentGateway` and return `PaymentResult`
17. Choose one obligation class hierarchy (`primitives.py` vs `instances/`) and delete the other

---

## What's Safe to Build On

| Component | File | Confidence |
|-----------|------|------------|
| `PaymentObligation` / `ServiceObligation` | `lifecycle_core/obligations/primitives.py` | High |
| `ObligationScheduler` (clean version) | `lifecycle_core/scheduler/obligation_scheduler.py` | High |
| `evaluate_obligation_state()` | `lifecycle_core/state/evaluator.py` | High |
| `contracts/state_machine.py` | — | High |
| `contracts/versioning.py` | — | High |
| `process_obligation_lifecycle()` | `contracts/obligations/lifecycle.py` | High |
| `Contract` aggregate pattern | `contracts/domain/contract.py` | Medium (signature fix needed) |
| Automation runner/factory | `automation/` | Medium |
| `Payment` model | `payments/models.py` | Medium (no sync logic yet) |
| `ContractObligation` / `ContractServiceObligation` models | `contracts/models.py` | Medium (state alignment needed) |

## What Not to Build On (Yet)

| Component | Reason |
|-----------|--------|
| `lifecycle_core/scheduler/scheduler.py` | Crashes on grace_days |
| `lifecycle_core/state/escalation.py` | Dead code + crash on deadline() |
| `engine/payments/payment_service.py` | Calls undefined contract method |
| `engine/contracts/services/` (most) | Interface methods missing |
| `api/payments/views.py` | No obligation sync, no auth, no transactions |
| `api/obligations/views.py` | No auth, no error handling |
| Any DEFAULTED/BREACHED state logic | Evaluator never produces these states |
