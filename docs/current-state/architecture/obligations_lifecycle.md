# Obligations Lifecycle Architecture

> Status: Current  
> Source of truth: code first, this document second  
> Scope: Post-contract obligations, execution sessions, approval flows, value adjustments, promotions, and resolution

---

## 1. Overview

The obligations lifecycle governs how work and payments are tracked after a contract is created. It covers two obligation types — payment (`ContractObligation`) and service (`ContractServiceObligation`) — along with the execution session and event system that tracks actual work performed, an approval layer that drives value adjustments and obligation promotions, and resolution paths for both types. Two separate API modules expose obligation functionality: a contract-scoped module under `/api/contracts/` and a user-scoped module under `/api/obligations/`. The payment domain (`/api/payments/`) intersects the lifecycle by updating `amount_paid` on payment obligations when payments are confirmed or refunded.

---

## 2. Models

### ContractObligation (payment obligation)

`backend/contracts/models.py:385`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, auto |
| contract | FK → Contract | CASCADE |
| version | FK → ContractVersion | CASCADE |
| obligor | FK → User | CASCADE, `related_name="owed_obligations"` |
| obligee | FK → User | CASCADE, `related_name="receivable_obligations"` |
| installment_number | PositiveIntegerField | |
| amount_due | DecimalField(12,2) | |
| currency | CharField | choices from CURRENCY_CHOICES, default "USD" |
| amount_paid | DecimalField(12,2) | default=0 |
| due_date | DateTimeField | |
| state | CharField | choices below, default "active" |
| is_defaulted | BooleanField | default=False |
| created_at / updated_at | DateTimeField | auto |

State choices (`backend/contracts/models.py:392`): `active`, `due`, `grace`, `overdue`, `defaulted`, `resolved`

Method `is_past_due()` (`backend/contracts/models.py:472`): returns True when `state=="active"` AND `amount_paid < amount_due` AND `due_date < current_time`. Not called from any obligation API view.

---

### ContractServiceObligation (service obligation)

`backend/contracts/models.py:486`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, auto |
| contract | FK → Contract | CASCADE |
| version | FK → ContractVersion | CASCADE |
| obligor | FK → User | CASCADE, `related_name="service_owed"` |
| obligee | FK → User | CASCADE, `related_name="service_receivable"` |
| description | TextField | |
| due_date | DateTimeField | |
| state | CharField | choices below, default "active" |
| completed_at | DateTimeField | null=True |
| created_at / updated_at | DateTimeField | auto |

State choices (`backend/contracts/models.py:488`): `active`, `due`, `overdue`, `resolved`  
No `grace` or `defaulted` states (unlike ContractObligation).

Method `mark_completed()` (`backend/contracts/models.py:537`): sets `state="resolved"`, `completed_at=timezone.now()`, saves `update_fields=["state", "completed_at", "updated_at"]`.

---

### ObligationExecutionSession

`backend/contracts/models.py:545`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, auto |
| payment_obligation | FK → ContractObligation | null=True, blank=True |
| service_obligation | FK → ContractServiceObligation | null=True, blank=True |
| started_at | DateTimeField | |
| ended_at | DateTimeField | null=True |
| status | CharField | choices: `active`, `closed`; default "active" |
| created_at | DateTimeField | auto |

Both obligation FKs are nullable. No DB constraint enforces that exactly one is set (`backend/contracts/models.py:559–573`).

---

### ObligationExecutionEvent

`backend/contracts/models.py:590`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, auto |
| session | FK → ObligationExecutionSession | CASCADE, `related_name="events"` |
| event_type | CharField(100) | set to `"execution_item_recorded"` by service |
| task | CharField(255) | null=True |
| observation | CharField(255) | null=True |
| summary | TextField | |
| estimated_duration_minutes | PositiveIntegerField | null=True |
| estimated_cost_amount | DecimalField(12,2) | null=True |
| estimated_cost_currency | CharField(10) | null=True |
| planned_execution_time | DateTimeField | null=True |
| metadata | JSONField | default=dict; evaluator decision stored here |
| created_at | DateTimeField | auto |

---

### ContractValueAdjustment

