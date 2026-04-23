# BLACKBOARD_PHASE1_SPRINT_01.md

> Status: Complete
> Scope: Blackboard phase-one Sprint 01
> Purpose: Record the first controlled batch of immediate trust-restoration fixes

## Sprint Goal

Sprint 01 focused on removing the most dangerous immediate trust breakers from the Blackboard backend so the repo became safer to continue building on.

This sprint covered only the highest-priority security hotfixes.

---

## Sprint 01 Items

### S1 — Fix Password Reset Token Disclosure
**Status:** Complete

#### Outcome
- password reset request no longer returns reset token or uid in API response
- reset flow now uses email delivery instead of response-body token disclosure
- generic anti-enumeration response is preserved

#### Verification
- automated tests passed
- manual/backend scenario verification confirmed:
  - response no longer leaks `uid` or `token`
  - reset link is sent through email backend

---

### S2 — Fix Stripe Webhook Unsafe Fallback
**Status:** Complete

#### Outcome
- unsafe raw-JSON fallback was removed
- missing webhook secret now fails safely
- verified webhook path remains intact

#### Verification
- billing tests passed
- focused webhook tests were added and passed

---

### S3 — Rotate Exposed Secrets Out of Tracked Source and Move Secrets to Environment Configuration
**Status:** Complete at code level

#### Outcome
- hardcoded `SECRET_KEY`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` were removed from tracked source
- settings now load them from environment
- `.env.example` was updated to document needed values

#### Verification
- recent tests passed
- tracked source no longer contains those hardcoded secret literals

#### Remaining operational follow-up
- rotate previously exposed LiveKit credentials
- rotate previously exposed Django `SECRET_KEY`
- consider git history cleanup if the repo was shared while secrets were committed

---

### S4 — Fix Debug / Production Settings Posture
**Status:** Complete

#### Outcome
- `DEBUG` is now environment-gated
- `EMAIL_BACKEND` is now environment-gated
- production posture is safer by default

#### Verification
- automated tests passed
- manual/backend scenario verification confirmed:
  - `DEBUG` is `False` by default
  - `DJANGO_DEBUG=True` turns it on explicitly

---

### S5 — Delete Dangerous Dormant `AllowAny` Contract Viewset
**Status:** Complete

#### Outcome
- dangerous dormant public contract view file was removed

#### Verification
- file removal confirmed
- active contract path remained unaffected
- manual verification confirmed the file is gone

---

### S6 — Fix Upload Ownership Hole in Document Attachment
**Status:** Complete

#### Outcome
- contract document attachment now requires upload ownership-safe lookup
- cross-user upload attachment is denied

#### Verification
- document tests passed
- manual/backend scenario verification confirmed:
  - one user cannot attach another user’s upload
  - no document is created in that scenario

---

## Sprint 01 Summary

Sprint 01 is complete.

### What Sprint 01 accomplished
- removed the dangerous dormant public contract view
- fixed password reset token disclosure
- fixed unsafe Stripe webhook fallback
- fixed upload ownership hole in document attachment
- removed hardcoded secret literals from tracked source
- fixed debug / email backend posture defaults

### Verification completed

#### Automated verification
- billing tests passed after Sprint 01 changes
- documents tests passed after Sprint 01 changes

#### Manual / backend scenario verification
- password reset no longer leaks token
- upload ownership fix works
- dangerous file is removed
- `DEBUG` is environment-controlled

### Remaining operational follow-up outside code
- rotate previously exposed LiveKit credentials
- rotate previously exposed Django `SECRET_KEY`
- consider git history cleanup if the repo was shared while secrets were committed

## Sprint Success Condition
Sprint 01 is closed.
The repo is ready to begin Sprint 02 after tracker/state files are updated.