# bonUP Privacy Slice 6 — production security and logging

Status: implemented with pre-commit corrections and focused validation; not deployed.

## Production settings

`backend/core/security.py` selects explicit `BONUP_ENV=development|test|production`.
Production requires DEBUG off, a strong SECRET_KEY, explicit non-wildcard hosts,
an HTTPS FRONTEND_URL, and real email delivery configuration. It enables HTTPS
redirects and secure session/CSRF cookies. Session cookies remain HttpOnly/Lax;
CSRF cookies remain readable/Lax for existing Django forms. nosniff and DENY frame
protection remain enabled; referrers are suppressed. CORS stays same-origin.

Development retains HTTP and the previous host list unless explicitly overridden.
No live `.env`, staging environment, storage/provider credentials, or service was
changed. Production mode must be set explicitly by deployment; development mode
is not a production security guarantee.

Required deployment configuration:

- `BONUP_ENV=production`, `DJANGO_DEBUG=False`, strong `SECRET_KEY`.
- `DJANGO_ALLOWED_HOSTS`: explicit live hostname(s).
- `FRONTEND_URL`: live HTTPS frontend URL.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: only necessary explicit HTTPS origins; empty is
  appropriate for matching-origin forms. Do not add wildcard CORS.
- `EMAIL_BACKEND`: ResendEmailBackend or Django SMTP backend, with the corresponding
  existing delivery credentials and `DEFAULT_FROM_EMAIL`. SMTP requires exactly
  one of TLS/SSL. A single boolean parser supplies both validation and effective
  Django SMTP flags (case-insensitive true/false or 1/0); both enabled is rejected
  in every environment. Resend transport must use HTTPS. Vault email also requires its
  existing Resend key and `BONUP_EMAIL_FROM`.
- `BONUP_TRUST_PROXY=False` by default. Set true only behind one verified edge
  that overwrites both X-Forwarded-Proto and X-Forwarded-For. The application port
  must be private. X-Forwarded-Host is not trusted. A comma-separated forwarded
  address chain is not treated as a trustworthy client identity.
- `BONUP_HSTS_SECONDS=0` remains the default. Enable a reviewed duration only after
  HTTPS/domain coverage is proven. Include-subdomains and preload remain false.

No tracked production proxy, service manager, or container configuration proves
an existing trusted topology. The tracked development path is browser → Vite →
Django runserver. Production acceptance must verify TLS termination, HTTP redirect,
Host/header rewriting, private backend binding/firewall, and built frontend serving.
Do not expose runserver/Vite development servers as the production deployment.

## Authentication and frontend credentials

JWT-in-Authorization remains the API mechanism; Django admin keeps session/CSRF
authentication. Normal customer access/refresh lifetimes remain SimpleJWT's 5
minutes/1 day. Refresh rotation remains off. View-As stays a separate 30-minute,
server-validated, non-refreshable context with existing write/content restrictions.

Customer logout verifies ownership/context before blacklisting the submitted
refresh token. A new operator logout endpoint blacklists the supplied operator
refresh and ends outstanding View-As sessions with intentional audit events.
The Operator Console now has an explicit sign-out button invoking that endpoint.
On failure it clears local operator/View-As credentials and displays an unconfirmed
server-sign-out notice on the operator login screen. It preserves customer credentials.
Stale operator profile cancellation/rejection cannot clear a newly selected identity.
Both customer menus show Exit User View during View-As and invoke its exit endpoint,
returning to the Operator Console without revoking either underlying refresh token.
Direct customer logout refuses an active View-As context before dispatch.
Already-issued access tokens remain valid until expiry; logout is not all-device
revocation, and failed network logout cannot promise server-side revocation.
Refresh of a deleted customer returns an authentication error. Password reset now
uses the existing password validators. No cookie/grant authentication system was added.

