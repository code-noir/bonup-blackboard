# Recommended Priorities

## Basis

These are recommendations based on inspected implementation, not claims of current behavior.

Requested priority order is preserved:

1. Review workflow
2. Counter workflow
3. Negotiation loop
4. State management
5. Dashboard clarity
6. Lifecycle continuity

## 1. Review Workflow

First priority: make contract review a real backend record.

Recommended work:

- Add a backend model for saved contract reviews or attach reviews to `AIConversation` with a structured result model.
- Persist analysis output server-side.
- Expose list/detail APIs for saved reviews.
- Update dashboard to fetch saved reviews from backend.
- Keep localStorage only as draft/autosave if needed.

Why first: it is the active user-facing workflow at `/review`, and current local-only saving limits continuity.

## 2. Counter Workflow

Second priority: connect counter generation to version creation.

Recommended work:

- Add explicit "Create contract version from revised contract" action.
- Enforce the 3-version Blackboard cap.
- Require user confirmation before creating a version.
- Preserve the AI output as review evidence.
- Remove or clearly retire legacy unreachable `Counter.tsx` save behavior.

Why second: counter generation currently produces useful text but does not enter the formal negotiation lifecycle.

## 3. Negotiation Loop

Third priority: clarify actual negotiation states.

Recommended work:

- Decide whether `sent` and `negotiating` are real states.
- Wire send/receive transitions if needed.
- Either implement `RequestChange` or remove/defer it from active mental models.
- Add notification creation for sent/rejected/signed/pending role switch events if product requires it.
- Avoid destructive role switch unless the owner explicitly accepts that behavior.

Why third: negotiation is core to Blackboard, but current behavior is narrower than model names imply.

## 4. State Management

Fourth priority: choose canonical state sources.

Recommended work:

- Define user-facing state mapping from `ContractVersion`, obligations, payments, and approvals.
- Stop relying on unused `Contract.status`/`state` fields unless they are actively maintained.
- Add tests for state transitions.
- Consider a service-level lifecycle state reader rather than duplicating state calculations in frontend.

Why fourth: dashboards and workflows cannot be clear until states are reliable.

## 5. Dashboard Clarity

Fifth priority: replace static dashboard sections with real data or honest empty states.

Recommended work:

- Fetch contracts from `/api/contracts/`.
- Fetch unread notifications from `/api/notifications/unread-count/`.
- Fetch saved reviews from the new review API once created.
- Add or build an aggregation endpoint for pending actions.
- Remove static sample contracts/payments/sessions from production UX.

Why fifth: dashboard is the user's operational entry point, and static data damages trust.

## 6. Lifecycle Continuity

Sixth priority: connect signed agreements to obligations and proof.

Recommended work:

- Decide how obligations are generated from signed contracts.
- Add due/overdue/default scheduling or state refresh jobs if required.
- Surface execution sessions, approvals, adjustments, and proof of work in the frontend.
- Tie lifecycle notifications to actual obligation/payment/session events.

Why sixth: lifecycle is the long-term product value, but it depends on the previous workflow/state foundations.

## AI System Separation

Recommended cross-cutting work:

- Extract AI provider client.
- Extract parsers.
- Move document prompts into prompt module.
- Validate AI action JSON with serializers/schemas.
- Add rate limiting and usage logging.
- Fix import billing gate ordering.

## Files Likely To Change First

- `backend/api/ai/views.py`
- `backend/ai/prompts.py`
- `backend/ai/models.py`
- `backend/api/ai/urls.py`
- `frontend/src/pages/ContractReview.tsx`
- `frontend/src/pages/Dashboard.tsx`
- new backend review model/API files if approved

## Files To Avoid Touching Without Explicit Approval

- `frontend/src/pages/CreateContract.tsx`
- migrations unless adding approved persistence
- settings/deployment files
- destructive role switch behavior without a dedicated task

