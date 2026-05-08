# Tech Debt Register

> Generated: 2026-05-07
> Source of truth: code first, this document second

---

## 1. Overview

This file consolidates known gaps, bugs, and deferred work across the bonUP Blackboard backend into one triage document. It was generated on 2026-05-07 from the twelve domain architecture files under `docs/current-state/architecture/` (identity, entity_layer, authority, contract_lifecycle, contract_pro, obligations_lifecycle, payments, billing, audit_activity, documents_uploads, sessions, sol) and from the 2026-05-06 worklog entries in `docs/work/2026/May/05/WORKLOG.md`. Severity ratings are opinionated by Project Claude; reasonable engineers may re-classify individual items. Every item cites the architecture file or worklog section where it was first surfaced so the original evidence is traceable.

---

## 2. Severity Legend

| Level | Definition |
|---|---|
| **Critical** | Security, data integrity, or correctness issue that can damage user data, leak access, or corrupt state. Fix before production launch. |
| **High** | Production-readiness issue that will fail or behave incorrectly under real load or in a multi-process deployment. Fix during pre-launch hardening. |
| **Medium** | Quality issue or unwired feature that doesn't block launch but causes drift, confusion, or wasted code. Fix when touching that domain next. |
| **Low** | Naming, cleanup, dead code, documentation drift. Address when convenient. |

---

## 3. Critical

### C1 — /api/users/login/ bypasses email_verified gate

The system exposes two login endpoints. `/api/auth/token/` enforces `email_verified = True` before issuing a JWT. `/api/users/login/` is unmodified SimpleJWT and issues tokens to any user regardless of verification status. A user who registers but never completes email verification can authenticate through the second endpoint and access the full API.

**Source:** `identity.md §7`  
**Why Critical:** Verification bypass is a security control failure that allows unverified accounts to act as authenticated users.

---

### C2 — PATCH /api/payments/\<id\>/ bypasses state machine

`PaymentDetailAPIView.patch()` accepts a partial update via `PaymentSerializer` with `partial=True`. The `status` field is not in `read_only_fields`, so a PATCH request can set `status` to any value — e.g., directly from `draft` to `confirmed` — without going through the `ALLOWED_FROM` transition checks enforced by the dedicated action endpoints (`/pending/`, `/confirm/`, etc.). No `amount_paid` recompute or `process_obligation_lifecycle()` call occurs on this path.

**Source:** `payments.md §7`, citing `backend/api/payments/views.py:170` and `backend/api/payments/serializers.py:32`  
**Why Critical:** Corrupts payment state and obligation `amount_paid` without going through the designed state machine, enabling incorrect financial state.

---

### C3 — DELETE /api/payments/\<id\>/ leaves amount_paid inflated

`PaymentDetailAPIView.delete()` deletes the payment row and returns 204 with no further side effects. If the deleted payment was in `confirmed` status and was linked to a `ContractObligation`, `amount_paid` on that obligation will remain inflated — it is computed as the sum of confirmed payments and is not recomputed after deletion. The obligation's financial record becomes incorrect without any observable signal.

**Source:** `payments.md §7`, citing `backend/api/payments/views.py:184`  
**Why Critical:** Silent data integrity corruption: the obligation reflects paid amounts that no longer exist in the payments table.

---

### C4 — SQLite hardcoded in settings (was supposed to be Postgres)

The Django `DATABASES` setting is configured to use SQLite rather than PostgreSQL. The worklog notes this was silently substituted by an AI agent. SQLite has critical limitations for production: `select_for_update()` — used by `PaymentConfirmAPIView`, `PaymentRefundAPIView`, and `PaymentReverseAPIView` to protect concurrent `amount_paid` recomputes — is effectively a no-op under SQLite's locking model, silently removing the concurrency protection on those payment flows.

**Source:** `docs/work/2026/May/05/WORKLOG.md` (2026-05-06 findings)  
**Why Critical:** The wrong database engine is active; all concurrency guarantees in the payment domain are silently absent, and the production storage target is wrong.

---

### C5 — log_activity silently discards notification failures with no observability

`log_activity()` in `backend/activity/log.py:58–70` wraps the notification side-effect call in a bare `except Exception: pass`. A broken notification backend — misconfigured SMTP, failed push delivery, exceptions in `notify()` — produces no error, no log entry, no alert, and no dead-letter queue. The caller has no way to know notifications were dropped. There is no retry, no counter, and no circuit breaker.