`backend/contracts/models.py:640`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, auto |
| contract | FK → Contract | CASCADE |
| payment_obligation | FK → ContractObligation | null=True |
| service_obligation | FK → ContractServiceObligation | null=True |
| execution_event | FK → ObligationExecutionEvent | SET_NULL, null=True |
| adjustment_type | CharField | choices: `additional_charge`, `lateness_adjustment` |
| mode | CharField | choices: `fixed_amount`, `percentage` |
| amount | DecimalField(12,2) | |
| currency | CharField | default "USD" |
| summary | TextField | |
| created_at | DateTimeField | auto |

---

### ContractApprovalRequest

`backend/contracts/models.py:724`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, auto |
| contract | FK → Contract | CASCADE |
| payment_obligation | FK → ContractObligation | null=True |
| service_obligation | FK → ContractServiceObligation | null=True |
| execution_event | FK → ObligationExecutionEvent | SET_NULL, null=True |
| requested_by | FK → User | SET_NULL, null=True |
| requested_from | FK → User | SET_NULL, null=True |
| approval_type | CharField(50) | default `"execution_item"` |
| status | CharField | choices: `pending`, `approved`, `rejected`; default "pending" |
| summary | TextField | |
| metadata | JSONField | default=dict; carries evaluator decision fields |
| requested_at | DateTimeField | auto |
| decided_at | DateTimeField | null=True |

---

### ContractObligationPromotion

`backend/contracts/models.py:859`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, auto |
| contract | FK → Contract | CASCADE |
| source_execution_event | FK → ObligationExecutionEvent | CASCADE |
| parent_service_obligation | FK → ContractServiceObligation | null=True, `related_name="child_promotions"` |
| promoted_service_obligation | FK → ContractServiceObligation | null=True, `related_name="origin_promotions"` |
| promotion_type | CharField | choices: `event_to_service_obligation`; default same |
| summary | TextField | |
| created_at | DateTimeField | auto |

---

### Obligation (template model)

`backend/contracts/models.py:226`

Fields: `id`, `contract` (FK), `obligation_type` (payment/service), `from_party`, `to_party`, `description`, `amount`, `currency`, `start_date`, `due_date`, `recurrence_interval_days`, `recurrence_count`, `state` (pending/due/fulfilled/overdue/cancelled).

Docstring states: "The engine expands this into actual lifecycle instances stored in ContractObligation." No code path performing this expansion was found. See Open Questions.

---

## 3. Core Concepts

### Two obligation types

`ContractObligation` tracks payment commitments with monetary fields. `ContractServiceObligation` tracks non-payment commitments with a description. Both are created per contract + version and link to obligor/obligee users.

### Execution sessions and events

A session (`ObligationExecutionSession`) represents a working period on an obligation. Sessions contain events (`ObligationExecutionEvent`), each of which records a discrete piece of work with estimates for duration and cost. Both payment and service obligations can have execution sessions, though promotion (converting events to new obligations) only works for service sessions.

### Evaluator and decision output

`ExecutionEvaluator` (`backend/engine/lifecycle_core/execution/evaluator.py:7`) evaluates each execution item and returns a structured decision. Currently always returns `decision_status="approval_required"` and `billing_mode="separate_charge"`. The only varying output is `promotion_suggestion`: `"suggest_side_obligation"` when `estimated_duration_minutes >= 120` OR `estimated_cost_amount >= 150`, otherwise `"keep_as_event"` (`evaluator.py:37–44`). The decision is stored in `event.metadata`.

### Approval flow

Every execution item produces a `ContractApprovalRequest` (because the evaluator always returns `approval_required`). Approving a request triggers two conditional follow-on actions in sequence: creating a value adjustment (if `billing_mode=="separate_charge"` and `estimated_cost_amount` is not None) and promoting the event to a new service obligation (if `promotion_suggestion=="suggest_side_obligation"`). Both are idempotent.

### Proof of work

`ProofOfWorkService` (`backend/api/contracts/services/proof_of_work_service.py:31`) assembles a read-only payload aggregating sessions, events, approvals, adjustments, and promotions for a given obligation. For service obligations the payload includes promotions and promoted side obligations. For payment obligations the promotions fields are always empty (`proof_of_work_service.py:89`).

---

## 4. Current Behavior

### Obligation creation

`backend/api/contracts/obligations_views.py:ContractObligationsAPIView.post()`  
Route: `POST /api/contracts/{contract_id}/obligations/`