The WebSocket entry point now rejects operator/View-As credentials and inactive
customers before joining a session. Its existing customer JWT query parameter
mechanism remains: external WebSocket/access logs must omit queries.

`frontend/src/api/client.ts` restricts credential-bearing requests to the same-origin
API. It rejects absolute URLs, backslashes, repeated slashes, encoded separators and
dot-segment paths, and checks the final Axios base/suffix destination before attaching
Authorization. The separate Slice 4 private-delivery allowlist remains intact.
It keeps customer/operator refresh promises separate, rejects stale responses on
identity changes, settles failed queued requests, and preserves cancellation.
View-As expiry/exit clears the correct state without reviving stale customer data.

JWTs still use localStorage and remain accessible to same-origin JavaScript. This
is an accepted MVP limitation.
Known contract HTML render/parser/paste boundaries now use DOMPurify or plain text.
Scripts, embedded resources, event handlers, unsafe links and arbitrary CSS are removed.
DOMPurify preserves semantic formatting (including sup/sub), bounded list numbering,
tables, and the existing font controls. A dedicated sanitizer instance parses CSS
while detached and rebuilds only current-editor font, alignment, decoration, bounded
pixel spacing, line-height, generated heading/placeholder colors and spacer heights.
Font families are limited to the same exported list used by the editor. Unknown
classes, resource-loading CSS, backgrounds, positioning and custom properties are
removed. This narrow CSS fallback avoids replacing the existing editor's format
representation. Unsupported historical styling still changes; arbitrary rich pasted
HTML remains plain text. Production builds
add script-src self, object-src none, base-uri self, form-action self and no-referrer
meta policies. CSP remains intentionally partial: no default-src, img-src, media-src,
frame-src, connect-src, style-src or font-src is declared. Blob image/media and iframe
navigation are therefore not prohibited by those absent directives. object/embed
content is blocked. This is not a complete CSP, exfiltration boundary or XSS proof.
Actual production response headers and native PDF/player behavior still require
browser verification; a successful build or JSDOM render cannot prove enforcement.
HttpOnly cookie migration would require coordinated authentication/CSRF changes and
is deferred. Other unscoped localStorage profile/contact caches are not migrated or
erased by this slice; account-specific cache migration remains separate work.

## Abuse controls

`backend/core/throttling.py` enables scoped limits in production (optional opt-in
for development using `BONUP_THROTTLE_ENABLED=True`). Production cannot disable
these by setting that environment flag false. Limits are:

| Exact endpoint coverage | Shared scope / limit |
|---|---|
| POST `/api/auth/token/`, `/api/users/login/` | login: 10/minute/IP |
| POST `/api/operator/auth/token/`, `/admin/login/` | operator_login: 5/minute/IP |
| POST `/api/auth/token/refresh/`, `/api/users/login/refresh/`, `/api/operator/auth/token/refresh/` | refresh: 30/minute/IP |
| POST `/api/users/register/`, `/api/users/password-reset/`, `/api/users/password-reset/confirm/`, `/api/users/resend-verification/` | recovery: 5/hour/IP |
| GET/HEAD `/api/uploads/shares/{token}/` | share_metadata: 60/minute/IP |
| GET/HEAD `/api/uploads/shares/{token}/delivery/`, including range requests | share_delivery: 120/minute/IP |
| GET/POST `/api/uploads/{id}/shares/` (listing and creation, not revocation) | share_create: 30/hour/customer |
| POST `/api/uploads/`, `/api/uploads/{id}/duplicate/` | upload: 20/minute/customer |
| POST `/api/uploads/bulk-download/` | bulk_download: 10/minute/customer |
| POST `/api/uploads/{id}/email/` | email: 20/minute/customer |
| GET `/api/users/search/`, `/api/search/`, `/api/search/{contracts,obligations,payments,sessions,documents,templates,sol}/` | search: 60/minute/customer |
| POST `/api/ai/{chat,analyze-contract,counter-contract,import-contract}/`, `/api/ai/contracts/generate-draft/` | ai: 10/minute/customer |

