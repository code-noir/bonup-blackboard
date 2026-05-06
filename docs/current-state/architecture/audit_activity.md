# Audit / Activity Log Architecture

> Status: Generated from code
> Source of truth: current code first, docs second
> Generated: 2026-05-06

---

## 1. Overview

The activity log domain provides a contract-scoped audit trail. Every mutation that changes meaningful contract state — creation, versioning, role switches, obligation resolution, payment events, approval decisions, session completion — writes a `ContractActivity` row via the `log_activity()` helper in `backend/activity/log.py`. The helper also fires a notification to the other contract party as a side effect. Two read-only API endpoints expose the log to authenticated parties. There is no background processing, no admin interface, and no middleware involved. This domain is entirely separate from `ContractProOversightEvent` (`backend/contract_pro/models.py:268`), which is a distinct model in the contract-pro app and is not written via `log_activity`.

---

## 2. Models

### 2.1 ContractActivity

**File:** `backend/activity/models.py:13`

One model only. One row per auditable event on a `Contract`.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4, editable=False)` | |
| `contract` | `ForeignKey(Contract, on_delete=CASCADE, related_name="activity_log")` | Required; row is deleted if contract is deleted |
| `user` | `ForeignKey(User, null=True, blank=True, on_delete=SET_NULL, related_name="activity_events")` | `None` for automated events; preserved as null if user is deleted |
| `activity_type` | `CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES)` | See type table below |
| `description` | `TextField` | Human-readable summary |
| `metadata` | `JSONField(default=dict, blank=True)` | Supplementary data; shape varies by call site |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Meta:** `ordering = ["-created_at"]`; DB index on `(contract, -created_at)` (`models.py:64–66`)

**Activity type choices** (`models.py:15–42`):

| Value | Label | Used at call sites? |
|---|---|---|
| `contract_created` | Contract Created | Yes |
| `contract_updated` | Contract Updated | **No** — defined but never passed to `log_activity` |
| `version_created` | Version Created | Yes |
| `version_signed` | Version Signed | Yes |
| `version_rejected` | Version Rejected | Yes |
| `role_switch_requested` | Role Switch Requested | Yes |
| `role_switch_confirmed` | Role Switch Confirmed | Yes |
| `obligation_resolved` | Obligation Resolved | Yes |
| `payment_obligation_resolved` | Payment Obligation Resolved | Yes |
| `payment_created` | Payment Created | Yes |
| `payment_confirmed` | Payment Confirmed | Yes |
| `payment_failed` | Payment Failed | Yes |
| `payment_cancelled` | Payment Cancelled | Yes |
| `payment_refunded` | Payment Refunded | Yes |
| `payment_reversed` | Payment Reversed | Yes |
| `approval_requested` | Approval Requested | Yes |
| `approval_granted` | Approval Granted | Yes |
| `approval_rejected` | Approval Rejected | Yes |
| `session_held` | Session Held | Yes (model comment: "reserved for future Sessions domain") |

18 of 19 defined types are used at call sites. `contract_updated` is defined but has no call site anywhere in the codebase.

**Distinction from ContractProOversightEvent:** `ContractProOversightEvent` is defined at `backend/contract_pro/models.py:268`. It is a separate model in the `contract_pro` app, written by contract-pro–specific logic, and has no relationship to `ContractActivity`. `log_activity` never writes to it. The two systems do not share a base class or common interface.

---

## 3. Core Concepts

### 3.1 The write path is a single helper

All writes go through `log_activity()` at `backend/activity/log.py:35`. No domain writes to `ContractActivity` directly. No signals, no middleware, no celery tasks.

### 3.2 Notification side-effect

Every `log_activity()` call attempts to notify the other contract party via `backend.notifications.notify.notify()` (`log.py:61–68`). The notification call is:
- Wrapped in `try/except Exception: pass` — failures are silently swallowed (`log.py:58–70`).
- Skipped if `user` is `None` or the other party has no registered account.

A broken notification backend will not surface errors to the caller and will not prevent the activity row from being written.

### 3.3 No atomicity guarantee

`log_activity()` is deliberately **not** wrapped in `transaction.atomic()` (`log.py:8`). Callers that require the activity row and their own mutation to commit together must wrap both in their own `transaction.atomic()`.

### 3.4 Scoped to contracts

`ContractActivity` has a required FK to `Contract`. There is no user-level activity log, no system-level audit log, and no activity record type that exists without a contract. All read access is party-scoped — only users who are an initiator or counterparty on a contract can see its activity.

---

## 4. log_activity Helper

**File:** `backend/activity/log.py:35`

**Signature:**
```python
def log_activity(contract, user, activity_type, description, metadata=None)
```

**What it does:**
1. Calls `ContractActivity.objects.create(...)` with all arguments. `metadata` defaults to `{}` if `None`.
2. Calls `_get_other_party(contract, user)` (`log.py:13`) to find the other party's `User` object. Logic: if `user` is the initiator, looks up counterparty by `contract.counterparty_email`; if `user` is the counterparty, returns `contract.initiator`. Returns `None` if `user` is `None` or the other party has no account.
3. If a recipient is found, calls `backend.notifications.notify.notify(user=recipient, notification_type=activity_type, message=description, related_contract=contract, metadata=metadata)`.
4. Any exception in steps 2–3 is caught and discarded.

---

## 5. API Routes

Registered at `backend/api/router.py:8` (`activity/` prefix) and `backend/api/contracts/urls.py:136`. Default permission is `IsAuthenticated` (DRF project default) for both.

### Route 1 — `GET /api/activity/`

| | |
|---|---|
| **View** | `ActivityListAPIView.get` (`backend/api/activity/views.py:66`) |
| **Permission** | `IsAuthenticated` |
| **Party filter** | `contract__initiator=user OR contract__counterparty_email=user.email` (`views.py:50`) |
| **What it does** | Returns all `ContractActivity` rows for the authenticated user's contracts, paginated. |
| **Query params** | `?contract_id=<uuid>` narrow to one contract; `?activity_type=<type>` filter by type; `?page=<int>` (default 1); `?page_size=<int>` (default 20, max 100) |
| **Response shape** | `{count, page, page_size, results[]}` where each result is `{id, contract_id, user_id, activity_type, description, metadata, created_at}` |
| **State transitions** | None |

### Route 2 — `GET /api/contracts/<contract_id>/activity/`

| | |
|---|---|
| **View** | `ContractActivityAPIView.get` (`backend/api/activity/views.py:87`) |
| **Registration** | `backend/api/contracts/urls.py:136–138` |
| **Permission** | `IsAuthenticated` + `is_party` check from `backend.api.contracts.permissions` (`views.py:89`) |
| **What it does** | Returns `ContractActivity` rows for a specific contract. Returns 403-equivalent via `contract_party_response()` if the caller is not a party. |
| **Query params** | `?page=`, `?page_size=` (same limits as Route 1) |
| **Response shape** | Same `{count, page, page_size, results[]}` shape |
| **State transitions** | None |

---

## 6. Call Sites

25 production call sites across 8 files in 4 domains. Test call sites in `backend/api/tests/test_notifications.py` are excluded.

### Contracts domain — `backend/api/contracts/`

| File | Line | `activity_type` |
|---|---|---|
| `viewsets/contract_viewset.py` | 49 | `"contract_created"` |
| `version_views.py` | 119 | `"version_created"` |
| `version_views.py` | 185 | `"version_signed"` |
| `version_views.py` | 241 | `"version_rejected"` |
| `approval_views.py` | 105 | `"approval_requested"` |
| `approval_views.py` | 165 | `"approval_granted"` |
| `approval_views.py` | 222 | `"approval_rejected"` |
| `resolve_views.py` | 42 | `"obligation_resolved"` |
| `resolve_views.py` | 95 | `"payment_obligation_resolved"` |
| `role_switch_views.py` | 76 | `"role_switch_requested"` |
| `role_switch_views.py` | 188 | `"role_switch_confirmed"` |

### Obligations domain — `backend/api/obligations/views.py`

| Line | `activity_type` |
|---|---|
| 593 | `"obligation_resolved"` |
| 641 | `"payment_obligation_resolved"` |
| 1022 | `"approval_requested"` |
| 1073 | `"approval_granted"` |
| 1123 | `"approval_rejected"` |

### Payments domain — `backend/api/payments/views.py`

| Line | `activity_type` |
|---|---|
| 144 | `"payment_created"` |
| 259 | `"payment_confirmed"` |
| 313 | `"payment_failed"` |
| 344 | `"payment_cancelled"` |
| 392 | `"payment_refunded"` |
| 440 | `"payment_reversed"` |

### Sessions domain — `backend/api/sessions/views.py`

| Line | `activity_type` |
|---|---|
| 117 | `"session_held"` |
| 198 | `"session_held"` |
| 288 | `"session_held"` |

`session_held` is called three times. The model comment at `models.py:40` labels it "reserved for future Sessions domain" — it is now active.

---

## 7. Authority / Access Rules

- Both API routes require `IsAuthenticated` (DRF project default).
- `ActivityListAPIView` enforces a party filter at the queryset level — rows from contracts the user is not a party to are never returned.
- `ContractActivityAPIView` enforces `is_party` from `backend.api.contracts.permissions` before querying. Non-parties receive a 403-equivalent response.
- No role distinction (no admin-only or staff-only read path).
- No Django admin registration for `ContractActivity` was found in the codebase.
- No management command or queryset utility exposes activity data outside the API.

---

## 8. Relationship to Other Domains

### Notifications (`backend/notifications/`)

`log_activity` calls `backend.notifications.notify.notify()` as a side effect on every write. The `activity_type` string is passed directly as `notification_type`. A failure in the notifications system does not affect the activity record write.

### Contracts (`backend/contracts/`, `backend/api/contracts/`)

`ContractActivity.contract` is a required FK. The contracts app is the structural dependency of this domain. `ContractActivityAPIView` is registered within the contracts URL namespace and uses contracts party-check permissions.

### Obligations, Payments, Sessions

These domains call `log_activity` but do not own or extend the activity model. They are consumers of the write helper only.

### Contract Pro (`backend/contract_pro/`)

`ContractProOversightEvent` (`contract_pro/models.py:268`) is a separate model. It is not written via `log_activity`, does not share a table or base class with `ContractActivity`, and is documented separately. The two systems have no code relationship.

---

## 9. Current Gaps

1. **`contract_updated` is never used.** Defined in `ACTIVITY_TYPE_CHOICES` (`models.py:22`) but no call site in the codebase passes it to `log_activity`. Whether it is intended for a future update-event path or is an oversight is not established in code.

2. **`backend/api/activity/serializers.py` is a mislabeled dead file.** The file exists at `backend/api/activity/serializers.py` but its header comment reads `# backend/api/contracts/serializers.py` and it contains `ContractSerializer`. It is not imported anywhere in the codebase. The views serialize inline using `_serialize()` at `views.py:37`. This file appears to be a stale copy-paste artifact.