- `is_party()` check only; both parties can create.
- No billing gate.
- No limit on number of obligations per contract.
- `ContractLifecycleService.create_obligation()` raises if no version exists for the contract (`backend/api/contracts/services/contract_lifecycle_service.py`).
- Does not require a signed version — any version suffices.
- Obligations are created with `state="active"` (model default).

### Opening an execution session

`backend/api/contracts/execution_views.py:ObligationExecutionSessionListCreateAPIView.post()`  
Route: `POST /api/contracts/obligations/<obligation_type>/<obligation_id>/execution-sessions/`

- `is_party()` check.
- Calls `ObligationExecutionService.open_session()` which creates an `ObligationExecutionSession` with `status="active"` (`obligation_execution_service.py:32–56`).
- Both `payment` and `service` obligation types accepted.

### Recording an execution item

`backend/api/contracts/execution_views.py:ExecutionItemCreateAPIView.post()`  
Route: `POST /api/contracts/execution-sessions/<session_id>/execution-items/`

- `is_party()` check via `get_contract_for_object(session)`.
- Calls `ObligationExecutionService.record_execution_item()` (`obligation_execution_service.py:58`):
  1. Builds `ExecutionItem` from request data.
  2. Runs `ExecutionEvaluator.evaluate(item)` — always returns `approval_required`.
  3. Creates `ObligationExecutionEvent` with `event_type="execution_item_recorded"` and stores evaluator decision in `metadata`.
  4. Because `decision_status == "approval_required"` (always), creates a `ContractApprovalRequest` via `ApprovalService.request_execution_item_approval()`.
- Response includes `event`, `decision`, and `approval_request` objects.

### Closing a session

`backend/api/contracts/execution_views.py:ExecutionSessionCloseAPIView.post()`  
Route: `POST /api/contracts/execution-sessions/<session_id>/close/`

- `is_party()` check.
- Sets `status="closed"`, sets `ended_at`.

### Approving an execution item

`backend/api/contracts/approval_views.py:ApprovalRequestApproveAPIView.post()`  
Route: `POST /api/contracts/approval-requests/<approval_id>/approve/`

- `is_party()` check.
- Additional gate: if `requested_from_id` is set and does not match `request.user.pk`, returns 403 (`approval_views.py:151–158`).
- Calls `ApprovalService.approve()` (`approval_service.py:71`):
  1. Marks approval request as approved via repo.
  2. `_create_adjustment_if_needed()`: creates `ContractValueAdjustment` of type `additional_charge` if `billing_mode == "separate_charge"` AND `estimated_cost_amount` is not None AND no existing adjustment for this event (idempotent check at `approval_service.py:98–102`).
  3. `_promote_if_needed()`: calls `ObligationPromotionService.promote_execution_event_to_service_obligation()` if `promotion_suggestion == "suggest_side_obligation"`.

### Rejecting an execution item

`backend/api/contracts/approval_views.py:ApprovalRequestRejectAPIView.post()`  
Route: `POST /api/contracts/approval-requests/<approval_id>/reject/`

- Same `is_party()` and `requested_from_id` gate as approve.
- Calls `ApprovalService.reject()` which marks status `rejected`. No follow-on actions.

### Promotion

`backend/api/contracts/services/obligation_promotion_service.py:ObligationPromotionService`

- Triggered by approval flow or directly via `POST /api/contracts/execution-events/<event_id>/promote/`.
- Idempotent: checks for existing promotion via `repo.find_for_execution_event(execution_event_id)` (`obligation_promotion_service.py:23–26`). If found, returns existing record without creating another.
- Raises if `session.service_obligation` is None — promotion only works for service obligation sessions (`obligation_promotion_service.py:44`).
- Creates a new `ContractServiceObligation` and a `ContractObligationPromotion` linking source event, parent obligation, and new obligation.

### Value adjustments (manual)

`backend/api/contracts/value_adjustment_views.py:ObligationValueAdjustmentListCreateAPIView.post()`  
Route: `POST /api/contracts/obligations/<obligation_type>/<obligation_id>/value-adjustments/`

- `is_party()` check.
- Only calls `ValueAdjustmentService.store_additional_charge()` (`value_adjustment_views.py:91–107`). Comment at line 28: "V1 write support is manual additional_charge only."
- `lateness_adjustment` type cannot be created via this endpoint.

