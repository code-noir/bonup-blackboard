# API_LEDGER.md — Endpoint Inventory

All endpoints are prefixed with `/api/`. All endpoints require JWT authentication
(`Authorization: Bearer <token>`), set globally via `DEFAULT_PERMISSION_CLASSES`,
except where noted (public registration, verification, invitation accept).

Status key:
- **Working** — implemented, no known critical bugs
- **Working*** — implemented, has known issues noted below
- **Stub** — route registered, ViewSet is empty

Ownership model: a contract is visible only to its initiator and its counterparty.
Both parties can read and write all obligations and payments on that contract.
All list endpoints are scoped to the authenticated user's contracts.

---

## Auth — `/api/auth/`

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/auth/token/` | Obtain JWT token pair (access + refresh) | Working |
| POST | `/api/auth/token/refresh/` | Refresh access token | Working |
| POST | `/api/auth/token/verify/` | Verify token validity | Working |

---

## Users — `/api/users/`

### Auth & Account

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| POST | `/api/users/register/` | None | Create account; issues email verification token | Working |
| POST | `/api/users/login/` | None | JWT token pair | Working |
| POST | `/api/users/login/refresh/` | None | Refresh access token | Working |
| POST | `/api/users/logout/` | JWT | Blacklist refresh token | Working |
| POST | `/api/users/password-reset/` | None | Request password reset (stateless HMAC token) | Working |
| POST | `/api/users/password-reset/confirm/` | None | Confirm password reset with token | Working |
| POST | `/api/users/verify-email/` | None | Verify email address with UUID token | Working |
| POST | `/api/users/resend-verification/` | JWT | Expire stale token and reissue | Working |

### Profile

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/users/me/` | Get own profile (User + BonUserProfile composite) | Working |
| PATCH | `/api/users/me/` | Update display name / bio | Working |
| POST | `/api/users/me/change-password/` | Change password (requires current password) | Working |
| POST | `/api/users/me/update-email/` | Change email address | Working |
| POST | `/api/users/me/update-phone/` | Update phone number | Working |
| POST | `/api/users/me/update-location/` | Update location | Working |
| GET | `/api/users/me/billing/` | Get billing info | Working |
| PUT | `/api/users/me/billing/` | Update billing info | Working |

### Invitations

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| GET | `/api/users/me/invitations/` | JWT | List sent invitations | Working |
| POST | `/api/users/me/invitations/` | JWT | Send invitation to an email address | Working |
| GET | `/api/users/invitations/<token>/` | None | Get invitation detail by token | Working |
| POST | `/api/users/invitations/<token>/accept/` | None | Accept invitation; marks invited email pre-verified | Working |