Scopes share a bucket across the listed endpoints. DRF can also throttle admitted
OPTIONS requests. Public scopes use the IP even for authenticated callers. Protected
scopes use the authenticated customer identity. Without explicit proxy trust, the
socket peer supplies the IP; with trust, only a single forwarded-for value is used.
These are not universal endpoint limits: contract device uploads, lifecycle attachment
uploads, private delivery and Share revocation are not included in these scopes.

Existing database-backed Email File attempt counting (10/hour by default),
idempotency, size limits, and quota checks remain intact. Native sharing continues
through authenticated delivery. Limits use hashed client/customer cache identities,
never raw bearer tokens or emails. Share guessing across different tokens shares
an IP limit; every admitted Share request still validates the bearer token.

Django's existing LocMem cache is process-local, non-atomic, and resets on restart.
It is best-effort abuse friction for single-process development/MVP use, not an exact
cross-worker limit or DDoS control. It must never be described as globally enforced.
A real multi-worker deployment must complement it with verified edge controls or
an intentionally configured shared cache. No Redis service or rate-limit model was
introduced. The existing Email File count-then-create limit is also approximate
under concurrent requests. Do not present these as a distributed quota guarantee.

## Errors and privacy-safe logs

Private Vault malformed path IDs use DRF's safe lookup wrapper. Unhandled API
exceptions become generic 500 responses, Django validation becomes a generic 400,
and 404 responses are normalized. Private ContractDocument/lifecycle attachment
non-party lookups now return 404; deliberate domain-policy 403 responses elsewhere,
including View-As denial, remain unchanged. Cleanup/retention behavior is unchanged.

`backend/core/privacy_logging.py` renders allowlisted JSON fields only: event,
level, status, generated request ID, and validated internal resource UUID where
supplied. It never renders arbitrary log messages, args, exception text, tracebacks,
request objects, headers, bodies, filenames, provider locators, or tokens. Known
application logger.exception calls and raw provider exception arguments were also
removed. Unexpected errors remain observable as safe failure events and HTTP 500s.
Notification delivery returns stable error categories instead of raw exception text.

`PrivacyRequestMiddleware` generates correlation IDs rather than trusting incoming
values. Intentional operator audit records remain separate and retain their domain
metadata. Forwarded audit IPs follow the explicit proxy trust setting.

Development console email is replaced with a safe placeholder that logs only a
suppression event and sends no email. To test real delivery, configure the existing
provider; automated tests use synthetic locmem messages. No recovery token is returned
to the frontend, and its stale direct-reset-link debug UI was removed. Raw frontend
identity/parser logs were removed; Vault native-sharing diagnostics remain DEV-only
and exclude tokens, filenames, contents, URLs, and exception messages.

Django logging configuration does not control an external proxy, independently
configured process manager, or all worker access loggers. Deployment MUST ensure
request paths containing Share/invitation tokens and all query strings (including
WebSocket JWTs, reset tokens, and private search queries) are omitted or redacted
there too. Logging full paths without query strings alone is insufficient for
bearer tokens embedded in path segments.

## Runtime-log Git hygiene and remaining boundaries

`.gitignore` now excludes generated logs/PIDs. The existing four tracked files under
`dev/logs/` remain tracked and excluded from the Slice 6 commit; running services
may continue writing them. Untracking remains separate owner-controlled work. The owner should remove those four paths from the
index while retaining local files, then commit the ignore change. Existing history
is not erased by untracking; historical exposure review is separate from this task.

No credential rotation, provider configuration change, auth redesign, purge,
retention/quota redesign, migration, deployment change, or service restart was made.
Dependency installation reported existing npm audit findings; the lockfile changes
only add DOMPurify and its type dependency. Broad dependency upgrades were not mixed
into this slice. Review unresolved dependency advisories before production release.