**Source:** `audit_activity.md §9`, citing `backend/activity/log.py:58–70`  
**Why Critical:** A broken notification system fails silently in production with no operational observability, violating the requirement that production failures must be detectable.

---

### C6 — ImportContractView writes contract before checking billing gate; failed gate does not block the write

`ImportContractView.post()` creates `Contract`, `ContractVersion`, and obligations inside a `transaction.atomic()` block, then commits. After the commit, `can_create_contract(request.user)` is called. If the gate returns `(False, _)`, the code only skips the usage counter increment — the contract is already written to the database and is not rolled back or deleted. A user whose plan does not allow another contract can use the import endpoint to create one anyway; the only consequence is that `contracts_used_this_period` is not incremented, which silently desyncs the usage counter from actual contract count.

**Source:** `ai.md §10`, citing `backend/api/ai/views.py:643–727` (atomic block at 643; gate check at 723–727)

**Why Critical:** Plan-limit bypass on a paid feature. Users on plans that should block contract creation can create contracts through the AI import path. Usage counter desync also breaks any downstream metering or billing logic that depends on `contracts_used_this_period`.

---

## 4. High

### H1 — InMemoryChannelLayer breaks WebSocket broadcasts in multi-process deployment

`CHANNEL_LAYERS` is configured as Django Channels' `InMemoryChannelLayer` (`backend/core/settings.py:176–180`). This channel layer is in-process only: WebSocket broadcasts from HTTP views via `_broadcast_to_group` (`backend/api/sessions/views.py:45–53`) will not reach clients connected to a different worker process. In any deployment running more than one Gunicorn/Daphne worker — the standard production configuration — the `session.ended`, `editor_update`, and `presentation_control` events will silently fail to reach most connected clients.

**Source:** `sessions.md §11`  
**Why High:** Multi-process deployment is the default for production; this configuration makes the real-time session feature non-functional at scale.

---

### H2 — LiveKit join token has no explicit TTL

`generate_token()` in `backend/sessions/token.py:10` creates a LiveKit `AccessToken` without calling `.with_ttl()` or any equivalent TTL setter. The token lifetime defaults to whatever the LiveKit SDK default is — not established in the code. A long-lived or indefinitely-valid token issued to a user who later loses party status, or whose session is cancelled, remains usable until the LiveKit server rejects it.

**Source:** `sessions.md §11`, citing `backend/sessions/token.py:10`  
**Why High:** Production security concern: tokens must expire to limit abuse window and enforce session boundaries.

---

### H3 — No file size limit on uploads

`UploadsViewSet.create` reads `file.size` and stores it in the `Upload` row but never checks it against a maximum (`uploads/views.py:78`). There is no `MAX_UPLOAD_SIZE` setting. Any file of any size is accepted and written to S3 via `default_storage.save()`. This exposes the system to accidental or malicious large-file uploads that consume storage and transfer bandwidth without bound.

**Source:** `documents_uploads.md §9`, citing `backend/api/uploads/views.py:78`  
**Why High:** Resource exhaustion attack vector in production.

---

### H4 — No MIME type or magic byte validation on uploads

`file_type` is a client-supplied string validated only against the set `{"pdf", "image", "video", "slides", "document"}` at `uploads/views.py:56–60`. The backend does not inspect the `Content-Type` header, read magic bytes, or verify actual file content. The AI domain at `ai/views.py:446–449` gates further processing on `upload.file_type == "pdf"` but trusts the stored string, meaning it will attempt to parse a maliciously crafted non-PDF file as a PDF.

**Source:** `documents_uploads.md §9`, citing `backend/api/uploads/views.py:56–60`  
**Why High:** File type spoofing is a production security concern, especially when uploaded files are later opened and parsed by the AI domain.

---

### H5 — No file name sanitization in storage key construction

The storage key is constructed as `uploads/<user_id>/<uuid4().hex>/<file.name>` using the raw original filename from the client (`uploads/views.py:63`). No normalization, extension stripping, or path traversal check is applied. A crafted filename containing directory traversal sequences (`../../`, `..%2F`) could produce unexpected key paths in the S3 bucket, and the unsanitized filename is stored permanently in `Upload.file_name`.