### Service obligation resolution

`backend/api/contracts/resolve_views.py:ObligationResolveAPIView.post()` (service branch)  
Route: `POST /api/contracts/obligations/<obligation_type>/<obligation_id>/resolve/`

- `is_party()` check.
- If already resolved, returns 200 with current state (idempotent behavior, `resolve_views.py:27–39`).
- Otherwise calls `obligation.mark_completed()` → `state="resolved"`, `completed_at=now()`.

### Payment obligation resolution

`backend/api/contracts/resolve_views.py:ContractPaymentResolveAPIView.post()`  
Route: `POST /api/contracts/obligations/payment/<obligation_id>/resolve/`

- `is_party()` check.
- Calls `PaymentResolutionService.resolve()` (`payment_resolution_service.py:8`):
  - Raises if state is already `"resolved"`.
  - Raises if state is `"breached"` (state not reachable via current API).
  - Raises if `amount_paid < amount_due`.
  - Sets `state="resolved"`, saves.

`amount_paid` is updated by the payments module — specifically `PaymentConfirmAPIView` and `PaymentRefundAPIView` in `backend/api/payments/views.py:244,386`. On payment confirmation, `amount_paid` is recalculated as the sum of all confirmed payments for the obligation, and `process_obligation_lifecycle()` is called to re-evaluate state (`payments/views.py:247`).

### Proof of work

`backend/api/contracts/proof_views.py:ObligationProofOfWorkAPIView.get()`  
Route: `GET /api/contracts/obligations/<obligation_type>/<obligation_id>/proof/`

- `is_party()` check.
- Read-only. Calls `ProofOfWorkService().build_for_obligation()`.
- Returns: `obligation_summary`, `execution_summary`, `observations`, `decisions`, `approval_requests`, `value_adjustments`, `promotions`, `promoted_side_obligations`, `timeline`, `sessions`.
- For payment obligations: `promotions` and `promoted_side_obligations` are always empty lists (`proof_of_work_service.py:89`).
- Lateness adjustment params are not passed from this view, so `lateness_adjustment` records cannot be created via this endpoint.

### Obligation list (user-scoped)

`backend/api/obligations/views.py:ObligationListAPIView.get()`  
Route: `GET /api/obligations/`

- Billing gate: returns 403 if `has_feature(request.user, "lifecycle")` is False (`obligations/views.py:117`). This is the only obligation endpoint with a billing gate.
- Returns obligations across all contracts where the user is initiator or counterparty.
- Supports filtering by `type`, `state`, `role`, `contract_id`; paginated (default 20, max 100).

---

## 5. Authority / Access Rules

All obligation and execution endpoints use `is_party()`:  
`contract.initiator_id == user.pk OR contract.counterparty_email == user.email`  
(`backend/api/contracts/permissions.py`)

No initiator-vs-counterparty distinction for obligation actions. Both parties can:
- create obligations
- open/close execution sessions
- record execution items
- create/list approval requests and value adjustments
- resolve obligations
- view proof of work

**Exception — approval/reject gate** (`backend/api/contracts/approval_views.py:151–158`, `208–215`):  
If `ContractApprovalRequest.requested_from_id` is set, only the user whose `pk` matches `requested_from_id` may approve or reject. Any party may act when `requested_from` is null.

**Billing gate** (`backend/api/obligations/views.py:117`):  
Applied only to `GET /api/obligations/`. No other obligation endpoint has a billing gate.

**No Contract Pro integration**:  
No Contract Pro authority checks appear in any obligation or execution view.

---

## 6. Relationship to Other Domains

### contract_lifecycle.md

Obligations begin after a contract has at least one version. No signed version is required. No automatic obligation creation occurs on signing. No feedback path from obligation resolution back to `Contract.state` or `Contract.status`.

### authority.md

Obligations use `is_party()` only. No role-based authority. No Contract Pro delegation applied.

### payments domain

`backend/api/payments/views.py` updates `ContractObligation.amount_paid` on payment confirmation and refund. `process_obligation_lifecycle()` is called in those flows to re-evaluate obligation state. This is the only path that advances payment obligation state beyond `active`.

### entity_layer.md

Obligations operate at the `User` level (obligor/obligee are User FKs). Not integrated with the Entity layer.

