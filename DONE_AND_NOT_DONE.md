# DONE_AND_NOT_DONE.md — Feature Completion Status

Last updated: 2026-04-01

---

## Complete

These things are implemented, tested, and have no known critical bugs.

### Engine — Core Primitives
- [x] `PaymentObligation` primitive — Decimal payment logic, overpayment cap, `is_past_due()`, `remaining_balance()`
- [x] `ServiceObligation` primitive — `mark_completed()`, lateness adjustment calculation, `was_completed_late()`
- [x] `evaluate_obligation_state()` — pure function, ACTIVE / OVERDUE / DEFAULTED / RESOLVED states
- [x] DEFAULTED state — triggers at 30+ days overdue
- [x] Escalation to BREACHED — `evaluate_default_escalation()` in `escalation.py` (path is now reachable)
- [x] `ObligationScheduler.generate_parallel_schedule()` — installment schedule generation, no crash bugs
- [x] `process_obligation_lifecycle()` — `@transaction.atomic`, single lifecycle processor
- [x] All `datetime.utcnow()` replaced with `timezone.now()` throughout engine and tests

### Engine — Contract Domain
- [x] `Contract` aggregate — `refresh()`, `apply_payment()`, `refresh_state()`, state evaluation from obligations
- [x] `ContractStateMachine` — explicit transition graph
- [x] `ContractVersioning` — version numbering logic
- [x] `ContractService.create_contract()` — schedule generation with correct Decimal coercion
- [x] `ContractActivationService.activate_contract()` — generates and persists obligations
- [x] `LifecycleRunnerService.tick()` — processes candidates, persists state changes

### Engine — Payments
- [x] `PaymentGateway` — abstract interface
- [x] `PaymentResult` — standardised response type
- [x] `MockPaymentGateway` — inherits from `PaymentGateway`, returns `PaymentResult`, matches interface signature
- [x] `PaymentService.process_payment()` — applies payment, runs lifecycle, persists

### Infrastructure
- [x] `ContractRepository` — full implementation
- [x] `ContractVersionRepository` — `get_latest()`, `get_all()`, `get_signed_version()`
- [x] `ContractObligationRepository` — `get_all()`, `list_candidates()`, `update_state()`

### API — Auth
- [x] JWT token issue (`/api/auth/token/`)
- [x] JWT token refresh (`/api/auth/token/refresh/`)
- [x] JWT token verify (`/api/auth/token/verify/`)
- [x] `IsAuthenticated` + `JWTAuthentication` as global defaults

### API — Users
- [x] Register (`POST /api/users/register/`) — creates User + BonUserProfile, issues verification token
- [x] Login (`POST /api/users/login/`) — JWT token pair
- [x] Login refresh (`POST /api/users/login/refresh/`)
- [x] Logout (`POST /api/users/logout/`) — blacklists refresh token
- [x] Password reset request (`POST /api/users/password-reset/`) — stateless HMAC token, no DB model
- [x] Password reset confirm (`POST /api/users/password-reset/confirm/`)
- [x] Email verification (`POST /api/users/verify-email/`) — UUID token on BonUserProfile
- [x] Resend verification (`POST /api/users/resend-verification/`) — expires stale tokens before reissuing
- [x] Get/update my profile (`GET/PATCH /api/users/me/`) — composite User + BonUserProfile
- [x] Change password (`POST /api/users/me/change-password/`)
- [x] Update email (`POST /api/users/me/update-email/`)
- [x] Update phone (`POST /api/users/me/update-phone/`)
- [x] Update location (`POST /api/users/me/update-location/`)
- [x] Billing info (`GET/PUT /api/users/me/billing/`)
- [x] Invitation list/create (`GET/POST /api/users/me/invitations/`)
- [x] Invitation detail (`GET /api/users/invitations/<token>/`)
- [x] Invitation accept (`POST /api/users/invitations/<token>/accept/`) — marks invited email as pre-verified
- [x] User search (`GET /api/users/search/?q=`) — icontains on name and bonID
- [x] Public profile (`GET /api/users/<bon_id>/`)

