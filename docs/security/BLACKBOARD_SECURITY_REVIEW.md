# BLACKBOARD_SECURITY_REVIEW.md

> Status: Working draft  
> Scope: Blackboard phase-one backend/system security review  
> Purpose: Record the current security findings derived from targeted repo inspection

## 1. Executive Security Summary

Blackboard’s core contract-party access model is coherent and consistently applied across its primary domains. The `is_party()` check is the central enforcement mechanism and appears in every major contract-adjacent view. JWT authentication is enforced globally via REST framework defaults. The email-verification gate at token issuance is solid.

However, several high-severity issues exist that collectively make the system **not ready** for production launch as-is:

- a production server IP is hardcoded in `settings.py` while `DEBUG = True` is also hardcoded
- LiveKit API credentials are hardcoded in source
- the password reset endpoint returns the reset token directly in the response body instead of sending it by email
- the Stripe webhook accepts crafted JSON when `STRIPE_WEBHOOK_SECRET` is unset
- a dormant `ContractViewSet` with `AllowAny` and no ownership filter exists in a routed package and is one bad import away from exposing all contracts publicly

## 2. Confirmed Security Strengths

- Global `IsAuthenticated` default is enforced through `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]`
- `is_party()` is consistently enforced across major contract-adjacent views
- Email verification is enforced before token issuance
- Contract write actions are initiator-only where expected
- Signing and rejection are counterparty-only where expected
- `BusinessEntity` detail access is owner-scoped
- Upload deletion is owner-scoped
- WebSocket session access uses JWT auth and party checks before accept
- Approval actions enforce `requested_from` checks when present
- Billing gates are server-side enforced
- Stripe webhook signature verification is performed when `STRIPE_WEBHOOK_SECRET` is configured
- Direct subscription mutation is disabled when Stripe is active
- `ContractVersion` immutability is enforced
- Initiator identity is stripped from contract create/update input
- Admin endpoints use `IsAdminUser`
- Refresh token blacklisting exists on logout

## 3. Confirmed Security Weaknesses

### W1. Password reset token returned in API response body
`PasswordResetRequestAPIView.post()` returns `uid` and `token` in the response body instead of only sending a reset link by email.

Impact:
- anyone who knows a registered email can request a reset token and potentially reset that account’s password

### W2. Email change verification token returned in API response body
`UpdateEmailAPIView.post()` returns `email_verification_token` in the response body.

Impact:
- a user can request an email change, receive the token directly, and complete verification without the new address actually receiving the email

### W3. Stripe webhook accepts arbitrary JSON when `STRIPE_WEBHOOK_SECRET` is unset
If the webhook secret is empty, raw JSON is accepted.

Impact:
- forged webhook events may create, upgrade, downgrade, cancel, or otherwise manipulate subscription state

### W4. Dormant `AllowAny` contract viewset exists in active package
`backend/api/contracts/views/payment_views.py` defines a `ContractViewSet` with:
- `permission_classes = [AllowAny]`
- `queryset = Contract.objects.all()`

Impact:
- not currently active, but dangerous enough that it should not exist in the codebase

### W5. Hardcoded secrets committed to source
`settings.py` contains:
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- hardcoded Django `SECRET_KEY`

Impact:
- secrets must be treated as exposed and rotated

### W6. `DEBUG = True` hardcoded with public IP in `ALLOWED_HOSTS`
`ALLOWED_HOSTS` includes a public server IP while `DEBUG` is hardcoded to `True`.

Impact:
- if this same settings file is used in production, debug mode may expose sensitive runtime information

### W7. Upload attachment to `ContractDocument` does not ownership-check the upload
Document attachment loads `Upload` by `pk` only, without checking `user=request.user`.

Impact:
- a contract party may attach another user’s upload to a contract document if they know the upload ID

## 4. High-Risk Findings

### H1 — Password reset is effectively an account takeover vector
File:
- `backend/api/users/views.py`

Impact:
- a valid reset token is disclosed directly in the API response
- this is a live functional security failure, not a hardening issue

### H2 — Stripe webhook accepts unsigned payloads when secret is unset
File:
- `backend/api/billing/views.py`

Impact:
- forged webhook requests may manipulate subscription state

### H3 — Hardcoded LiveKit secret committed to repository
File:
- `backend/core/settings.py`

Impact:
- anyone with repo access can generate valid session tokens and potentially join live negotiation sessions

### H4 — Dangerous unauthenticated contract viewset exists in live package
File:
- `backend/api/contracts/views/payment_views.py`

Impact:
- not active now, but too dangerous to leave in place

## 5. Medium-Risk Findings

### M1 — Email change token disclosure
The email verification token is returned directly in the API response.

### M2 — Upload IDOR on document attachment
A party to a contract can attach any upload object by ID, regardless of ownership.

### M3 — Obligation POST may allow arbitrary `obligor_id` / `obligee_id`
Current path appears to accept those values without clear validation that they belong to the contract parties.

### M4 — Verification flows are inconsistent
Some paths expose verification tokens directly while others do not.

### M5 — Invitation acceptance bypasses the normal pending-signup flow
Invitation acceptance appears to create a live user without going through the normal email-verification onboarding path.

### M6 — Documents / Workspace / Tools return successful placeholder responses
They are authenticated-only, but still behave like fake-success surfaces.

## 6. Low-Risk / Hygiene Findings

- hardcoded Django `SECRET_KEY`
- `DEBUG = True` not environment-gated
- console email backend not environment-gated
- obligations route double-registration
- debug-mode billing gate bypasses for some behaviors
- unvalidated `slide_url` broadcast in WebSocket flow
- dead dangerous file in `views/payment_views.py`
- inconsistent environment override patterns in settings

