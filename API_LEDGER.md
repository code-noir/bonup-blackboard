# API_LEDGER.md — Endpoint Inventory

All endpoints are prefixed with `/api/`. All endpoints require JWT authentication
(`Authorization: Bearer <token>`), set globally via `DEFAULT_PERMISSION_CLASSES`.

Status key:
- **Working** — implemented, no known critical bugs
- **Working*** — implemented, has known issues noted below
- **Stub** — route registered, ViewSet is empty

---

## Auth — `/api/auth/`

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/auth/token/` | Obtain JWT token pair (access + refresh) | Working |
| POST | `/api/auth/token/refresh/` | Refresh access token | Working |
| POST | `/api/auth/token/verify/` | Verify token validity | Working |

---

## Contracts — `/api/contracts/`

Provided by `ContractViewSet` (DefaultRouter) plus manual paths.

### Contract CRUD

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/contracts/` | List all contracts | Working |
| POST | `/api/contracts/` | Create contract | Working |
| GET | `/api/contracts/<id>/` | Retrieve contract | Working |
| PATCH | `/api/contracts/<id>/` | Update contract | Working |
| DELETE | `/api/contracts/<id>/` | Delete contract | Working |

### Contract Obligations

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/contracts/<contract_id>/obligations/` | List obligations for a contract | Working |
| GET | `/api/contracts/<contract_id>/management-summary/` | Management-level summary | Working |

### Obligation Operations (contract-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET/POST | `/api/contracts/obligations/<type>/<id>/execution-sessions/` | List/create execution sessions | Working |
| POST | `/api/contracts/obligations/<type>/<id>/resolve/` | Resolve obligation | Working* |
| POST | `/api/contracts/obligations/payment/<id>/resolve/` | Resolve payment obligation via service | Working* |
| GET/POST | `/api/contracts/obligations/<type>/<id>/approval-requests/` | List/create approval requests | Working |
| GET/POST | `/api/contracts/obligations/<type>/<id>/value-adjustments/` | List/create value adjustments | Working |
| POST | `/api/contracts/obligations/<type>/<id>/proof/` | Submit proof of work | Working |

### Execution Sessions (contract-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/contracts/execution-sessions/<session_id>/` | Session detail | Working |
| POST | `/api/contracts/execution-sessions/<session_id>/execution-items/` | Add execution item | Working |
| GET | `/api/contracts/execution-sessions/<session_id>/events/` | List session events | Working |
| POST | `/api/contracts/execution-sessions/<session_id>/close/` | Close session | Working |

### Execution Events (contract-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/contracts/execution-events/<event_id>/` | Event detail | Working |
| DELETE | `/api/contracts/execution-events/<event_id>/delete/` | Delete event | Working |
| POST | `/api/contracts/execution-events/<execution_event_id>/promote/` | Promote event to side obligation | Working |

### Approval Requests (contract-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/contracts/approval-requests/<approval_id>/approve/` | Approve request | Working |
| POST | `/api/contracts/approval-requests/<approval_id>/reject/` | Reject request | Working |

---

## Obligations — `/api/obligations/`

### Obligation Browsing

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/obligations/` | List all obligations (payment + service) | Working* |
| GET | `/api/obligations/dashboard-summary/` | Cross-contract obligation summary | Working |
| GET | `/api/obligations/<type>/<id>/` | Obligation detail | Working |
| GET | `/api/obligations/<type>/<id>/timeline/` | Obligation timeline | Working |
| GET | `/api/obligations/<type>/<id>/next-actions/` | Recommended next actions | Working |

*No filtering or pagination on list endpoint yet.

### Obligation Lifecycle

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/obligations/<type>/<id>/resolve/` | Resolve obligation — validates state, rejects if terminal | Working |
| POST | `/api/obligations/payment/<id>/resolve/` | Resolve payment obligation | Working |

### Execution Sessions (obligation-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/obligations/<type>/<id>/execution-sessions/` | List sessions | Working |
| GET | `/api/obligations/execution-sessions/<session_id>/` | Session detail | Working |
| POST | `/api/obligations/execution-sessions/<session_id>/close/` | Close session | Working |
| POST | `/api/obligations/execution-sessions/<session_id>/execution-events/` | Add execution event | Working |