---

## 7. Current Gaps

### State transitions not wired in obligation API

`ContractObligation` defines states `due`, `grace`, `overdue`, `defaulted`, but no obligation API view sets these states. They are only reachable via `process_obligation_lifecycle()` called from the payments module.  
`ContractServiceObligation` defines `due` and `overdue` but no API view sets them.

### lateness_adjustment not reachable via any API

`ValueAdjustmentService.store_lateness_adjustment()` is defined (`value_adjustment_service.py:20`).  
`ProofOfWorkService._ensure_service_lateness_adjustment_if_requested()` can create one, but only when `lateness_adjustment_enabled=True` is passed (`proof_of_work_service.py:338`).  
`ObligationProofOfWorkAPIView` calls `build_for_obligation()` with no lateness parameters (`proof_views.py:36–42`), so `lateness_adjustment_enabled` defaults to False.  
No other view calls these methods. `lateness_adjustment` type is defined in the model but has no live creation path.

### Duplicate resolve view definitions

`ObligationResolveAPIView` and `ContractPaymentResolveAPIView` are each defined in two files:
- `backend/api/contracts/resolve_views.py` — has `is_party()` check
- `backend/api/contracts/proof_views.py` — `ObligationResolveAPIView` lacks is_party check; `ContractPaymentResolveAPIView` lacks is_party check (`proof_views.py:46–127`)

The contracts URL router imports from `resolve_views` (`backend/api/contracts/urls.py` import line). The `proof_views.py` duplicate definitions are not routed via the contracts URL config but exist in the same module as the active proof endpoint.

### No contract state feedback from obligations

Resolving or creating obligations does not update `Contract.state`, `Contract.status`, or `Contract.is_active`. `Contract.refresh_state()` is never called from any obligation-related view or service.

### No signed-version requirement

`ContractLifecycleService.create_obligation()` checks for the existence of any contract version, not a signed one. Obligations can be created before a version is signed.

### Obligation template model (Obligation) — partial use

`backend/contracts/models.py:226` — model exists with fields for type, parties, amount, recurrence. No code path found that expands it into `ContractObligation` instances. Imported in `backend/api/obligations/serializers.py:2`. A separate URL prefix `obligation-templates/` is registered in the router (`backend/api/router.py:20`).

### Payment obligation promotion blocked

Promotion via `ObligationPromotionService` raises an exception if `session.service_obligation` is None (`obligation_promotion_service.py:44`). Execution sessions on payment obligations cannot trigger promotion.

### Service obligation resolve — ObligationResolveAPIView (resolve_views.py)

The payment branch returns a 400 with `"Payment obligation resolve is not supported yet."` (`resolve_views.py:63–67`). The separate `ContractPaymentResolveAPIView` (also in resolve_views.py) handles payment resolution correctly. Both are routed (`contracts/urls.py`), so the payment path through `ObligationResolveAPIView` is a dead branch.

### No obligation count limit

No maximum number of obligations per contract is enforced at creation time.

---

## 8. Open Questions

1. **`Obligation` template model** — The docstring at `backend/contracts/models.py:226` says "The engine expands this into actual lifecycle instances stored in ContractObligation" but no expansion code was found. The `obligation-templates/` URL prefix exists in the router. The relationship between `Obligation`, `ContractObligation`, and `backend/api/obligation_templates/` was not fully traced; those modules were not inspected.

2. **`backend/api/obligation_templates/` and `backend/api/payment_templates/`** — Both are registered in the router (`router.py:20–21`) but not inspected in this audit. Their relationship to obligation creation is unknown.

3. **`process_obligation_lifecycle()`** — Called from the payments module when payments are confirmed or refunded (`payments/views.py:247,387`). This function controls state transitions for payment obligations beyond `active`. Its full logic was not inspected in this audit.

4. **Payment obligation execution sessions** — Sessions can be opened on payment obligations (`obligation_type="payment"`). The execution flow records events and creates approvals. However, promotion is blocked for payment sessions and value adjustments created by approval go to the payment obligation. Whether this execution path has a complete intended lifecycle is not determinable from code alone.

5. **`Obligation.recurrence_interval_days` and `recurrence_count`** — Fields exist on the template model (`backend/contracts/models.py:301–311`). No code path was found that uses these to generate recurring obligation instances.