## Previous implementation validation and baselines

Synthetic fixtures only; tests use dedicated PostgreSQL databases. No customer file
was opened. A temporary runner calls Django's normal test command with a dedicated
test database and an MD5 test password hasher; runtime application settings are not
changed by the runner.

- New backend security tests: 33 passed.
- Main relevant regression: 348 tests, 1 pre-existing administrator fixture failure.
  The pre-change run had 315 tests and the same single failure.
- Broader current run: 523 tests, 13 failures and 32 errors. The isolated pre-change
  baseline had 490 tests, the same 13 failures/32 errors, and identical failure/error
  identities and multiplicities. These existing failures are not claimed resolved.
- Frontend security and Slice 4 delivery tests: 27 passed, no skips.
- Vite production build passes, with the existing large-chunk warning.
- `manage.py check`: no issues.
- No new migration; global migration consistency still reports pre-existing users
  and activity drift, and no migration was generated or applied.
- Standard TypeScript build is blocked by the existing TypeScript 6 baseUrl
  deprecation. With the CLI-only deprecation override, both current and untouched
  HEAD source have the same 71 diagnostics. No tsconfig change was made.
- ESLint cannot run because the repository has no ESLint configuration file.

Commands used (output logs are under `/tmp/slice6-*`):

```bash
venv/bin/python /tmp/bonup_slice5_tests.py backend.api.tests.test_production_privacy
venv/bin/python /tmp/bonup_slice5_tests.py backend.api.tests.test_production_privacy backend.api.tests.test_operator_auth backend.api.tests.test_auth_login_verification backend.api.tests.test_signup_email backend.api.tests.test_resend_email_backend backend.api.tests.test_uploads backend.api.tests.test_documents backend.api.tests.test_operator_file_privacy backend.api.tests.test_canonical_file_authorization backend.api.tests.test_file_delivery backend.api.tests.test_retention_safe_removal backend.api.tests.test_removal_concurrency
venv/bin/python /tmp/bonup_slice5_tests.py backend.api.tests.test_production_privacy backend.api.tests.test_ai_contract_tools backend.api.tests.test_search backend.api.tests.test_sessions backend.api.tests.test_stripe_billing backend.api.tests.test_billing backend.lifecycle.tests backend.agreement_exchange.tests backend.emailing.tests
BONUP_TEST_TOOLS=/tmp/bonup-slice4-test-tools/node_modules node --test frontend/tests/privacySecurity.test.cjs frontend/tests/fileDelivery.test.cjs
npm run build --prefix frontend
venv/bin/python manage.py check
venv/bin/python manage.py makemigrations --check --dry-run
frontend/node_modules/.bin/tsc -p frontend/tsconfig.app.json --ignoreDeprecations 6.0 --noEmit --pretty false
```

## Scope inventory

Files changed for Slice 6 (plus this document):

- `.env.example`
- `.gitignore`
- `backend/agreement_exchange/notifications.py`
- `backend/agreement_exchange/services.py`
- `backend/api/ai/views.py`
- `backend/api/auth/views.py`
- `backend/api/billing/views.py`
- `backend/api/contracts/document_views.py`
- `backend/api/contracts/prepare_views.py`
- `backend/api/lifecycle/views.py`
- `backend/api/operator/urls.py`
- `backend/api/operator/views.py`
- `backend/api/search/views.py`
- `backend/api/sessions/consumers.py`
- `backend/api/tests/test_canonical_file_authorization.py`
- `backend/api/tests/test_documents.py`
- `backend/api/tests/test_file_delivery.py`
- `backend/api/tests/test_production_privacy.py`
- `backend/api/tests/test_uploads.py`
- `backend/api/uploads/views.py`
- `backend/api/users/views.py`
- `backend/billing/services.py`
- `backend/core/api_errors.py`
- `backend/core/email_backends.py`
- `backend/core/middleware.py`
- `backend/core/privacy_logging.py`
- `backend/core/security.py`
- `backend/core/settings.py`
- `backend/core/throttling.py`
- `backend/lifecycle/tests.py`
- `backend/operator/services.py`
- `backend/uploads/services.py`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/api/client.ts`
- `frontend/src/components/workflow/WorkflowWorkspace.tsx`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/context/OperatorContext.tsx`
- `frontend/src/lib/safeHtml.ts`
- `frontend/src/pages/AgreementExchange.tsx`
- `frontend/src/pages/ContractDocumentView.tsx`
- `frontend/src/pages/Contracts.tsx`
- `frontend/src/pages/CreateContract.tsx`
- `frontend/src/pages/ForgotPassword.tsx`
- `frontend/tests/privacySecurity.test.cjs`
- `frontend/vite.config.ts`