### API — Contracts
- [x] Contract CRUD (list, create, retrieve, update, delete)
- [x] Contract list scoped to user's contracts (initiator or counterparty)
- [x] Contract create forces `initiator=request.user`
- [x] Signed-lock check on update — rejects PATCH if any signed version exists
- [x] Contract obligations list
- [x] Contract management summary
- [x] Execution session list/create, detail, close, events
- [x] Execution event detail, delete, promote
- [x] Obligation resolve (payment + service)
- [x] Approval request list/create, approve, reject
- [x] Value adjustment list/create
- [x] Proof of work submission
- [x] Version negotiation — create (`POST /api/contracts/<id>/versions/`, initiator only, max 3, 409 on limit)
- [x] Version sign (`POST /api/contracts/<id>/versions/<vid>/sign/`, counterparty only)
- [x] Version reject (`POST /api/contracts/<id>/versions/<vid>/reject/`, counterparty only)
- [x] Role switch request (`POST /api/contracts/<id>/request-role-switch/`, counterparty only, 7-day TTL)
- [x] Role switch confirm (`POST /api/contracts/<id>/confirm-role-switch/`, initiator only, atomic contract swap)
- [x] Ownership guards on all contract sub-views (execution, approval, value adjustment, proof, promotion)

### API — Obligations
- [x] Obligation list filtered to user's contracts — `?user_id=` security hole removed
- [x] `?role=` filter scoped to `request.user` (not an external user_id parameter)
- [x] Dashboard summary filtered to user's contracts
- [x] Obligation detail, timeline, next actions — `is_party` guard on all
- [x] Obligation resolve with state validation (rejects already-resolved and breached)
- [x] Execution session list, detail, close, add event — ownership checked
- [x] Execution event list, detail, delete, promote — ownership checked
- [x] Approval request list/create (per obligation), approve, reject — ownership + `requested_from` guard
- [x] Promotion list, promoted-side-obligation list
- [x] Value adjustment list/create — ownership checked
- [x] Proof of work submission — ownership checked
- [x] All naked `.objects.get()` calls replaced with `get_object_or_404`

### API — Payments
- [x] Payment list/create, detail, update, delete
- [x] Payment list filtered to user's contracts — no global exposure
- [x] Dashboard summary filtered to user's contracts
- [x] Ownership guard (`is_party`) on all payment detail and transition endpoints
- [x] Payment status transition guards — each endpoint enforces valid source state, returns 409 on invalid transition
- [x] `POST /pending/` — draft → pending transition endpoint
- [x] Payment confirm (syncs obligation balance, runs lifecycle engine)
- [x] Payment fail, cancel
- [x] Payment refund (reverses obligation balance)
- [x] Payment reverse (reverses obligation balance)
- [x] Obligation state validation on payment creation — rejects if obligation is resolved/breached/defaulted
- [x] Filtering on all three list endpoints (`?status=`, `?payment_method=`, `?created_after=`, `?created_before=`)
- [x] Pagination on all three list endpoints (`?page=`, `?page_size=`, default 20, max 100)
- [x] Contract-scoped payment list/create (with ownership guard)
- [x] Obligation-scoped payment list/create (with ownership guard)
- [x] Contract summary, obligation summary — ownership guarded
- [x] All mutations wrapped in `transaction.atomic()`

