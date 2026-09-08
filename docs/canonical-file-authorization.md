# Canonical file authorization

`get_upload_for_new_reference(user, upload_id)` in `backend/uploads/services.py`
resolves an existing Upload for a new Tool reference or bare-upload processing.
It reuses `get_active_uploads_for_user`: Upload ownership is always required;
a non-null StoredObject relationship additionally requires matching active,
visible UserObjectAccess. Missing canonical access fails closed. Only rows
with no StoredObject relationship use the legacy owner-only policy.

Contract-document creation uses this resolver for every existing Upload ID.
The client-provided `source` value does not select authorization policy.
Creating a reference does not copy storage, grant/reactivate access, or change
quota accounting. Fresh multipart uploads retain their existing creation flow.

The shared AI PDF reader uses the same resolver for analyze, counter, and
import requests. Authorized canonical reads use StoredObject backend and
object identity; legacy reads retain Upload storage-key behavior. Invalid or
unauthorized Upload IDs return 404 before reading storage or processing AI.

## Existing references

Existing ContractDocument access continues to use contract-party authorization.
Removing a referenced file from Vault leaves its access active and quota-counting
but hidden. That file remains accessible through its authorized contract, while
new attachment selection and bare-upload AI reads reject it. Authorized document
search can retain the reference; Vault/upload search excludes the hidden file.

## Limits

The resolver checks eligibility at lookup time; it does not serialize concurrent
access removal against attachment creation or a storage read. No new locking or
revocation protocol is introduced. Existing-reference AI processing would require
an explicit reference-authorized API; a bare Upload ID does not provide one.
Provider-URL delivery, historical null relationships, physical removal, and quota
policy are unchanged. Operator View-As restrictions remain independently enforced.
