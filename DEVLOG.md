# bonUP Blackboard — Development Log

---

## 2026-04-04

**Session summary:** Built Uploads, Documents, Search (all 9 domains), AI Assistant (chat + 3 contract tools), Sol rotating savings group domain with PDF exports, injected Sol data into AI context, added i18n support and language preference endpoint.

### Test count
| Point | Tests passing |
|---|---|
| Start of session | 355 |
| End of session | 627 |
| Net added | +272 |

### Commits (oldest → newest)

| Hash | Description |
|---|---|
| `e00d257` | feat: build Uploads domain — Digital Ocean Spaces storage + Upload model + API |
| `0cb860b` | feat: build Documents domain — ContractDocument model + contract-scoped API |
| `9671508` | feat: add is\_draft\_document to Upload — field, filter, serializer |
| `eb11b7f` | feat: build Search domain — global, contract, and template search endpoints |
| `8a2e25e` | feat: expand Search domain to all 9 data domains + 4 scoped endpoints |
| `2578097` | feat: build AI Assistant domain — chat, context injection, action execution |
| `3a3caf7` | fix: raise template context cap 20→50 and wire dotenv on startup |
| `0d9ddb8` | feat: add i18n (7 languages), currency expansion, and language preference endpoint |
| `aa5dafb` | feat: build Sol (sou-sou/tontine) rotating savings group domain |
| `30fac90` | feat: add PDF export endpoints for Sol domain (reportlab) |
| `e9e570c` | feat: inject Sol data into AI context; expand Search domain with Sol |
| `cc7df7c` | feat: add AI contract analysis, counter-drafting, and import endpoints |
| `c296be1` | fix: open analyze-contract to all active subscribers |

---

### Domains built / completed

#### Uploads (new)
- `Upload` model: UUID pk, user FK, file_url, file_name, file_type, file_size, storage_key, related_contract FK, related_session FK, is_prep_material, is_draft_document
- Storage: Django `default_storage` pointed at Digital Ocean Spaces; key path `uploads/{user_id}/{uuid}/{filename}`
- `GET /api/uploads/` — list user's uploads; `?contract_id=`, `?session_id=`, `?is_draft_document=` filters
- `POST /api/uploads/` — multipart file upload to Spaces, creates Upload record
- `DELETE /api/uploads/<id>/` — removes record and Spaces object

#### Documents (new)
- `ContractDocument` model: UUID pk, contract FK, uploaded_by FK, title, file_url, file_type, description, created_at
- Full CRUD ViewSet under `/api/documents/`; ownership enforced (contract parties only)

#### Search (new — 8 endpoints)
- `GET /api/search/?q=` — global search returning top 10 per domain across contracts, obligations, payments, sessions, documents, templates, users, Sol groups
- 7 domain-specific endpoints (`/contracts/`, `/obligations/`, `/payments/`, `/sessions/`, `/documents/`, `/templates/`, `/sol/`) with per-domain filters
- Global `users` results include SolMember name/email/phone lookup across requesting user's managed Sol groups (tagged `source: "sol_member"`)
- All results scoped to requesting user's data

#### AI Assistant (new — 6 endpoints)
- `AIConversation` model: messages stored as JSONField list of `{role, content}` dicts
- `POST /api/ai/chat/` — multi-turn chat; three tier prompts (basic/advanced/full); builds user context from live DB state; full tier parses and executes action blocks (`create_contract`, `instantiate_template`)
- `GET /api/ai/conversations/`, `GET /api/ai/conversations/<id>/` — history browsing
- `POST /api/ai/analyze-contract/` — upload or reference PDF; returns summary, key_terms, red_flags, questions; any active subscriber
- `POST /api/ai/counter-contract/` — returns concerning_clauses with counter language, negotiation_strategy (push_on / concede), revised_contract; Business/Anchor only
- `POST /api/ai/import-contract/` — extracts parties, contract type, payment + service obligations from PDF; atomically creates Contract + obligations; Anchor only
- PDF text extraction via pdfplumber; all endpoints accept `file` (multipart) or `upload_id`
- User context injection covers identity, subscription, active contracts, obligations due in 7 days, available templates, Sol groups managed, Sol memberships

#### i18n + Currency (additions to Users domain)
- Django `LocaleMiddleware` wired; `LANGUAGES` extended to 7: English, French, Spanish, Haitian Creole, Portuguese, Swahili, Chinese
- `POST /api/users/me/language/` — updates `BonUserProfile.preferred_language`; `Accept-Language` header also respected

#### Sol — Rotating Savings Group (new — 20 endpoints)
- Models: `Sol`, `SolMember`, `SolContract`, `SolPayout`, `SolContribution`, `SolNote`, `SolTip`
- Manager CRUD: create/list/detail/update Sol groups
- Member management: add/remove members (bonUP users or off-platform by email), generate participation contracts
- Payout scheduling: list/create/update payouts; rearrange payout order with reason tracking (`was_rearranged`, `rearranged_reason`, `original_recipient`, `rearranged_by`)
- Contribution tracking: mark contributions paid/pending per payout cycle
- Dashboard, notes, tips
- PDF exports via reportlab:
  - Manager export: full group ledger (members, payout schedule, contribution history, rearrangements, tips, notes)
  - Member export: personal record (participation contract, own contribution history, upcoming payout date)
- Sol creation gated to `plan.has_sol=True` (Business/Anchor); joining open to any active subscriber
- Sol context injected into AI system prompt: manager sees payout recipient + paid/pending contributions; member sees own payout schedule + contribution status

---

### Platform status as of end of session

| Domain | Status | Endpoints |
|---|---|---|
| Auth (JWT) | Complete | 3 |
| Users | Complete | 23 |
| Contracts | Complete | 28 |
| Obligations | Complete | 22 |
| Payments | Complete | 18 |
| Templates | Complete | 3 |
| Activity | Complete | 2 |
| Notifications | Complete | 4 |
| Sessions (Live) | Complete | 8 + 1 WS |
| NegotiationPrep | Complete | 10 |
| Billing | Complete | 7 |
| Uploads | Complete | 3 |
| Documents | Complete | 5 |
| Search | Complete | 8 |
| AI Assistant | Complete | 6 |
| Sol | Complete | 20 |
| Tools | Stub | — |
| Workspace | Stub | — |
| **Total HTTP** | | **170 + 1 WS** |

**Test suite:** 627 tests, 0 failures.

**Stack:** Django 6.0.2 · DRF 3.16.1 · Django Channels 4.3.2 · Daphne 4.2.1 · Python 3.12 · pdfplumber · reportlab · PostgreSQL (prod) / SQLite (dev)

**Open:** Stripe payment processing. Studio (contract-free live sessions). Workspace / tools domains. Engine-level import service and change request workflow. Grace period + recurrence expansion.

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
