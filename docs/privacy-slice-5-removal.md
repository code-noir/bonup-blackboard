# bonUP Vault retention-safe removal

Customer Remove != physical destruction. Future hard purge is a separate
privileged operation; this slice adds no purge endpoint, sweeper, or deduplication.

## Removal and authorization

Legacy Upload removal sets nullable `vault_removed_at` and retains the row,
physical locator, and existing ContractDocument references. Shared ordinary
Vault eligibility excludes removed legacy rows from listing, search, delivery,
new references, bare Upload-ID AI processing, and customer actions. Existing
authorized ContractDocument delivery remains available. URL-only legacy rows
are retained without fetching, proxying, or deleting remote content. Removed
rows do not make an otherwise empty Vault folder non-empty.

Canonical removal revokes shares and hides the customer's UserObjectAccess.
If any ContractDocument references the same StoredObject through any Upload
owned by that customer, access stays active and quota-counting. Otherwise,
access becomes inactive/non-counting and the selected Upload metadata row is
deleted as before. StoredObject and provider bytes remain retained in both cases.

## Transaction boundary

`backend/uploads/retention.py` supplies short database-only transactions.
Required lock order is Contract (where applicable), Upload rows ordered by PK,
then UserObjectAccess rows ordered by customer and StoredObject. Locks use plain
Upload rows, not the DISTINCT eligibility queryset. Eligibility is rechecked
after locks. Canonical state comes only from `Upload.stored_object_id`; missing
canonical access fails closed. StoredObject identity is unchanged and is not
locked. Storage/AI/provider work stays outside these short transactions.

Contract attachment and Share creation use the same locking boundary as Remove.
If attachment wins, removal sees the committed reference and retains hidden,
counting access. If removal wins, attachment rechecks eligibility and fails.
If Share creation wins, removal revokes it; if removal wins, Share creation fails.
Bulk Remove uses one transaction per item, preserving per-item result semantics.

## Reference reconciliation

`backend/documents/services.py` integrates attachment, explicit detach, contract
API deletion, role-switch contract deletion, and Django admin single/bulk Contract
deletion. After detach, reconciliation considers every surviving ContractDocument
for the same customer and StoredObject, including references through other Uploads.
Only access with `is_visible=False` AND `removed_at IS NOT NULL` represents prior
customer removal. When its last reference disappears, access becomes inactive and
non-counting, shares remain revoked, and removal time and physical bytes remain.
Visible files and hidden grants without a removal timestamp are unchanged. Another
customer's access is not modified.

Quota history recognizes a counting UOA or a removal timestamp so archiving the
last canonical access cannot restore stale legacy aggregate usage. A genuinely
legacy-only customer retains aggregate accounting; an intentionally non-counting
grant without removal history does not switch that customer to canonical usage.

## Migration

`uploads.0010_upload_vault_removed_at` adds only the nullable timestamp. No data
migration, provider configuration, authentication change, or physical copy occurs.

## Validation

All fixtures are synthetic. The dedicated PostgreSQL test database is
`test_bonup_slice5_validation`; a temporary test runner sets that name and the MD5
password hasher for tests only, then invokes Django's normal test command.

Final focused result: **31 tests passed in 18.538s**, including **8 PostgreSQL
concurrency tests**, with no skips.

Focused modules:

- `backend.api.tests.test_retention_safe_removal`
- `backend.api.tests.test_removal_concurrency`

The concurrency suite uses separate PostgreSQL connections and verifies actual
blocking with `pg_blocking_pids`, covering both attachment/removal and Share/removal
orders, legacy removal, and separate Uploads sharing a customer UOA. Its test-only
all-app cascading flush accommodates a historical `users_contact` table whose
model is absent from current code.

Regression modules: `test_uploads`, `test_documents`, `test_stored_objects`,
`test_storage_capacity_foundation`, `test_operator_file_privacy`,
`test_canonical_file_authorization`, `test_file_delivery`, `test_role_switch`, and
`test_search`, all under `backend.api.tests`.

The pre-change seven-module baseline (excluding role-switch/search and new tests)
passed 317 tests. The combined regression run passed 455 tests. Django system
check and Upload-scoped migration consistency pass. The global migration check
reports pre-existing model/migration drift in `users` and `activity`; no unrelated
migrations are included.

## Remaining boundaries

Arbitrary ORM deletion, account-wide cascades, and custom code bypassing these
explicit services are not automatically reconciled or serialized. No hidden
signals or broad cascade interception were added. Future reference mutation paths
must use the same lock order and explicit services.

Legacy aggregate usage cannot reliably attribute bytes to individual Upload rows;
this slice does not invent a per-file decrement. URL-only legacy content remains
undeliverable without a trusted locator. Existing failed-write compensation and
temporary artifact cleanup remain physical cleanup operations, distinct from
customer Remove. Already in-flight delivery/AI operations are not cancelled by
removal; network work is deliberately outside mutation transactions.

## Commands run

```bash
venv/bin/python /tmp/bonup_slice5_tests.py backend.api.tests.test_retention_safe_removal backend.api.tests.test_removal_concurrency --verbosity 2
venv/bin/python /tmp/bonup_slice5_tests.py backend.api.tests.test_retention_safe_removal backend.api.tests.test_removal_concurrency backend.api.tests.test_uploads backend.api.tests.test_documents backend.api.tests.test_stored_objects backend.api.tests.test_storage_capacity_foundation backend.api.tests.test_operator_file_privacy backend.api.tests.test_canonical_file_authorization backend.api.tests.test_file_delivery backend.api.tests.test_role_switch backend.api.tests.test_search
venv/bin/python manage.py migrate uploads 0010 --plan
venv/bin/python manage.py migrate uploads 0010 --noinput
venv/bin/python manage.py makemigrations uploads --check --dry-run
venv/bin/python manage.py makemigrations --check --dry-run
venv/bin/python manage.py check
```

The temporary runner is an invocation adapter, not a repository/configuration
change. For a normally configured isolated test database, use `manage.py test`
with the same module arguments. No frontend files changed; no frontend build
was required.