3. **Notification failures are silently discarded.** The bare `except Exception: pass` at `log.py:58–70` means a broken notification backend produces no error, no log entry, and no observable signal. There is no dead-letter queue, retry, or alerting.

4. **No atomicity enforcement at the helper level.** Callers that do not wrap `log_activity` in their own `transaction.atomic()` may produce orphaned activity records if the surrounding mutation rolls back. Whether each of the 25 call sites handles this is not verified here.

5. **`session_held` fires three times in `sessions/views.py`** (lines 117, 198, 288). Whether these represent three distinct session-completion paths or a duplication is not established without reading the surrounding view logic in detail.

6. ### User-facing activity API endpoints have no frontend consumer

   `GET /api/activity/` (`backend/api/activity/views.py:66`) and
   `GET /api/contracts/<contract_id>/activity/` (`backend/api/activity/views.py:87`)
   are wired and functional but no frontend code calls them. A repo-wide
   search of `frontend/src/` for these endpoints returned zero matches.
   The admin panel uses a separate `/admin/activity/` endpoint via
   `AdminActivity.tsx`, not these routes.

   Note: `frontend/src/pages/CreateContract.tsx:131` defines a static
   hardcoded `ACTIVITY` array used by an in-editor "Activity Feed" panel.
   This is a placeholder — it is not connected to `ContractActivity` and
   makes no API calls. The file header at `CreateContract.tsx:13`
   acknowledges this as a known issue.

---

## 10. Open Questions

1. **Why is `contract_updated` defined but unused?** Was it intended for a contract-edit endpoint that was never built, or is it genuinely reserved?

2. **Do any of the 25 call sites lack `transaction.atomic()` wrapping?** Given the no-atomicity contract in `log.py`, it is worth confirming which call sites are safe and which could produce orphaned activity rows on rollback.

3. **`session_held` at three call sites** — are these three different outcomes in the sessions flow mapped to the same type, or should they eventually be distinct types?

---

## 11. Update Rule

Update this file when code changes `ContractActivity`, `log_activity`, the activity API views, or when new `log_activity` call sites are added or removed in any domain.
