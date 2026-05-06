# Payments Architecture

> Status: Current  
> Source of truth: code first, this document second  
> Scope: Payment model, payment API routes (13 routes, 10 view classes), obligation amount_paid write path, and engine-layer payment abstractions

---

## 1. Overview

The payments domain tracks individual payment records against contracts and contract payment obligations. A `Payment` record is created with a status of `draft` and progresses through status transitions (pending → confirmed, or to failed/cancelled/refunded/reversed) via dedicated action endpoints. The domain's primary side effect is maintaining `ContractObligation.amount_paid`: when a payment is confirmed, refunded, or reversed, the view recomputes `amount_paid` as the aggregate sum of all confirmed payments for that obligation and calls `process_obligation_lifecycle()` to re-evaluate obligation state. The payment API is the only live write path for `amount_paid`. A separate engine-layer `PaymentService` and `PaymentGateway` abstraction exist in `backend/engine/payments/` but are not wired to any live API route.

---

## 2. Models

### Payment

`backend/payments/models.py:8`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, `uuid4`, not editable |
| contract | FK → contracts.Contract | CASCADE, null=True, blank=True; `related_name="payments"` |
| payment_obligation | FK → contracts.ContractObligation | CASCADE, null=True, blank=True; `related_name="payments"` |
| payer | FK → AUTH_USER_MODEL | CASCADE; `related_name="sent_payments"` |
| payee | FK → AUTH_USER_MODEL | CASCADE; `related_name="received_payments"` |
| amount | DecimalField(12,2) | |
| currency | CharField(10) | choices from `backend/core/currencies.CURRENCY_CHOICES`; default `"USD"` |
| status | CharField(20) | choices below; default `"draft"` |
| payment_method | CharField(20) | choices below; default `"manual"` |
| idempotency_key | CharField(255) | null=True, blank=True, unique=True |
| reference | CharField(255) | null=True, blank=True |
| metadata | JSONField | default=dict, blank=True |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |
| confirmed_at | DateTimeField | null=True |
| failed_at | DateTimeField | null=True |
| cancelled_at | DateTimeField | null=True |
| refunded_at | DateTimeField | null=True |
| reversed_at | DateTimeField | null=True |

`Meta.ordering = ["-created_at"]` (`backend/payments/models.py:84`)

**Status choices** (`backend/payments/models.py:9`):

| Value | Label |
|---|---|
| `draft` | Draft |
| `pending` | Pending |
| `confirmed` | Confirmed |
| `failed` | Failed |
| `cancelled` | Cancelled |
| `refunded` | Refunded |
| `reversed` | Reversed |

**Payment method choices** (`backend/payments/models.py:19`):

| Value | Label |
|---|---|
| `cash` | Cash |
| `card` | Card |
| `bank_transfer` | Bank Transfer |
| `manual` | Manual |

Both `contract` and `payment_obligation` are nullable. No DB constraint enforces that they are set.

---

## 3. Core Concepts

### What a Payment represents

A `Payment` record is a discrete payment event — an amount from a payer to a payee, optionally linked to a contract and/or a `ContractObligation`. The model itself carries no business logic; all state transitions are performed by API views.

### Relationship to ContractObligation

`Payment.payment_obligation` is a nullable FK to `ContractObligation` (`backend/payments/models.py:36`). When set, confirming, refunding, or reversing a payment triggers a recompute of `ContractObligation.amount_paid` and a re-evaluation of the obligation's lifecycle state.

`ContractObligation` is documented fully in `obligations_lifecycle.md`. This document only covers the three write sites for `amount_paid` that live in the payments domain.

### Idempotency mechanism

`Payment.idempotency_key` is a unique field (`backend/payments/models.py:71`). The helper `_idempotency_response(key)` (`backend/api/payments/views.py:38`) checks for an existing payment with that key before creation. If found, the existing payment is returned with HTTP 200 instead of creating a duplicate. This is checked at the top of POST handlers in `PaymentListCreateAPIView`, `ContractPaymentListCreateAPIView`, and `ObligationPaymentListCreateAPIView`.

### The amount_paid recompute pattern

`ContractObligation.amount_paid` is not incremented additively. On each of the three write sites (confirm, refund, reverse), `amount_paid` is recomputed as:

