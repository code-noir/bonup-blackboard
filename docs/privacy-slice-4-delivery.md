# Privacy Slice 4: authorized file delivery

Private file responses use bonUP delivery routes. The browser fetches those
routes with the existing authenticated Axios client and displays or downloads
Blob URLs. No delivery cookie, session, or bearer grant was introduced.

## Authorization and delivery

- `backend/uploads/delivery.py` reads an already-authorized storage identity.
  It performs no user or reference authorization and never generates a storage
  URL. Canonical Uploads use StoredObject backend/object identity; noncanonical
  Uploads require an existing trusted storage key. FileField resources use their
  own storage backend.
- Vault delivery uses the existing owner/active/visible queryset. ContractDocument
  delivery resolves the document within its contract and checks contract-party
  authorization, preserving retained hidden references and counterparty access.
- Lifecycle delivery resolves the attachment within the authorized lifecycle
  item and its agreement/contract. It does not change lifecycle domain rules.
- Each public-share GET/HEAD/range request reuses token hashing, expiry,
  revocation, and active/visible owner-access checks before reading bytes.
  There is no provider redirect.
- View-As guards run before storage access on every integrated endpoint.
  Existing write blocking and canonical new-reference eligibility are unchanged.

The reader supports GET, body-free HEAD, and one byte range. GET ranges support
closed, open-ended and suffix forms; valid ranges return 206 and Content-Range.
Invalid, multiple or unsatisfiable ranges return 416. HEAD ignores Range and
returns full-representation headers. If-Range requests receive a full GET because
this API does not publish validators. S3 uses SDK bounded reads with an ETag
precondition instead of S3File's full-object spool. Other backends use size/open
and seek. Streams are closed on completion, interruption and response closure.

Private responses use `Cache-Control: private, no-store`; public share responses
use `Cache-Control: no-store`. Both use nosniff, including delivery permission
errors. ZIP delivery also receives the private headers. Missing storage objects
produce generic 404 responses; other storage failures produce generic 503s.
Failures after headers terminate the response without exposing provider errors.

Private delivery defaults to attachment. `preview=1` permits only the explicit
safe MIME allowlist; `download=1` forces attachment. Unknown or active types,
including HTML/SVG/XML, use application/octet-stream and attachment disposition.
Frontend previews independently allow only supported raster images, media and
PDF; PDF Blob iframes are sandboxed. Public safe PDF preview alone receives a
scoped SAMEORIGIN frame header. Global frame/security configuration is unchanged.

## API and frontend compatibility

Upload, ContractDocument, search and lifecycle `file_url` fields contain
resource-specific bonUP routes. ContractDocument routes never fall back to Vault
visibility authorization. View-As still suppresses these fields. Creation and
duplication persist an empty legacy URL field rather than generate provider URLs.
Existing persisted values are not rewritten or used as proxy targets.

Prep URL-only records do not establish storage authorization. Their metadata is
preserved and their `file_url` is null for all customers. There is no generic URL
proxy or filename/URL-to-object inference. Legacy Uploads with no trusted storage
key fail closed at delivery. These are intentional compatibility limitations.

`frontend/src/api/fileDelivery.ts` accepts only known relative private delivery
routes, strips the existing API base prefix correctly, and uses the existing JWT
client. External URLs, public bearer URLs and unrelated API paths are rejected
before Axios can attach credentials. Authentication-context changes invalidate
pending requests and object URLs. Cancellation survives delivery token refresh.

`frontend/src/components/files/PrivateFile.tsx` implements Blob previews,
lazy thumbnails, downloads, cancellation, loading/errors and object-URL cleanup.
Vault uses it for previews/thumbnails/downloads. Contract and lifecycle attachment
buttons download authenticated Blobs for opening locally. Public Share continues
using direct bonUP bearer delivery URLs, with explicit download disposition on
its download link. Native Share, Email File and ZIP operations retain their
existing authorization and business behavior.

## MVP limitations

- Audio/video playback waits for the whole authenticated Blob. Large media and
  original-image thumbnails can consume substantial browser memory. Progressive
  private media playback, transcoding and thumbnail generation are deferred.
- Browser/plugin-specific PDF rendering and real media decoding are not proven
  by DOM component tests. Unsupported preview types remain downloadable.
