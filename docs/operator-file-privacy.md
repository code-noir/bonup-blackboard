# Operator View-As file privacy

A validated `request.impersonation_session` prohibits customer file content
access. The shared policy lives in `backend/api/operator/permissions.py`;
customer identity alone does not distinguish View-As from customer access.

Direct upload delivery, public-share metadata/delivery, and Sol PDF exports
reject View-As with 403 before content operations, including on HEAD requests.
Bulk-download and email handlers also use the guard; the existing JWT
write-method restriction continues to reject these POST requests first.

Upload, contract-document, search, and prep responses preserve metadata but
return null file URLs during View-As. Lifecycle attachment responses retain
the existing empty-string convention. URL generation is skipped entirely,
including legacy upload URL fallback.

AI conversation detail returns an empty messages list while retaining message
count and other metadata. Workflow responses suppress review results,
counter-drafts, and counterparty requested changes. Normal customer responses
and existing ownership/contract-party checks remain unchanged.

Share listing remains metadata-only. Anonymous valid Share Links continue to
work. There is no privileged-content exception or new audit/grant mechanism.

## Limits

This boundary does not revoke previously issued URLs or cached bytes, identify
an operator using an independently obtained anonymous Share Link, or track
content copied into arbitrary free text or contract snapshots. Existing
GET-side effects are not addressed by the file-content policy.

## Verification

`backend/api/tests/test_operator_file_privacy.py` exercises real View-As JWT
requests, metadata suppression, storage-call avoidance, GET/HEAD delivery
blocking, anonymous sharing, normal customer access, and View-As exit.