```python
Payment.objects
    .filter(payment_obligation_id=obligation.id, status="confirmed")
    .aggregate(total=Sum("amount"))["total"]
```

(`backend/api/payments/views.py:239–242`, `381–385`, `429–433`)

This sum is the authoritative total. After writing `amount_paid`, `process_obligation_lifecycle(obligation, obligation_repo=None, current_time=now)` is called to re-evaluate the obligation's state. This is the only live path that advances `ContractObligation` beyond `state="active"`.

### Valid state transitions

`ALLOWED_FROM` (`backend/api/payments/views.py:25`) defines legal source states for each transition endpoint:

| Target status | Allowed from |
|---|---|
| `pending` | `draft` |
| `confirmed` | `pending` |
| `failed` | `pending` |
| `cancelled` | `draft`, `pending` |
| `refunded` | `confirmed` |
| `reversed` | `confirmed` |

Any request that violates these transitions returns HTTP 409.

---

## 4. Current Behavior

All routes are under the prefix registered for the payments API. The `backend/api/payments/urls.py` confirms the 13 URL patterns below.

---

### `GET /api/payments/`

**View**: `PaymentListCreateAPIView.get()` (`backend/api/payments/views.py:109`)  
**Permission/gate**: Authenticated; `has_feature(request.user, "lifecycle")` required — returns HTTP 403 with PAYG-blocked message if not (`views.py:110`).  
**What it does**: Filters `Payment` objects to contracts where the user is initiator or counterparty (`_party_q`), applies optional query-param filters (`status`, `payment_method`, `created_after`, `created_before`, `currency`), paginates (default 20, max 100).  
**State transitions**: None.  
**Side effects**: None.

---

### `POST /api/payments/`

**View**: `PaymentListCreateAPIView.post()` (`backend/api/payments/views.py:118`)  
**Permission/gate**: Authenticated; `has_feature(request.user, "lifecycle")` required (`views.py:119`); `is_party()` check on the contract if a `contract_id` is present (`views.py:138`).  
**What it does**: Checks idempotency key if provided. Validates via `PaymentSerializer`, saves in an atomic transaction. Logs `payment_created` activity.  
**State transitions**: None (payment created with default status `"draft"`).  
**Side effects**: `log_activity` with `activity_type="payment_created"`.

---

### `GET /api/payments/<payment_id>/`