**Source:** `documents_uploads.md §9`, citing `backend/api/uploads/views.py:63`  
**Why High:** Path traversal in file upload is an OWASP-listed vulnerability class; the raw client-supplied filename should never be used directly in a storage path.

---

### H6 — ContractDocumentDeleteAPIView orphans Upload rows and S3 objects

`DELETE /api/contracts/<id>/documents/<doc_id>/` calls `doc.delete()`, which removes only the `ContractDocument` join row. The underlying `Upload` row is not deleted and `default_storage.delete()` is never called (`document_views.py:87`). S3 objects from detached contract documents accumulate indefinitely, and `Upload` rows persist with no associated document record.

**Source:** `documents_uploads.md §9`, citing `backend/api/contracts/document_views.py:87`  
**Why High:** Causes unbounded S3 cost growth; orphaned storage objects have no cleanup path.

---

### H7 — No LiveKit webhook handler

The LiveKit server emits events for room creation, participant join/leave, recording, and disconnection. No endpoint in the backend handles any of these events. If a session ends on the LiveKit side — all participants disconnect, inactivity timeout — the `LiveSession` record in the database remains in `active` status indefinitely, consuming the session usage counter and appearing as open in all session queries.

**Source:** `sessions.md §11`  
**Why High:** Stateful resource (`LiveSession`) diverges from real LiveKit room state; stuck `active` sessions pollute billing counters, dashboards, and session queries.

---

### H8 — ContractPaymentListCreateAPIView POST missing lifecycle feature gate

`PaymentListCreateAPIView.post()` checks `has_feature(request.user, "lifecycle")` before allowing payment creation (`views.py:119`). `ContractPaymentListCreateAPIView.post()` — the contract-scoped create route at `POST /api/payments/contracts/<contract_id>/` — does not check this gate (`views.py:467–489`). A user whose plan fails the lifecycle feature check can still create payments by using the contract-scoped endpoint.

**Source:** `payments.md §7`, citing `backend/api/payments/views.py:467`  
**Why High:** Billing gate bypass; allows users to access paid features without a qualifying plan.

---

### H9 — No SubscriptionPlan seed or fixture

`SubscriptionPlan` rows must exist in the database for any billing gate to function. No migration, fixture, or management command that creates initial plan rows was found in the codebase. All gate functions catch `UserSubscription.DoesNotExist` and return a blocked result, meaning a fresh deployment with no plan rows will lock all users out of contract creation and other gated features without a clear error.

**Source:** `billing.md §9`, citing `backend/billing/models.py` and `backend/billing/gates.py`  
**Why High:** A fresh production deployment is non-functional without plan seed data; there is no documented or code-backed path to create it.

---

### H10 — PaymentResolutionService diverges from the amount_paid recompute pattern

`PaymentResolutionService.resolve()` at `backend/api/contracts/services/payment_resolution_service.py:24–31` sets `obligation.state = "resolved"` directly and saves with `update_fields=["state"]`. It does not recompute `amount_paid` from confirmed payments and does not call `process_obligation_lifecycle()`. The three payment-domain write paths (confirm, refund, reverse) all recompute `amount_paid` and call `process_obligation_lifecycle()` before writing state. This path diverges silently and can mark an obligation resolved even if `amount_paid` has drifted from the confirmed payment sum.

**Source:** `payments.md §7`, citing `backend/api/contracts/services/payment_resolution_service.py:24–31`  
**Why High:** Data integrity divergence on a critical financial state transition; obligation financial state can be marked resolved incorrectly.

---

## 5. Medium

### M1 — DocumentsViewSet at /api/documents/ is a stub returning hardcoded strings

All five methods of `DocumentsViewSet` in `backend/api/documents/views.py:7–20` return `{"message": "..."}` literal strings. The viewset does not import `ContractDocument`, queries no model, and returns no real data. It is wired and reachable at `/api/documents/` (`backend/api/router.py:12`), where it conflicts in purpose with the real contract-document views at `/api/contracts/<id>/documents/`.

**Source:** `documents_uploads.md §9`, citing `backend/api/documents/views.py:7–20`  
**Why Medium:** Dead-end API route in the live URL namespace; misleads callers and creates confusion with the functional document views.

---

### M2 — Upload.is_draft_document is never set on upload create

`Upload.is_draft_document` was added in migration `0002` and is filterable via `?is_draft_document=` on the list endpoint (`uploads/views.py:44–46`). The upload `create` action sets `is_prep_material` from request data but never sets `is_draft_document` (`uploads/views.py:82`). The field is always `False` on every row in the database.