### API — Templates
- [x] Template list (`GET /api/templates/`) — all active templates, `?tier=` filter
- [x] Template detail (`GET /api/templates/<id>/`) — guided fields and clauses included
- [x] Template instantiation (`POST /api/templates/<id>/instantiate/`) — creates contract, version, and obligations from template; `counterparty_email`, `start_date`, `guided_field_values` body
- [x] `TemplateInstantiationService` — resolves guided field values into clause bodies, schedules obligations per obligation pattern, handles `one_time` / `per_session` / `monthly` / `installment` frequency types and `fixed_total` / `deposit_balance` / `installments` / `package_upfront` payment models
- [x] Template library — **45 templates seeded** across 10 categories:

  | Category | Count | Templates |
  |---|---|---|
  | `health_wellness` | 3 | Personal Training, Nutrition Coaching, Wellness Coaching |
  | `education` | 3 | Academic Tutoring, Skills Coaching, Test Prep |
  | `creative_services` | 7 | Photography, Videography, Graphic Design, Beat Production, Recording Session, DJ Performance, Content Collaboration |
  | `technology_services` | 6 | Web Development, Mobile App Development, IT Support, Software Consulting, Cybersecurity, Data Analytics |
  | `manual_labor` | 12 | Lawn Care, Home Cleaning, Home Renovation, Plumbing, Electrical, HVAC, Painting, Moving Services, Handyman, Pest Control, Custom Fabrication, General Repair |
  | `freelancer` | 6 | Content Writing, Social Media Management, Virtual Assistant, Marketing Consulting, Accounting & Bookkeeping, Legal Document Prep |
  | `rental` | 3 | Property Rental, Equipment Rental, Vehicle Rental |
  | `financial_services` | 3 | Tax Services, Financial Planning, Credit Consulting |
  | `lending` | 1 | Personal Loan |
  | `barter` | 1 | Barter Agreement |

### Models
- [x] `ContractTemplate`, `TemplateGuidedField`, `TemplateClause`, `TemplateObligationPattern`
- [x] `Contract`, `ContractVersion`, `ContractObligation`, `ContractServiceObligation`
- [x] `ObligationExecutionSession`, `ObligationExecutionEvent`
- [x] `ContractValueAdjustment`, `ContractApprovalRequest`, `ContractObligationPromotion`
- [x] `ContractRoleSwitchRequest` — pending/confirmed/expired, 7-day TTL, CASCADE on contract delete
- [x] `RequestChange`
- [x] `Payment`
- [x] `BonUserProfile`, `ReservedBonId` (with bonID generation and reservation logic)

### API — Activity
- [x] `ContractActivity` model — UUID pk, contract FK, user FK, activity_type (19 choices), description, metadata JSON, created_at; indexed on `[contract, -created_at]`
- [x] `log_activity()` write-through helper called at every mutation site
- [x] Write-through hooks on: contract create/update, version create/sign/reject, role switch request/confirm, obligation resolve (service + payment), payment create/confirm/fail/cancel/refund/reverse, approval request/grant/reject, session create/cancel/end
- [x] `GET /api/activity/` — paginated, `?contract_id=`, `?activity_type=` filters
- [x] `GET /api/contracts/<id>/activity/` — ownership enforced, paginated

### API — Notifications
- [x] `Notification` model — UUID pk, user FK, notification_type, title, message, is_read (default False), related_contract FK (nullable), metadata JSON, created_at; indexed on `[user, -created_at]` and `[user, is_read]`
- [x] `notify()` helper — creates DB record + calls `send_mail(fail_silently=True)`; integrated into `log_activity()` to notify the other contract party on every event
- [x] `GET /api/notifications/` — paginated, `?is_read=true|false` filter
- [x] `GET /api/notifications/unread-count/` — returns `{ unread_count: N }`
- [x] `POST /api/notifications/read-all/` — marks all user's unread as read
- [x] `POST /api/notifications/<id>/read/` — marks single notification read; 403 if not owner

### API — Sessions (Live Sessions)
- [x] `LiveSession` model — UUID pk, contract FK, version FK (nullable), created_by FK, title, room_name (unique), status (scheduled/active/ended/cancelled), scheduled_at, started_at, ended_at, created_at, updated_at; indexed on `[contract, -created_at]`
- [x] LiveKit token generation via `livekit-api` SDK (`backend/sessions/token.py`)
- [x] `POST /api/sessions/` — create session; logs activity
- [x] `GET /api/sessions/` — list across user's contracts; `?contract_id=`, `?status=` filters
- [x] `GET /api/sessions/<id>/` — detail; ownership enforced
- [x] `PATCH /api/sessions/<id>/` — update title/scheduled_at; 409 if not scheduled
- [x] `POST /api/sessions/<id>/cancel/` — cancel scheduled session; logs activity; 409 if not scheduled
- [x] `POST /api/sessions/<id>/join/` — returns LiveKit token; auto-activates scheduled sessions; 409 if ended/cancelled
- [x] `POST /api/sessions/<id>/end/` — ends session, records duration, logs activity, broadcasts `session_ended` WS event
- [x] `POST /api/sessions/<id>/broadcast/` — initiator pushes contract content to WS group; 403 for counterparty; 409 if not active
- [x] `GET /api/contracts/<id>/sessions/` — contract-scoped list; ownership enforced
- [x] WebSocket `ws/sessions/<id>/?token=<jwt>` — JWT auth, party check, active-only; `editor_update` events from initiator broadcast to all; `session_ended` event closes consumer
- [x] Django Channels 4.3.2 installed; InMemoryChannelLayer configured; ASGI routing wired