## Pre-commit correction validation

The original 47-file slice is retained. Six additional frontend files wire and test
explicit sign-out actions: 53 intended files total including this document.

- Corrected focused backend run: 94 tests passed (production privacy/settings,
  SMTP, operator API authentication, operator file privacy, customer login
  verification, Resend backend, and file delivery).
- The run also including AdministratorAccountModelTests ran 102 tests with the one
  recorded pre-existing failure:
  `test_real_administrator_requires_linked_verified_bonup_user`. Its failure identity
  matches the prior baseline. No unrelated fixture/model correction was made.
- Frontend correction/security/delivery tests: 44 passed, zero failures or skips.
  Checks use the already available Node/React/JSDOM mechanism and synthetic
  data. They cover final Axios destinations, all credential contexts, actual logout
  UI/context behavior, format save/reload sanitization, XSS rejection, private Blob
  image/audio/video/PDF rendering, download cleanup and public Share image/media/PDF
  component rendering. The built index policy is checked unchanged.
- No installed browser test mechanism/executable was found. No framework/browser was
  installed. Real playback, native PDF rendering and CSP enforcement remain manual
  deployment prerequisites for the actual built frontend and deployment headers.
- `manage.py check` passes. Vite production build passes with the existing chunk-size
  warning. The 71 TypeScript diagnostics match the recorded baseline as a multiset
  after ignoring shifted line/column positions; no new diagnostic was introduced.
- No broad 523-test suite or migration command was rerun for these corrections.

Correction commands (logs `/tmp/slice6-corrections-*`):

```bash
venv/bin/python /tmp/bonup_slice5_tests.py backend.api.tests.test_production_privacy backend.api.tests.test_operator_auth backend.api.tests.test_operator_file_privacy backend.api.tests.test_auth_login_verification backend.api.tests.test_resend_email_backend backend.api.tests.test_file_delivery
venv/bin/python /tmp/bonup_slice5_tests.py backend.api.tests.test_production_privacy backend.api.tests.test_operator_auth.OperatorAuthenticationTests backend.api.tests.test_operator_file_privacy backend.api.tests.test_auth_login_verification backend.api.tests.test_resend_email_backend backend.api.tests.test_file_delivery
BONUP_TEST_TOOLS=/tmp/bonup-slice4-test-tools/node_modules node --test frontend/tests/privacySecurity.test.cjs frontend/tests/authContextSecurity.test.cjs frontend/tests/fileDelivery.test.cjs
venv/bin/python manage.py check
(cd frontend && npm run build)
frontend/node_modules/.bin/tsc -p frontend/tsconfig.app.json --ignoreDeprecations 6.0 --noEmit --pretty false
```

Additional correction files:

- `frontend/src/components/layout/CustomerSignOutButton.tsx`
- `frontend/src/components/layout/Header.tsx`
- `frontend/src/components/layout/PlatformShell.tsx`
- `frontend/src/pages/admin/AdminLayout.tsx`
- `frontend/src/pages/OperatorLogin.tsx`
- `frontend/tests/authContextSecurity.test.cjs`