**Source:** `documents_uploads.md §9`, citing `backend/uploads/models.py:52` and `backend/api/uploads/views.py:82`  
**Why Medium:** A queryable filter field that can never return results; the intended write path is not established in code.

---

### M3 — contract_updated activity_type defined but never written

`contract_updated` is included in `ACTIVITY_TYPE_CHOICES` at `backend/activity/models.py:22` but no call site in the codebase passes it to `log_activity`. Contract updates through `ContractViewSet.update()` produce no activity record. Eighteen of the nineteen defined activity types are used at call sites; this one is not.

**Source:** `audit_activity.md §9`, citing `backend/activity/models.py:22`  
**Why Medium:** Audit trail is incomplete — contract edits leave no record in the activity log, creating gaps in contract history.

---

### M4 — start_trial is never called from any production code path

`start_trial(user)` in `backend/billing/gates.py:204` creates a trialing `UserSubscription` with `plan=business` and `trial_contracts_remaining=1`. It is defined and called from test code (`backend/api/tests/test_billing.py`) but is not called from any registration view, signal, or management command in production. New users receive no trial subscription; they hit a `no_subscription` gate immediately.

**Source:** `billing.md §9`, citing `backend/billing/gates.py:204`  
**Why Medium:** The trial onboarding flow is defined and tested but silently absent from production; the designed first-user experience does not function.

---

### M5 — Contract Pro permission matrix not wired to API enforcement

`ContractProPermissionService.get_effective_state()` evaluates the 15-action permission matrix defined via `ContractProPermissionRule` and returns a permission state per action. No API view consults this result before executing a Contract Pro action. The editing exclusivity check (`owner_editing_allowed()`) is enforced, but all per-action permission rules (sensitive/accessible) are not. Two sources flag this gap independently.

**Source:** `authority.md §7`; `contract_pro.md §7`, citing `backend/contract_pro/services/contract_pro_permission_service.py`  
**Why Medium:** The permission matrix exists in the database and service layer but has no effect on actual API behavior; the Contract Pro feature is partially unimplemented.

---

### M6 — Engine-layer PaymentService and PaymentGateway are unwired

`backend/engine/payments/payment_service.py` defines `PaymentService`, `PaymentGateway` (abstract base class), and `MockPaymentGateway`. The file header explicitly states it is not imported by any live API view. All live payment state transitions are direct ORM operations in `backend/api/payments/views.py`. The engine layer represents an alternative architecture that exists in the codebase but is not connected to any route. `MockPaymentGateway` always returns `transaction_id="mock_txn_123"`.

**Source:** `payments.md §7`, citing `backend/engine/payments/payment_service.py:8`  
**Why Medium:** Dead engine-layer code creates confusion about the actual payment flow and can mislead new contributors about what runs in production.

---

### M7 — SolContract.signed_by_member is never enforced as a precondition

`SolContract.signed_by_member` defaults to `False`. No view checks this flag before allowing payout creation, contribution updates, or any other Sol workflow step. A Sol can operate fully — payouts created, contributions tracked, PDFs exported — with all member contracts unsigned. There is also no member-accessible endpoint to set this flag to `True`.

**Source:** `sol.md §10`, citing `backend/sol/models.py:101`  
**Why Medium:** A defined consent mechanism with no enforcement and no completion path; the field serves no functional purpose.

---

### M8 — Sol domain has no audit trail

No `log_activity` calls exist anywhere in the Sol domain (`backend/api/sol/views.py`, `backend/api/sol/pdf_views.py`). Manager actions including payout creation, rearrangement, member deactivation, and contribution status changes are not written to any audit table. `SolPayout.rearranged_by` and `rearranged_reason` are the only per-event audit fields. `SolNote` is manager narrative, not an event log.

**Source:** `sol.md §10`  
**Why Medium:** Financial group management actions leave no traceable audit trail; this is a compliance concern for a platform handling rotating savings.

---

### M9 — Deactivated Sol member's pending SolContribution rows are not cleaned up

`SolMemberDeleteView.delete()` sets `SolMember.is_active = False` but does not modify or cancel any `SolContribution` rows in `pending` state (`views.py:383–384`). The deactivated member's contribution obligations remain in `pending` status. Managers see them as outstanding, and the dashboard contribution totals include them, even though the member is no longer active.