### Execution Events (obligation-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/obligations/<type>/<id>/execution-events/` | List events | Working |
| GET | `/api/obligations/execution-events/<event_id>/` | Event detail | Working |
| DELETE | `/api/obligations/execution-events/<event_id>/delete/` | Delete event | Working |
| POST | `/api/obligations/execution-events/<execution_event_id>/promote/` | Promote event | Working |

### Approval Requests (obligation-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET/POST | `/api/obligations/<type>/<id>/approval-requests/` | List/create approval requests | Working |
| POST | `/api/obligations/approval-requests/<approval_id>/approve/` | Approve | Working |
| POST | `/api/obligations/approval-requests/<approval_id>/reject/` | Reject | Working |

### Promotions and Adjustments

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/obligations/<type>/<id>/promotions/` | List promotions | Working |
| GET | `/api/obligations/<type>/<id>/promoted-side-obligations/` | List promoted side obligations | Working |
| GET/POST | `/api/obligations/<type>/<id>/value-adjustments/` | List/create value adjustments | Working |
| POST | `/api/obligations/<type>/<id>/proof/` | Submit proof of work | Working |

---

## Payments — `/api/payments/`

All three list endpoints support:
- Filtering: `?status=`, `?payment_method=`, `?created_after=`, `?created_before=`
- Pagination: `?page=`, `?page_size=` (default 20, max 100) — response shape: `{ count, page, page_size, results }`

All status transition endpoints enforce valid source state and return `409 Conflict` on invalid transitions.

### Payment CRUD

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/payments/` | List all payments (filtered, paginated) | Working |
| POST | `/api/payments/` | Create payment | Working |
| GET | `/api/payments/<payment_id>/` | Payment detail | Working |
| PATCH | `/api/payments/<payment_id>/` | Update payment | Working |
| DELETE | `/api/payments/<payment_id>/` | Delete payment | Working |

### Payment Status Transitions

Valid state machine: `draft → pending → confirmed → refunded / reversed`; `pending → failed / cancelled`; `draft → cancelled`

| Method | Path | Description | Allowed From | Status |
|--------|------|-------------|--------------|--------|
| POST | `/api/payments/<payment_id>/pending/` | Mark pending | `draft` | Working |
| POST | `/api/payments/<payment_id>/confirm/` | Confirm; syncs obligation balance + lifecycle | `pending` | Working |
| POST | `/api/payments/<payment_id>/fail/` | Mark failed | `pending` | Working |
| POST | `/api/payments/<payment_id>/cancel/` | Mark cancelled | `draft`, `pending` | Working |
| POST | `/api/payments/<payment_id>/refund/` | Refund; reverses obligation balance | `confirmed` | Working |
| POST | `/api/payments/<payment_id>/reverse/` | Reverse; reverses obligation balance | `confirmed` | Working |

### Summaries

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/payments/dashboard-summary/` | Global payment totals and counts by status | Working |
| GET | `/api/payments/contracts/<contract_id>/` | Payments for a contract (filtered, paginated) | Working |
| GET | `/api/payments/contracts/<contract_id>/summary/` | Contract payment totals | Working |
| GET | `/api/payments/obligations/<obligation_id>/` | Payments for an obligation (filtered, paginated) | Working |
| GET | `/api/payments/obligations/<obligation_id>/summary/` | Obligation summary: `amount_due`, `amount_paid`, `remaining_balance`, `obligation_state`, payment totals | Working |

---

## Stub Domains

These domains are registered in the router but contain only empty ViewSets.
No business logic exists. All routes return `[]` or DRF defaults.

| Domain | Path | Notes |
|--------|------|-------|
| users | `/api/users/` | No user management endpoints |
| workspace | `/api/workspace/` | No workspace endpoints |
| activity | `/api/activity/` | No activity feed |
| billing | `/api/billing/` | No billing logic |
| documents | `/api/documents/` | No document endpoints |
| notifications | `/api/notifications/` | No notification delivery |
| search | `/api/search/` | No search endpoints |
| sessions | `/api/sessions/` | No session management |
| templates | `/api/templates/` | No template endpoints |
| tools | `/api/tools/` | No tools endpoints |
| uploads | `/api/uploads/` | No upload handling |

---

## Known Issues Across Working Endpoints

- **No ownership checks** — any authenticated user can read or modify any contract, obligation, or payment
- **No filtering or pagination** on obligation list endpoints (done for payments, not yet for obligations)
- **No API tests** — all endpoints are untested at the HTTP level
- **Duplicate URL patterns** in `api/obligations/urls.py` — `approval-request-list` is registered twice; second registration shadows first