### Discovery

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/users/search/?q=` | Search users by name or bonID (icontains) | Working |
| GET | `/api/users/<bon_id>/` | Public profile by bonID | Working |

---

## Contracts — `/api/contracts/`

All endpoints enforce `is_party` — returns 403 if the authenticated user is not
the initiator or the counterparty of the contract.

### Contract CRUD

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/contracts/` | List contracts (scoped to user's contracts) | Working |
| POST | `/api/contracts/` | Create contract (`initiator` forced to `request.user`) | Working |
| GET | `/api/contracts/<id>/` | Retrieve contract | Working |
| PATCH | `/api/contracts/<id>/` | Update contract (blocked if signed version exists) | Working |
| DELETE | `/api/contracts/<id>/` | Delete contract (initiator only) | Working |

### Version Negotiation

| Method | Path | Who | Description | Status |
|--------|------|-----|-------------|--------|
| POST | `/api/contracts/<id>/versions/` | Initiator | Create new version; max 3, 409 at limit | Working |
| POST | `/api/contracts/<id>/versions/<vid>/sign/` | Counterparty | Sign version; locks contract | Working |
| POST | `/api/contracts/<id>/versions/<vid>/reject/` | Counterparty | Reject version | Working |

### Role Switch

| Method | Path | Who | Description | Status |
|--------|------|-----|-------------|--------|
| POST | `/api/contracts/<id>/request-role-switch/` | Counterparty | Request to become initiator; 7-day TTL | Working |
| POST | `/api/contracts/<id>/confirm-role-switch/` | Initiator | Confirm; atomically creates new contract with roles swapped | Working |

### Contract Obligations

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/contracts/<contract_id>/obligations/` | List obligations for a contract | Working |
| GET | `/api/contracts/<contract_id>/management-summary/` | Management-level summary | Working |

### Obligation Operations (contract-scoped)

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET/POST | `/api/contracts/obligations/<type>/<id>/execution-sessions/` | List/create execution sessions | Working |
| POST | `/api/contracts/obligations/<type>/<id>/resolve/` | Resolve obligation | Working |
| POST | `/api/contracts/obligations/payment/<id>/resolve/` | Resolve payment obligation via service | Working |
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

All endpoints enforce `is_party`. List endpoints are scoped to the user's contracts.
`?user_id=` parameter removed. `?role=obligor|obligee` filters against `request.user`.

### Obligation Browsing

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/obligations/` | List obligations (scoped to user's contracts) | Working* |
| GET | `/api/obligations/dashboard-summary/` | Cross-contract obligation summary (scoped) | Working |
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
| POST | `/api/obligations/approval-requests/<approval_id>/approve/` | Approve (only `requested_from` user, or any party) | Working |
| POST | `/api/obligations/approval-requests/<approval_id>/reject/` | Reject (only `requested_from` user, or any party) | Working |

### Promotions and Adjustments

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/obligations/<type>/<id>/promotions/` | List promotions | Working |
| GET | `/api/obligations/<type>/<id>/promoted-side-obligations/` | List promoted side obligations | Working |
| GET/POST | `/api/obligations/<type>/<id>/value-adjustments/` | List/create value adjustments | Working |
| POST | `/api/obligations/<type>/<id>/proof/` | Submit proof of work | Working |

---

## Payments — `/api/payments/`

All endpoints enforce `is_party`. List endpoints are scoped to the user's contracts.
All three list endpoints support:
- Filtering: `?status=`, `?payment_method=`, `?created_after=`, `?created_before=`
- Pagination: `?page=`, `?page_size=` (default 20, max 100) — response shape: `{ count, page, page_size, results }`

All status transition endpoints enforce valid source state and return `409 Conflict` on invalid transitions.

### Payment CRUD

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/payments/` | List payments (scoped to user's contracts, filtered, paginated) | Working |
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

### Summaries and Scoped Lists

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/payments/dashboard-summary/` | Payment totals and counts (scoped to user's contracts) | Working |
| GET | `/api/payments/contracts/<contract_id>/` | Payments for a contract (filtered, paginated) | Working |
| GET | `/api/payments/contracts/<contract_id>/summary/` | Contract payment totals | Working |
| GET | `/api/payments/obligations/<obligation_id>/` | Payments for an obligation (filtered, paginated) | Working |
| GET | `/api/payments/obligations/<obligation_id>/summary/` | Obligation summary: `amount_due`, `amount_paid`, `remaining_balance`, `obligation_state`, payment totals | Working |

---

## Templates — `/api/templates/`

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/templates/` | List all active templates; `?tier=` filter | Working |
| GET | `/api/templates/<id>/` | Template detail with guided fields and clauses | Working |
| POST | `/api/templates/<id>/instantiate/` | Create contract + version + obligations from template; body: `counterparty_email`, `start_date`, `guided_field_values` | Working |

**Template library**: 45 templates seeded across 10 categories (`health_wellness`, `education`, `creative_services`, `technology_services`, `manual_labor`, `freelancer`, `rental`, `financial_services`, `lending`, `barter`).

**Known gaps**:
- `obligation_pattern` is not included in the detail response

---

## Activity — `/api/activity/`

All endpoints enforce ownership — only the authenticated user's contracts are visible.

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/activity/` | List activity across all user's contracts; `?contract_id=`, `?activity_type=`, paginated | Working |
| GET | `/api/contracts/<id>/activity/` | Activity for a specific contract; paginated, ownership enforced | Working |

Write-through hooks fire on all contract, obligation, payment, approval, version, role-switch, and session mutations.

---

## Notifications — `/api/notifications/`

All endpoints scoped to the authenticated user.

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/notifications/` | List user's notifications; `?is_read=true\|false`, paginated | Working |
| GET | `/api/notifications/unread-count/` | `{ unread_count: N }` | Working |
| POST | `/api/notifications/read-all/` | Mark all unread as read; `{ marked_read: N }` | Working |
| POST | `/api/notifications/<id>/read/` | Mark single notification read; 403 if not owner | Working |

Notifications are created automatically via `log_activity()` — every activity event notifies the other contract party via in-app record + email (`send_mail`, `fail_silently=True`).

---

## Sessions — `/api/sessions/`

All endpoints enforce `is_party`. WebSocket requires JWT via `?token=` query param.

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/sessions/` | List sessions across user's contracts; `?contract_id=`, `?status=` | Working |
| POST | `/api/sessions/` | Create session; body: `contract_id`, `version_id?`, `title?`, `scheduled_at?` | Working |
| GET | `/api/sessions/<id>/` | Session detail | Working |
| PATCH | `/api/sessions/<id>/` | Update `title` / `scheduled_at`; 409 if not scheduled | Working |
| POST | `/api/sessions/<id>/cancel/` | Cancel scheduled session; 409 if active/ended | Working |
| POST | `/api/sessions/<id>/join/` | Get LiveKit token; auto-activates scheduled sessions | Working |
| POST | `/api/sessions/<id>/end/` | End session; logs duration; broadcasts `session_ended` to WS group | Working |
| POST | `/api/sessions/<id>/broadcast/` | Initiator pushes contract content to WS group; 403 for counterparty | Working |
| GET | `/api/contracts/<id>/sessions/` | Contract-scoped session list | Working |
| WS | `ws/sessions/<id>/?token=<jwt>` | Real-time contract broadcast; JWT auth, party check, active sessions only | Working |

**Session state machine**: `scheduled → active → ended`; `scheduled → cancelled`. Join auto-transitions `scheduled → active`. Cancel and update are only valid from `scheduled`.

**WebSocket events**:
- Client → server: `{ "type": "editor_update", "content": "..." }` (initiator only)
- Server → client: `{ "type": "editor_update", "content": "...", "sender_id": "..." }`
- Server → client: `{ "type": "session_ended" }` (pushed when `POST /end/` is called; consumer closes)

---

## Stub Domains

These domains are registered in the router but contain only empty ViewSets.
No business logic exists. All routes return `[]` or DRF defaults.

| Domain | Path | Notes |
|--------|------|-------|
| workspace | `/api/workspace/` | No workspace endpoints |
| billing | `/api/billing/` | No billing logic |
| documents | `/api/documents/` | No document endpoints |
| search | `/api/search/` | No search endpoints |
| tools | `/api/tools/` | No tools endpoints |
| uploads | `/api/uploads/` | No upload handling |

---

## Known Issues Across Working Endpoints

- **Duplicate URL patterns** in `api/obligations/urls.py` — `approval-request-list` is registered twice; second registration shadows first