### Tests
- [x] 201 tests passing (engine + all API domains)
- [x] No deprecation warnings

### Documentation
- [x] `CLAUDE.md` — project structure, test commands, coding conventions, what not to touch
- [x] `PROJECT_PLAN.md` — bonUP ecosystem, Lifecycle Engine, Blackboard vertical, PBVD definition
- [x] `API_LEDGER.md` — full endpoint inventory with status
- [x] `DOMAIN_MAP.md` — all models, fields, relationships, domain ownership
- [x] `DONE_AND_NOT_DONE.md` — this file
- [x] `AUDIT.md` — full bug registry (BUG-1 through BUG-16), all blockers and high-risk bugs fixed

---

## In Progress / Partially Done

These have a foundation but meaningful gaps remain.

### Contract Lifecycle
- [ ] Grace period — `grace_days` parameter exists in the scheduler but is never stored or evaluated
- [ ] `Obligation` template model — has `recurrence_interval_days` and `recurrence_count` fields but no service expands them into `ContractObligation` instances

### Obligation State Alignment
- [ ] `ContractObligation.state` choices include `"due"` and `"grace"` which the engine never produces (BUG-16)
- [ ] `ContractServiceObligation` missing lateness tracking fields compared to `ServiceObligation` primitive
- [ ] `is_defaulted` on `ContractObligation` is a redundant mirror of `state == "defaulted"` (BUG-15)

### Execution Infrastructure
- [ ] Execution session closure does not enforce single open session per obligation
- [ ] Approval workflow is data-only — approval/rejection has no downstream effect on obligation state
- [ ] Value adjustments are stored but not applied anywhere


---

## Not Started

These domains and features do not exist yet beyond empty stubs.

### API Domains (all stubs)
- [ ] Workspace — team/org management, member roles
- [ ] Billing — billing records, invoices
- [ ] Documents — file attachments on contracts
- [ ] Search — full-text contract/obligation search
- [ ] Tools — (purpose unclear)
- [ ] Uploads — file upload handling

### Core Features Not Yet Built
- [ ] Idempotency key on `Payment` — no duplicate payment protection
- [ ] Real payment gateway integration (only mock exists)
- [ ] Recurrence expansion — `Obligation` template → `ContractObligation` instances
- [ ] Import service — `contracts/services/import_service.py` is empty
- [ ] Change request workflow — `contracts/change_request.py` is a 4-line stub with no logic
- [ ] Audit logging — no record of who changed what
- [ ] API-layer tests — zero test coverage on all HTTP endpoints
- [ ] DB-level constraint `amount_paid <= amount_due` on `ContractObligation`
- [ ] Proof of work verification — events are stored but no verification logic exists

### Infrastructure Not Yet Built
- [ ] `ContractServiceObligationRepository` — no concrete implementation
- [ ] `PaymentRepository` — no repository pattern for payments
- [ ] Background task queue — `automation/tasks.py` references Celery-style tasks but nothing is wired

---

## Known Remaining Bugs (medium severity)

| ID | Description | Status |
|----|-------------|--------|
| BUG-15 | `is_defaulted` flag duplicates `state == "defaulted"` | Open |
| BUG-16 | Model state choices include states the engine never produces (`due`, `grace`) | Open |

All blockers (BUG-1 through BUG-7) and high-risk bugs (BUG-8 through BUG-14) are fixed.