**Source:** `sol.md §10 / Open Questions §4`, citing `backend/api/sol/views.py:383–384`  
**Why Medium:** Inconsistent state in contribution tracking after deactivation; causes dashboard miscounts and confusing contribution history.

---

### M10 — No automatic obligation creation after contract signing

Signing a contract version via the sign endpoint sets `version.status = "signed"` and logs activity but does not trigger creation of any `ContractObligation` or `ContractServiceObligation` rows. Obligations must be created separately by either party after signing. There is no code path connecting the signing event to the obligations lifecycle.

**Source:** `contract_lifecycle.md §7`  
**Why Medium:** The designed handoff from contract lifecycle to obligations lifecycle is not implemented; parties must know to create obligations manually after signing.

---

### M11 — billing_period always written as "monthly" by Stripe sync

`_sync_subscription_from_stripe` in `backend/billing/services.py:322` unconditionally sets `billing_period="monthly"` regardless of the Stripe subscription's actual interval. The model defines `"yearly"` and `"per_contract"` as valid choices, and `price_yearly` exists on `SubscriptionPlan`. Any yearly subscriber synced from Stripe will show `billing_period="monthly"` in the local database.

**Source:** `billing.md §9`, citing `backend/billing/services.py:322`  
**Why Medium:** Data drift between Stripe state and local subscription records for any non-monthly billing tier; usage reports and billing-period-dependent logic will be incorrect.

---

### M12 — User-facing /api/activity/ endpoints have zero frontend consumers

`GET /api/activity/` and `GET /api/contracts/<id>/activity/` are fully functional, party-scoped read endpoints. No frontend code calls them. `frontend/src/pages/CreateContract.tsx:131` defines a static hardcoded `ACTIVITY` array in an in-editor "Activity Feed" panel — this is a placeholder that makes no API calls. The backend audit trail is invisible to users.

**Source:** `audit_activity.md §9`; noted in `backend/api/activity/views.py:66` and `CreateContract.tsx:131`  
**Why Medium:** Working backend infrastructure that produces no user-visible output; the activity domain writes to a void from the user's perspective.

---

### M13 — SubscriptionAPIView.post() allows direct plan changes when STRIPE_SECRET_KEY is absent

When `STRIPE_SECRET_KEY` is not set, `POST /api/billing/subscription/` writes plan and status directly to `UserSubscription` without Stripe involvement. The code comment says "dev/test only" but this is enforced solely by the absence of the secret key — there is no `DEBUG` guard, environment tag, or admin-only permission class. A production deployment without the Stripe key exposes this write path to all authenticated users.

**Source:** `billing.md §9`, citing `backend/billing/views.py:101`  
**Why Medium:** Configuration-dependent security boundary with no code-level production guard.

---

### M14 — Contract.status, Contract.state, Contract.is_active, Contract.version unused by API

`Contract.status` (draft/sent/active/completed/archived), `Contract.is_active` (Boolean), `Contract.version` (counter field), and `Contract.state` (refreshed by `refresh_state()` which is never called from any view) are defined on the model but are not written or read by any live API view. The contract lifecycle proceeds entirely through `ContractVersion.status`. These four fields are database columns with no live write path.

**Source:** `contract_lifecycle.md §7`, citing `backend/contracts/models.py`  
**Why Medium:** Dead model fields create schema confusion and mislead readers about what state the system actually tracks.

---

### M15 — No atomicity enforcement at the log_activity helper level

`log_activity()` deliberately omits `transaction.atomic()` (`backend/activity/log.py:8`). Callers that do not wrap both their own mutation and the `log_activity` call in a `transaction.atomic()` block can produce orphaned `ContractActivity` rows if the surrounding mutation rolls back. Of the 25 call sites across 8 files, whether each is safe was not individually verified.

**Source:** `audit_activity.md §9`, citing `backend/activity/log.py:8`  
**Why Medium:** Audit integrity risk; orphaned rows in the activity log break the accuracy of the audit trail without any error surfacing.

---

## 6. Low

### L1 — backend/api/activity/serializers.py is a stale dead file

The file exists at `backend/api/activity/serializers.py` but its header comment reads `# backend/api/contracts/serializers.py` and its content is `ContractSerializer`. It is not imported anywhere in the codebase. The activity views serialize inline via `_serialize()` at `backend/api/activity/views.py:37`.