- Revocation prevents subsequent authorized requests. Downloaded bytes and
  responses already authorized/in flight cannot be recalled. Already-issued
  historical provider URLs are not retroactively invalidated by this code.
- Authorization and storage reads are not one cross-system transaction. S3's
  read precondition prevents mixing object replacements within a response;
  generic storage backends depend on their own seek/identity semantics.
- URL-only Prep/legacy records cannot be delivered without a trusted resource
  relationship. No schema migration or provider configuration change is included.

## Validation commands

Synthetic fixtures only; no customer object reads or email deliveries.

The initial baseline used the normal command:

```sh
venv/bin/python manage.py test backend.api.tests.test_uploads backend.api.tests.test_documents backend.api.tests.test_operator_file_privacy backend.api.tests.test_canonical_file_authorization backend.api.tests.test_prep --noinput
```

Subsequent runs used `/tmp/bonup_slice4_tests.py`, a temporary management-command
wrapper with a separate test database name and MD5 **test-only** password hasher.
It changes no repository configuration. Its equivalent ordinary command is:

```sh
venv/bin/python manage.py test backend.api.tests.test_file_delivery backend.api.tests.test_uploads backend.api.tests.test_documents backend.api.tests.test_operator_file_privacy backend.api.tests.test_canonical_file_authorization backend.api.tests.test_prep backend.api.tests.test_search --noinput
```

Broader coverage added `backend.api.tests.test_stored_objects`,
`backend.api.tests.test_storage_capacity_foundation`,
`backend.api.tests.test_ai_contract_tools`, and `backend.api.tests.test_operator_auth`.
`backend.lifecycle.tests` was also run separately.

Lifecycle/operator failure baselines used `/tmp/bonup_slice4_baseline.py`, which
loads only modified Slice 4 Python modules from HEAD through an import loader.
It leaves working-tree files unchanged and retains unrelated dirty source code.

Frontend dependencies were kept outside the repository:

```sh
npm install --prefix /tmp/bonup-slice4-test-tools --no-audit --no-fund jsdom@26
BONUP_TEST_TOOLS=/tmp/bonup-slice4-test-tools/node_modules node --test frontend/tests/fileDelivery.test.cjs
cd frontend
npm run build
npx tsc --noEmit -p tsconfig.app.json --ignoreDeprecations 6.0
```

The TypeScript baseline used a temporary CompilerHost to read modified frontend
files from HEAD without restoring files. Diagnostics were compared by filename,
code and message, ignoring shifted line numbers. ESLint was attempted but the
repository has no ESLint 9 configuration. No lint configuration was added.

```sh
venv/bin/python manage.py check
```

## Recorded results

- Initial baseline: 273 tests, OK (955.144 seconds).
- Final focused backend: 383 tests, OK (32.744 seconds).
- Broader backend: 517 tests, 516 passed and one failure (36.368 seconds).
  `AdministratorAccountModelTests.test_real_administrator_requires_linked_verified_bonup_user`
  also fails before Slice 4 (one-test baseline, 0.142 seconds).
- Lifecycle: 80 tests, 73 passed, six failures and one error (24.027 seconds).
  The pre-Slice-4 baseline has the same seven failing tests (25.729 seconds):
  `test_dashboard_open_lifecycle_route_can_load_lifecycle_data` (error),
  `test_performance_action_rejects_oversized_video_proof`,
  `test_personal_overlay_is_user_specific_and_persists_across_refresh`,
  `test_personal_overlay_repeated_patch_updates_existing_user_state`,
  `test_signed_event_setup_agreement_refines_titles_triggers_and_conditional_fee`,
  `test_signed_loan_repayment_schedule_uses_contract_values_for_different_terms`,
  `test_timeline_setup_owner_edit_rules_and_tracking_metadata`.
- Frontend: 16 tests passed, no failures/skips (2191.869606 milliseconds).
  These are synthetic jsdom component tests, not real-browser media decoding.
- Production frontend build passed (1.38 seconds), with a chunk-size warning.
- TypeScript: 71 diagnostics before and after; identical filename/code/message
  sets, no new diagnostics. The existing TypeScript 6 baseUrl deprecation was
  handled on the command line; repository configuration remains unchanged.
- Django check: no issues (0 silenced).
- ESLint cannot run without a repository ESLint 9 configuration.

No migrations, provider/credential configuration, global authentication/security
settings, or quota/removal semantics were changed. No real customer file access
was used for validation.