**View**: `PaymentDetailAPIView.get()` (`backend/api/payments/views.py:164`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Returns the payment record.  
**State transitions**: None.  
**Side effects**: None.

---

### `PATCH /api/payments/<payment_id>/`

**View**: `PaymentDetailAPIView.patch()` (`backend/api/payments/views.py:170`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Partial update via `PaymentSerializer`. Saves in an atomic transaction.  
**State transitions**: None enforced by this endpoint; any writable field including `status` can be patched (serializer does not restrict which fields are writable beyond `read_only_fields`). See section 7 for a note.  
**Side effects**: None (no `log_activity` call, no obligation recompute).

---

### `DELETE /api/payments/<payment_id>/`

**View**: `PaymentDetailAPIView.delete()` (`backend/api/payments/views.py:184`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Deletes the payment record. Returns HTTP 204.  
**State transitions**: None.  
**Side effects**: None (no `log_activity` call, no obligation recompute on deletion).

---

### `POST /api/payments/<payment_id>/pending/`

**View**: `PaymentPendingAPIView.post()` (`backend/api/payments/views.py:274`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Transitions payment from `draft` → `pending`. Returns HTTP 409 if source state not in `ALLOWED_FROM["pending"]`.  
**State transitions**: `status = "pending"`. Saves `update_fields=["status", "updated_at"]`.  
**Side effects**: None (no `log_activity`, no obligation recompute).

---

### `POST /api/payments/<payment_id>/confirm/`

**View**: `PaymentConfirmAPIView.post()` (`backend/api/payments/views.py:198`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Transitions payment from `pending` → `confirmed`. If `payment.payment_obligation_id` is set, acquires `select_for_update()` on the obligation, recomputes `amount_paid`, calls `process_obligation_lifecycle()`, updates `is_defaulted`, saves obligation. Returns HTTP 409 if source state not `pending`.  
**State transitions**:  
- Payment: `status = "confirmed"`, `confirmed_at = now`, clears `failed_at`, `cancelled_at`, `refunded_at`, `reversed_at`.  
- Obligation (if linked): `amount_paid` recomputed, `state` updated by lifecycle engine, `is_defaulted` updated.  
**Side effects**: `log_activity` with `activity_type="payment_confirmed"`.

---

### `POST /api/payments/<payment_id>/fail/`

**View**: `PaymentFailAPIView.post()` (`backend/api/payments/views.py:292`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Transitions payment from `pending` → `failed`. Returns HTTP 409 if source state not in `ALLOWED_FROM["failed"]`.  
**State transitions**: `status = "failed"`, `failed_at = now`. Saves `update_fields=["status", "failed_at", "updated_at"]`.  
**Side effects**: `log_activity` with `activity_type="payment_failed"`. No obligation recompute (payment moving to `failed` does not change confirmed sum).

---

### `POST /api/payments/<payment_id>/cancel/`

**View**: `PaymentCancelAPIView.post()` (`backend/api/payments/views.py:323`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Transitions payment from `draft` or `pending` → `cancelled`. Returns HTTP 409 if source state not in `ALLOWED_FROM["cancelled"]`.  
**State transitions**: `status = "cancelled"`, `cancelled_at = now`. Saves `update_fields=["status", "cancelled_at", "updated_at"]`.  
**Side effects**: `log_activity` with `activity_type="payment_cancelled"`. No obligation recompute.

---

### `POST /api/payments/<payment_id>/refund/`

**View**: `PaymentRefundAPIView.post()` (`backend/api/payments/views.py:354`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Transitions payment from `confirmed` → `refunded`. If `payment.payment_obligation_id` is set, acquires `select_for_update()` on the obligation, recomputes `amount_paid` from confirmed payments (refunded payment is no longer `confirmed`, so it drops from the sum), calls `process_obligation_lifecycle()`, updates `is_defaulted`, saves obligation. Returns HTTP 409 if source state not `confirmed`.  
**State transitions**:  
- Payment: `status = "refunded"`, `refunded_at = now`.  
- Obligation (if linked): `amount_paid` recomputed, `state` updated, `is_defaulted` updated.  
**Side effects**: `log_activity` with `activity_type="payment_refunded"`.

---

### `POST /api/payments/<payment_id>/reverse/`

**View**: `PaymentReverseAPIView.post()` (`backend/api/payments/views.py:402`)  
**Permission/gate**: `is_party()` on `payment.contract`.  
**What it does**: Transitions payment from `confirmed` → `reversed`. Same obligation recompute pattern as refund. Returns HTTP 409 if source state not `confirmed`.  
**State transitions**:  
- Payment: `status = "reversed"`, `reversed_at = now`.  
- Obligation (if linked): `amount_paid` recomputed, `state` updated, `is_defaulted` updated.  
**Side effects**: `log_activity` with `activity_type="payment_reversed"`.

---

### `GET /api/payments/dashboard-summary/`

**View**: `PaymentDashboardSummaryAPIView.get()` (`backend/api/payments/views.py:547`)  
**Permission/gate**: Authenticated; no `has_feature` gate.  
**What it does**: Aggregates payment counts and amounts for all contracts where the user is a party. Returns total count, total amount, confirmed amount, refunded amount, reversed amount, and per-status counts for all 7 statuses.  
**State transitions**: None.  
**Side effects**: None.

---

### `GET /api/payments/contracts/<contract_id>/`

**View**: `ContractPaymentListCreateAPIView.get()` (`backend/api/payments/views.py:456`)  
**Permission/gate**: `is_party()` on the contract; no `has_feature` gate on GET.  
**What it does**: Lists payments scoped to the given contract with query-param filtering and pagination.  
**State transitions**: None.  
**Side effects**: None.

---

### `POST /api/payments/contracts/<contract_id>/`

**View**: `ContractPaymentListCreateAPIView.post()` (`backend/api/payments/views.py:467`)  
**Permission/gate**: `is_party()` on the contract; **no `has_feature` gate** (see section 7).  
**What it does**: Checks idempotency key if provided. Forces `contract` field to `contract_id` from URL. Validates via `PaymentSerializer`, saves in an atomic transaction. No `log_activity` call.  
**State transitions**: None (payment created with default status `"draft"`).  
**Side effects**: None (no `log_activity`).

---

### `GET /api/payments/contracts/<contract_id>/summary/`

**View**: `ContractPaymentSummaryAPIView.get()` (`backend/api/payments/views.py:580`)  
**Permission/gate**: `is_party()` on the contract.  
**What it does**: Returns aggregate payment stats for the contract: total count, total amount, confirmed amount, refunded amount, failed count, cancelled count.  
**State transitions**: None.  
**Side effects**: None.

---

### `GET /api/payments/obligations/<obligation_id>/`

**View**: `ObligationPaymentListCreateAPIView.get()` (`backend/api/payments/views.py:498`)  
**Permission/gate**: `is_party()` on `obligation.contract`.  
**What it does**: Lists payments scoped to the given obligation with query-param filtering and pagination.  
**State transitions**: None.  
**Side effects**: None.

---

### `POST /api/payments/obligations/<obligation_id>/`

**View**: `ObligationPaymentListCreateAPIView.post()` (`backend/api/payments/views.py:509`)  
**Permission/gate**: `is_party()` on `obligation.contract`; no `has_feature` gate.  
**What it does**: Checks idempotency key if provided. Rejects creation if the obligation's state is `resolved`, `breached`, or `defaulted` (HTTP 409). Forces `contract` and `payment_obligation` fields from URL. Validates via `PaymentSerializer`, saves in an atomic transaction.  
**State transitions**: None (payment created with default status `"draft"`).  
**Side effects**: None (no `log_activity`).

---

### `GET /api/payments/obligations/<obligation_id>/summary/`

**View**: `ObligationPaymentSummaryAPIView.get()` (`backend/api/payments/views.py:604`)  
**Permission/gate**: `is_party()` on `obligation.contract`.  
**What it does**: Returns aggregate payment stats for the obligation: obligation state, `amount_due`, `amount_paid`, remaining balance (`amount_due - amount_paid`), payment counts and amounts by status.  
**State transitions**: None.  
**Side effects**: None.

---

## 5. Authority / Access Rules

### is_party() check

All payment endpoints enforce `is_party()` (`backend/api/contracts/permissions.py`):

```python
contract.initiator_id == user.pk OR contract.counterparty_email == user.email
```

No initiator-vs-counterparty distinction. Both parties may create, read, update, delete, and transition payments.

### Billing feature gate

`has_feature(request.user, "lifecycle")` is checked in:  
- `PaymentListCreateAPIView.get()` (`views.py:110`)  
- `PaymentListCreateAPIView.post()` (`views.py:119`)

These are the only two endpoints with a billing gate. The gate is absent from all other payment endpoints, including the per-contract and per-obligation create routes.

### PAYG-blocked message

`_PAYG_BLOCKED` (`views.py:22`): `"This feature requires a monthly plan. Upgrade to Blackboard Basic ($19/month) to unlock contract management."`  
Returned as HTTP 403 when the lifecycle feature is not enabled.

---

## 6. Relationship to Other Domains

### obligations_lifecycle.md

`ContractObligation.amount_paid` is written exclusively by the payments domain. The three write sites are `PaymentConfirmAPIView`, `PaymentRefundAPIView`, and `PaymentReverseAPIView` in `backend/api/payments/views.py`. Each site recomputes `amount_paid` as the aggregate of all confirmed payments and calls `process_obligation_lifecycle()` to advance the obligation's state machine. The obligation model, its states, and `process_obligation_lifecycle()` are documented in `obligations_lifecycle.md`.

### Billing domain (Stripe)

Stripe integration belongs to the billing domain and is documented separately in `billing.md` (when written). The payments domain has no Stripe references. `has_feature()` is imported from `backend/billing/gates` (`views.py:19`) but Stripe itself is not part of this domain.

### Engine layer (disconnected)

`backend/engine/payments/payment_service.py` contains `PaymentService`, a gateway-aware engine class that calls `gateway.charge()`, `contract.apply_payment()`, `contract.refresh_state()`, and `process_obligation_lifecycle()` (`payment_service.py:42–63`).

`backend/engine/payments/gateway.py` defines `PaymentGateway` (abstract base class, one method: `charge()`) and `PaymentResult` (`gateway.py:5–22`).

`backend/engine/payments/mock_gateway.py` defines `MockPaymentGateway`, which always returns `PaymentResult(success=True, transaction_id="mock_txn_123")` (`mock_gateway.py:11`).

The file header of `payment_service.py` states explicitly: "It is NOT imported by any live API view." (`payment_service.py:8`). No import of `PaymentService` or `PaymentGateway` was found in `backend/api/payments/views.py`. These engine classes are not wired to the live API.

---

## 7. Current Gaps

### ContractPaymentListCreateAPIView POST has no lifecycle feature gate

`PaymentListCreateAPIView.post()` requires `has_feature(request.user, "lifecycle")` (`views.py:119`).  
`ContractPaymentListCreateAPIView.post()` does not check this gate (`views.py:467–489`).  
A user who fails the lifecycle feature check can still create payments via the contract-scoped route.

### PaymentResolutionService does not call process_obligation_lifecycle

`backend/api/contracts/services/payment_resolution_service.py:PaymentResolutionService.resolve()` sets `obligation.state = "resolved"` directly and saves with `update_fields=["state"]` (`payment_resolution_service.py:24–31`).  
It does not call `process_obligation_lifecycle()` before writing the state, and it does not verify `amount_paid` against the current confirmed payment sum.  
This diverges from the confirm/refund/reverse path in `views.py`, which always recomputes `amount_paid` from confirmed payments before writing state.  
`PaymentResolutionService` is called from `backend/api/contracts/resolve_views.py:ContractPaymentResolveAPIView` and is documented as the payment obligation resolution path in `obligations_lifecycle.md`.

### Engine-layer PaymentService and PaymentGateway are unwired

`PaymentService`, `PaymentGateway`, and `MockPaymentGateway` exist in `backend/engine/payments/` with working tests (noted in `payment_service.py:7`). None of these are imported or called by any live API view. The live payment path is direct ORM operations in `backend/api/payments/views.py`. The engine layer represents an alternative architecture that is not currently connected.

### PATCH endpoint can bypass state machine

`PaymentDetailAPIView.patch()` uses `PaymentSerializer` with `partial=True`. The serializer's `read_only_fields` list (`serializers.py:32`) does not include `status`. A PATCH to `status` can set any value without going through `ALLOWED_FROM` transition checks or obligation recompute logic.

### DELETE endpoint has no obligation recompute

`PaymentDetailAPIView.delete()` deletes the payment record without checking its current status or recomputing `ContractObligation.amount_paid`. Deleting a `confirmed` payment would leave `amount_paid` inflated on the linked obligation until the next confirm/refund/reverse action.

### No log_activity on ContractPaymentListCreateAPIView POST

`PaymentListCreateAPIView.post()` calls `log_activity` on payment creation (`views.py:144`). `ContractPaymentListCreateAPIView.post()` and `ObligationPaymentListCreateAPIView.post()` do not (`views.py:483–489`, `533–539`).

---

## 8. Open Questions

1. **PATCH status bypass** — Whether PATCH bypassing the state machine is intentional (e.g., for admin correction) or an oversight is not determinable from code alone.

2. **DELETE and amount_paid** — Whether the absence of obligation recompute on DELETE is intentional (relying on operators to only delete draft/non-confirmed payments) is not established in code.

3. **ContractPaymentListCreateAPIView POST — no log_activity** — Whether the absence of activity logging on this create route is intentional or an omission is not established.

4. **process_obligation_lifecycle with obligation_repo=None** — All three obligation write sites in views.py call `process_obligation_lifecycle(obligation, obligation_repo=None, current_time=now)`. The behavior of `obligation_repo=None` inside `process_obligation_lifecycle` was not inspected in this audit; it is not clear whether passing None suppresses any persistence.

5. **Dashboard summary — no billing gate** — `PaymentDashboardSummaryAPIView` has no `has_feature` gate, unlike `PaymentListCreateAPIView`. Whether this is intentional is not established in code.