**Source:** `audit_activity.md §9`, citing `backend/api/activity/serializers.py`  
**Why Low:** Copy-paste artifact; dead code with a misleading path header.

---

### L2 — AWS_QUERYSTRING_AUTH not configured; presigned URL behavior undefined

`AWS_DEFAULT_ACL = "private"` means S3 objects are not publicly accessible. URL generation via `default_storage.url()` returns the stored `Upload.file_url`. Whether `S3Boto3Storage` generates presigned (time-limited) or permanent URL strings depends on `AWS_QUERYSTRING_AUTH`, which is absent from `settings.py`. The actual URL behavior at runtime depends on the `django-storages` default, which is not established from the settings file alone.

**Source:** `documents_uploads.md §9`, citing `backend/core/settings.py:206–211`  
**Why Low:** Behavioral ambiguity in URL generation; affects whether stored `file_url` values expire and become unusable over time.

---

### L3 — LIVEKIT_HOST hardcoded in settings rather than driven by env var

`LIVEKIT_HOST = "https://live.bonup.cloud"` is hardcoded in `backend/core/settings.py:185`. All other LiveKit settings (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`) are env-driven. The host cannot be overridden without editing the settings file, making it impossible to point a staging environment at a different LiveKit instance.

**Source:** `sessions.md §11 / Open Questions §1`, citing `backend/core/settings.py:185`  
**Why Low:** Configuration inflexibility; inconsistent with the env-var pattern used by every other setting in the same block.

---

### L4 — _MAX_BUSINESSES contains both legacy and current plan slug sets

`_MAX_BUSINESSES` in `backend/billing/gates.py:259` includes legacy slugs (`trial`, `starter`, `professional`, `business`, `anchor`) alongside current slugs (`blackboard_basic`, `blackboard_pro`, `blackboard_business`, `blackboard_enterprise`). Any plan slug not in this dict silently returns `0` from `max_businesses` and blocks business entity creation. Whether the legacy slugs correspond to active `SubscriptionPlan` rows in any environment is not established in code.

**Source:** `billing.md §9`, citing `backend/billing/gates.py:259`  
**Why Low:** Potential dead slug entries cause confusion; a slug mismatch silently blocks a user from creating businesses with no informative error.

---

### L5 — SolContract name conflicts with contracts.Contract

`SolContract` (`backend/sol/models.py:144`) is a per-member plaintext participation agreement in the Sol domain. `contracts.Contract` (`backend/contracts/models.py`) is a full lifecycle negotiation model with versioning, signing, and role switching. They share no FK, no code relationship, and no base class. The naming collision can mislead developers searching for "Contract" in the codebase or reading model references.

**Source:** `sol.md §10`  
**Why Low:** Naming confusion only; no runtime impact.

---

### L6 — presentation_controller updated via WebSocket but not returned via HTTP serializer

`LiveSession.presentation_controller` is written by `SessionConsumer._update_presentation_controller` (`consumers.py:224–229`) when the initiator sends a `presentation_control` WebSocket event. The `_serialize()` function used by all HTTP session endpoints (`views.py:23–37`) does not include `presentation_controller` in its output. Clients loading the session detail page cannot retrieve the current controller state through the HTTP API.

**Source:** `sessions.md §11`, citing `backend/api/sessions/views.py:23–37`  
**Why Low:** Omission in the HTTP serializer; a client that needs the current controller state on page load cannot retrieve it without WebSocket history.

---

### L7 — RequestChange model defined but not wired to API

`RequestChange` is defined in `backend/contracts/models.py` as representing negotiation intent. It is not connected to any URL, view, or serializer and is not used in the live contract lifecycle. It exists as a schema artifact with no live write or read path.

**Source:** `contract_lifecycle.md §7`  
**Why Low:** Orphaned model definition; adds schema noise without contributing to any live feature.

---

### L8 — ContractVersion sent and negotiating statuses defined but never set

The status choices on `ContractVersion` include `draft`, `sent`, `negotiating`, `signed`, `superseded`, `archived`, and `rejected`. In live API usage, only `draft`, `signed`, `rejected`, and `superseded` are ever written. `sent` and `negotiating` are valid choices that no code path sets, creating a misleading state space on an otherwise active model.

**Source:** `contract_lifecycle.md §7`, citing `backend/contracts/models.py`  
**Why Low:** Dead status values; creates false expectation that these transitions exist.

---

### L9 — No log_activity on ContractPaymentListCreateAPIView POST and ObligationPaymentListCreateAPIView POST

`PaymentListCreateAPIView.post()` calls `log_activity` with `activity_type="payment_created"` (`views.py:144`). The contract-scoped and obligation-scoped create routes — `ContractPaymentListCreateAPIView.post()` and `ObligationPaymentListCreateAPIView.post()` — do not call `log_activity` (`views.py:483–489`, `533–539`). Payments created through these routes produce no activity record.

**Source:** `payments.md §7`, citing `backend/api/payments/views.py:483` and `:533`  
**Why Low:** Inconsistent audit coverage across semantically equivalent payment create paths.

---

## 7. Open Questions

Items that are not definitive gaps but are unresolved questions surfaced across the architecture documents. These require a human decision or deeper inspection before classification.

### Identity

- **Duplicate login endpoint intent** — Is `/api/users/login/` kept deliberately (e.g., for admin tooling or a legacy integration) or is it a forgotten artifact? If it has a real use case, the verification bypass (C1) may need a different fix than simply removing the endpoint. (`identity.md §4`)

### Payments

- **PATCH status bypass — intentional?** — Is the ability to PATCH `status` directly on `PaymentDetailAPIView` intended for admin correction flows, or is it an oversight? The architecture doc notes this is not determinable from code alone. (`payments.md §8.1`)
- **DELETE no recompute — intentional?** — Is the absence of obligation recompute on DELETE intentional — e.g., an operator promise to only delete draft payments — or an oversight? (`payments.md §8.2`)
- **process_obligation_lifecycle with obligation_repo=None** — All three obligation write sites call `process_obligation_lifecycle(obligation, obligation_repo=None, current_time=now)`. Whether passing `None` for `obligation_repo` suppresses any persistence was not inspected. (`payments.md §8.4`)

### Obligations

- **Obligation template model expansion** — `backend/contracts/models.py:226` docstring says "The engine expands this into actual lifecycle instances stored in ContractObligation" but no expansion code was found. The `obligation-templates/` URL prefix is registered in the router. The full relationship between `Obligation`, `ContractObligation`, and `backend/api/obligation_templates/` was not traced. (`obligations_lifecycle.md §8.1`)
- **obligation_templates and payment_templates modules** — Both `backend/api/obligation_templates/` and `backend/api/payment_templates/` are registered in the router but were not inspected. Their relationship to obligation creation is unknown. (`obligations_lifecycle.md §8.2`)
- **Obligation.recurrence_interval_days and recurrence_count** — Fields exist on the template model but no code path uses them to generate recurring obligation instances. Whether this is deferred or intended is not established. (`obligations_lifecycle.md §8.5`)

### Billing

- **Plan population mechanism** — How are `SubscriptionPlan` rows created in production? A management command, a data migration, or manual admin entry? (`billing.md §10.1`)
- **Legacy slug retirement** — Are the legacy slugs in `_MAX_BUSINESSES` (`trial`, `starter`, `professional`, `business`, `anchor`) still present in any `SubscriptionPlan` table in any environment, or have they been replaced entirely by the `blackboard_*` slugs? (`billing.md §10.2`)
- **Trial trigger** — Was `start_trial` removed from a prior registration flow, or was it never wired? Is the trial flow manually triggered only? (`billing.md §10.3`)
- **Yearly billing** — `price_yearly`, the `"yearly"` billing_period choice, and `"Per Contract"` choice exist in the model, but Stripe price IDs only cover monthly plans and `_sync_subscription_from_stripe` always writes `"monthly"`. Is yearly billing intentionally deferred? (`billing.md §10.4`)
- **sol_member in _LOWER_THAN_SOL_MEMBER** — `_LOWER_THAN_SOL_MEMBER = {"trial"}` means users on `per_contract`, `starter`, or other non-trial plans are not upgraded by `auto_upgrade_to_sol_member`. Whether this is intentional is not established. (`billing.md §10.6`)

### Documents / Uploads

- **Are Upload.file_url values ever expired?** — If `default_storage.url()` returns presigned URLs (the `S3Boto3Storage` default when `AWS_QUERYSTRING_AUTH` is unset or `True`), stored `file_url` values have a finite lifetime. Is there a refresh path? (`documents_uploads.md §10.1`)
- **Upload row cleanup responsibility** — After `ContractDocument` deletion, the `Upload` row remains. Is the expectation that users call `DELETE /api/uploads/<pk>/` separately, or is there an intended cleanup path that was never implemented? (`documents_uploads.md §10.3`)
- **Is related_contract on Upload redundant with ContractDocument?** — `Upload.related_contract` can be set at upload time; `ContractDocument` also joins `Upload` to a `Contract`. These can refer to different contracts. Whether the dual-association is intentional is not established. (`documents_uploads.md §10.4`)

### Sessions

- **Redis migration for CHANNEL_LAYERS** — Is there an intended path to replace `InMemoryChannelLayer` with a Redis-backed layer? No Redis URL for channels was found in `settings.py`. (`sessions.md §12.2`)
- **Can a party rejoin an ended session?** — `SessionJoinAPIView` blocks join for `ended` and `cancelled` statuses. There is no endpoint to re-open an ended session. Whether this is intentional is not established. (`sessions.md §12.4`)

### Sol

- **Is Sol.is_private enforced anywhere?** — The field is stored and returned in API responses but no view uses it to filter Sol visibility or restrict access. Its enforcement purpose is not established in code. (`sol.md §11.1`)
- **Is there a member self-service path to sign SolContract?** — `SolMembershipDetailView` returns the contract text and `signed_by_member` flag but there is no PATCH endpoint in the member self-service routes to update this flag. No signing endpoint was found. (`sol.md §11.2`)
- **Tips to co-managers** — `to_manager` is always set to `sol.primary_manager` at `views.py:701` regardless of caller. If co-managers are expected to receive tips, this does not work as written. (`sol.md §11.3`)

### Audit / Activity

- **contract_updated activity_type intent** — Was this type intended for a contract-edit audit path that was never built, or is it genuinely reserved? (`audit_activity.md §10.1`)
- **Atomicity at all 25 log_activity call sites** — Which of the 25 call sites wrap both their mutation and `log_activity` in `transaction.atomic()`? This was not individually verified. (`audit_activity.md §10.2`)

---

## 8. Suggested Order of Attack

This ordering follows: small-scope security fixes first → data integrity bugs → production-readiness items → everything else.

1. **[C4] Restore Postgres** — Restore `DATABASES` to Postgres. SQLite's `select_for_update()` no-op breaks payment concurrency guarantees. Settings-level change; no code changes required.
2. **[C1] Disable or patch /api/users/login/** — Remove or redirect the unverified login endpoint before any real users can register. One-line URL removal or endpoint deletion.
3. **[C2] Make PATCH /api/payments/\<id\>/ status read-only** — Add `status` to `read_only_fields` in `PaymentSerializer` to close the state machine bypass.
4. **[C3] Add obligation recompute to DELETE /api/payments/\<id\>/** — Replicate the `select_for_update()` + `amount_paid` recompute pattern from `PaymentConfirmAPIView` before deleting a payment.
5. **[H10] Fix PaymentResolutionService to call process_obligation_lifecycle** — Make the resolve path consistent with the confirm/refund/reverse pattern; add recompute before writing `state="resolved"`.
6. **[H3, H4, H5] Add file upload guards** — Add file size limit, MIME validation, and filename sanitization to `UploadsViewSet.create` in a single PR.
7. **[H8] Add lifecycle gate to ContractPaymentListCreateAPIView** — Copy the `has_feature(request.user, "lifecycle")` check from the generic payment create route to the contract-scoped route.
8. **[H9] Add SubscriptionPlan seed** — Create a data migration or management command that seeds the required `SubscriptionPlan` rows so a fresh deployment is functional.
9. **[H1] Switch CHANNEL_LAYERS to Redis** — Replace `InMemoryChannelLayer` with `channels_redis`; add `REDIS_URL` to the env configuration.
10. **[C5] Add structured error logging to log_activity** — Replace the bare `except Exception: pass` with a `logger.error(...)` call so notification failures are observable without blocking the caller.

---

## 9. Update Rule

Regenerate or update this file when:
- A gap listed here is fixed — remove the item or note the fixing commit.
- A new architecture file is written — check its "Current Gaps" section and add new items.
- A domain audit surfaces a new gap — add it to the appropriate severity section.
- Severity ratings change based on new context — re-classify and update the item.

This file is a point-in-time snapshot of known debt. It does not update automatically.
