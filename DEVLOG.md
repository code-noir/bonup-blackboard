# bonUP Blackboard — Development Log

---

## 2026-04-02

**Session summary:** Completed Live Session domain, built NegotiationPrep, built full Billing domain with feature gates and free trial logic.

### Test count
| Point | Tests passing |
|---|---|
| Start of session | 278 |
| End of session | 355 |
| Net added | +77 |

### Commits (oldest → newest)

| Hash | Description |
|---|---|
| `b066090` | refactor: make LiveSession.contract nullable (SET\_NULL, future-proof for Studio) |
| `aee10c0` | feat: complete Live Session domain with WS broadcast, PATCH, cancel, broadcast |
| `0c05962` | feat: slide/presentation WS events + NegotiationPrep domain |
| `ed44fac` | feat: build Billing domain — plans, subscriptions, feature gates, wired to contracts/sessions/templates |
| `cd3f00b` | fix: update professional plan — all\_templates True, no excluded categories |
| `73f56f2` | feat: free trial on registration — business tier, 1 contract, auto-expires to no\_subscription |

---

### Domains built / completed

#### Live Session (completed)
- `PATCH /api/sessions/<id>/` — update title / scheduled\_at on scheduled sessions
- `POST /api/sessions/<id>/cancel/` — cancel a scheduled session (409 if already active/ended)
- `POST /api/sessions/<id>/broadcast/` — initiator-only HTTP broadcast to channel layer
- WebSocket consumer at `ws/sessions/<id>/` — JWT auth via `?token=` query param
  - Events: `editor_update` (initiator only), `slide_update` (either party), `presentation_control` (initiator only, closes non-initiator with 4004)
  - Outbound: `session_ended` broadcast from end endpoint
- `presentation_controller` field added to `LiveSession` model
- `LiveSession.contract` made nullable (`SET_NULL`) — future-proofs schema for Studio (contract-free sessions)
- Django Channels 4.3.2 + Daphne 4.2.1 installed; `InMemoryChannelLayer` wired in settings; `ProtocolTypeRouter` in `asgi.py`
- 15 WebSocket consumer tests (TransactionTestCase), 6 update tests, 7 cancel tests, 5 broadcast tests

#### NegotiationPrep (new)
- Models: `PrepSession`, `PrepDocument`, `PrepNote` in `backend/negotiation_prep/`
- 10 API endpoints under `/api/prep/`:
  - `GET/POST /api/prep/` — list / create prep session
  - `GET/PATCH/DELETE /api/prep/<id>/` — detail, update, delete
  - `POST /api/prep/<id>/documents/` — attach document (title, file\_url, file\_type)
  - `DELETE /api/prep/<id>/documents/<doc_id>/` — remove document
  - `POST /api/prep/<id>/notes/` — add ordered note
  - `PATCH/DELETE /api/prep/<id>/notes/<note_id>/` — update or delete note
- Privacy model: owner-only (returns 404 not 403 to non-owners)
- Both parties of a contract may create independent prep sessions linked to the same live session
- 48 tests

#### Billing (new)
- Models: `SubscriptionPlan`, `UserSubscription`, `Invoice` in `backend/billing/`
- 5 plans seeded via data migration:

  | Slug | Price | Max contracts | Sessions/mo | AI tier | Notes |
  |---|---|---|---|---|---|
  | per\_contract | $15 one-time | 1 | 0 | none | No lifecycle/notifications |
  | starter | $10/mo or $100/yr | 3 | 1 | none | |
  | professional | $83/mo | unlimited | 20 | basic | all templates |
  | business | $200/mo | unlimited | 60 | advanced | all templates |
  | anchor | $600/mo | unlimited | unlimited | full | priority support, early access |

- `backend/billing/gates.py` — feature gate helpers:
  - `can_create_contract(user)` — checks trial limit then plan limit
  - `can_create_session(user)` — checks monthly session limit
  - `can_access_template(user, template)` — enforces excluded\_categories
  - `get_ai_tier(user)`, `has_feature(user, feature_name)`
  - `increment_contracts_used(user)`, `increment_sessions_used(user)`
- Gates wired into existing endpoints:
  - `POST /api/contracts/` → 403 with upgrade message if contract limit reached
  - `POST /api/sessions/` → 403 if session limit reached or plan excludes sessions
  - `GET /api/templates/` → filters inaccessible templates from list
  - `GET /api/templates/<id>/` → 403 if template not accessible
- 7 billing API endpoints:
  - `GET /api/billing/plans/` — all active plans
  - `GET/POST/DELETE /api/billing/subscription/` — create, change, cancel
  - `GET /api/billing/invoices/` — paginated invoice list
  - `GET /api/billing/usage/` — current period usage vs limits
  - `GET /api/billing/trial/` — trial status and contracts remaining
- Free trial on registration:
  - `RegisterAPIView` calls `start_trial(user)` on every new registration
  - Trial: business tier, `status=trialing`, `trial_contracts_remaining=1`
  - `consume_trial_contract(user)` called after each contract creation
  - When counter hits 0: status transitions `trialing → no_subscription`
  - `no_subscription` is blocked by all gates
- 77 billing tests (61 original + 16 trial tests)

---

### Platform status as of end of session

| Domain | Status | Endpoints |
|---|---|---|
| Auth (JWT) | Complete | 3 |
| Users | Complete | 22 |
| Contracts | Complete | 28 |
| Obligations | Complete | 22 |
| Payments | Complete | 18 |
| Templates | Complete | 3 |
| Activity | Complete | 2 |
| Notifications | Complete | 4 |
| Sessions (Live) | Complete | 8 + 1 WS |
| NegotiationPrep | Complete | 10 |
| Billing | Complete | 7 |
| Documents | Stub | 5 |
| Search | Stub | 5 |
| Tools | Stub | 5 |
| Uploads | Stub | 5 |
| Workspace | Stub | 5 |
| **Total HTTP** | | **172** |

**Test suite:** 355 tests, 0 failures.

**Stack:** Django 6.0.2 · DRF 3.16.1 · Django Channels 4.3.2 · Daphne 4.2.1 · Python 3.12 · PostgreSQL (prod) / SQLite (dev)

**Open:** Stripe payment processing (billing stubs wired, no charges yet). Studio (contract-free live sessions). Document upload, search, tools, workspace domains.