## 7. Business Entity Isolation Review

### Strong points
- entity list is owner-filtered
- entity detail/update/delete is owner-filtered
- entity creation limits are enforced server-side
- deletion is soft, not destructive

### Gap
Contracts are not actually tied to `BusinessEntity` by a true foreign key. They use `entity_type` as metadata.

Implication:
- business entity isolation is stronger in entity management than in contract ownership semantics
- contracts are not strongly owned by a `BusinessEntity` in a database-enforced way

## 8. Authority and Signing Review

### Strong points
- version creation is initiator-only
- signing is counterparty-only
- terminal statuses help prevent repeated or invalid actions
- state-machine logic exists in the engine

### Weakness
The current model is secure enough for the present two-party setup, but it is not extensible without changes.

Main concern:
- counterparty is stored as `counterparty_email`, not a foreign key to a user
- if email-change behavior is weak, party identity can become vulnerable

## 9. Contract Pro Security Readiness

The current system is **not yet ready** for safe Contract Pro introduction.

### What exists
- two-party role distinction already exists
- `is_party()` provides a basis for future permission refinement
- invitation structures exist
- `BusinessEntity` exists as a possible organizational boundary

### What is missing
- no third-role access model
- no ACL/permission table for delegated contract access
- no business-level or contract-level delegated-access schema
- no Contract Pro grant/revoke flow
- no Contract Pro-specific audit trail
- no safe extension of party checks to support delegated roles without risk of privilege leakage

### Conclusion
Contract Pro should not be added casually. It requires a deliberate delegated-access model.

## 10. Payment, Billing, and Webhook Review

### Strengths
- server-side billing gates
- atomic usage counter increments
- direct subscription mutation disabled when Stripe is active
- fallback logic exists for subscription lookup
- invoice sync uses idempotent patterns
- subscription sync uses transactions

### Weaknesses
- webhook safety collapses if `STRIPE_WEBHOOK_SECRET` is unset
- webhook handler acknowledges some failures too broadly
- some fallback logic may silently downgrade or normalize state

## 11. Uploads, Documents, and Session Access Review

### Uploads
Strong:
- list is user-scoped
- create sets `user=request.user`
- delete is owner-scoped
- storage key is user-namespaced

Weak:
- file content is not deeply validated
- contract/session associations on upload creation may not be party-validated
- upload ownership is not enforced when attaching an upload to a `ContractDocument`

### Documents
Strong:
- list and delete are party-checked through the contract

Weak:
- attachment path allows upload IDOR

### Sessions
Strong:
- HTTP session actions use party checks
- token issuance happens after permission checks
- initiator-only broadcast exists
- WebSocket auth + party check + active-session check happen before accept

Weak:
- `slide_url` is broadcast without validation

## 12. Exposed, Broken, or Placeholder Surface Review

### Contacts domain
- broken and unreachable
- not routed
- imports a deleted model class
- must be fixed or removed before ever being exposed

### Documents / Workspace / Tools
- placeholder-like
- protected by global auth
- low immediate risk, but confusing and should not be treated as real functionality

### Dangerous dormant files
- `backend/api/contracts/views/payment_views.py` should be deleted

### Duplicate routing
- obligations are mounted twice
- low direct security impact, but confusing and unnecessary

### Shadowed modules
- dead/shadowed files create maintenance and enforcement confusion

## 13. Unknowns Requiring Deeper Verification

- whether any alternate production-safe password-reset flow exists elsewhere
- whether `STRIPE_WEBHOOK_SECRET` is actually set in the deployed environment
- whether invitation acceptance creates all related profile objects safely
- whether infrastructure-level rate limiting exists
- whether CORS is handled outside code
- whether upload associations are consumed unsafely elsewhere
- whether obligation creation service validates obligor/obligee strictly
- whether production is actually running with `DEBUG = True`

## 14. Immediate Security Priorities

### Priority 1
Fix the password reset flow:
- stop returning reset tokens in API responses
- send real reset emails instead
- make reset token disclosure impossible

### Priority 2
Secure billing webhook behavior:
- require `STRIPE_WEBHOOK_SECRET`
- remove unsafe raw-JSON fallback for production
- verify environment config immediately

### Priority 3
Rotate and externalize secrets:
- rotate LiveKit secrets
- move LiveKit and Django secrets to environment variables
- gate debug and email backend through environment settings
- verify production is not in debug mode

### Priority 4
Delete dangerous dormant code:
- remove `views/payment_views.py`

### Priority 5
Remove token disclosure from email-change flow

### Priority 6
Fix upload ownership check in document attachment flow

### Priority 7
Fix or remove the broken contacts domain before it can ever be routed

## 15. Overall Blackboard Security Status

**Not ready**

### Why
Blackboard already has several real security strengths:
- coherent party-based access checks
- strong two-party signing rules
- server-side billing gates
- meaningful session/WebSocket protection

But it also has multiple functional security failures that block launch trust:

- password reset token disclosure
- webhook forgery risk when secret is unset
- hardcoded live credentials
- debug-mode production risk signal
- dangerous dormant unauthenticated contract viewset

These are not polish issues. They are real trust-breaking failures that must be fixed before Blackboard can be treated as security-ready.

## Summary

Blackboard’s core access-control model is stronger than it first appeared, but its current launch security is blocked by a small set of high-severity issues. The system is **not security-ready** until those are fixed.