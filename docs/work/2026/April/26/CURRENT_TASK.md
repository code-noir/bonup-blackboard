# CURRENT_TASK.md

Status: Active

## Date
2026-04-23

## Sprint
Sprint 01 — Security Hotfixes

## Task ID
SPRINT_01_CLOSEOUT

## Task Name
Close Sprint 01 in the repo docs and finalize structure cleanup

## Why this is the current task
Sprint 01 code work is complete and key verification has already been done.
However, Sprint 01 is not fully closed in the repo docs yet, and the repo/document structure still needs cleanup before handoff or Sprint 02 work begins.

## Goal
Bring the repo documentation and folder structure into alignment with the completed Sprint 01 work.

## What must be done
- update `docs/sprints/BLACKBOARD_PHASE1_SPRINT_01.md`
- update `docs/execution/BLACKBOARD_PHASE1_BUILD_TRACKER.md`
- confirm the new doc/work folder structure is correct
- make sure Sprint 01 is marked complete and verified
- do not start Sprint 02 implementation until this closeout is finished

## Sprint 01 completed fixes
- S1 fixed password reset token disclosure
- S2 fixed Stripe webhook unsafe fallback
- S3 removed hardcoded `SECRET_KEY`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` from tracked source and moved them to environment loading
- S4 fixed `DEBUG` and `EMAIL_BACKEND` posture to be environment-gated
- S5 deleted the dangerous dormant `AllowAny` contract viewset
- S6 fixed upload ownership hole in contract document attachment

## Verification already completed

### Automated verification
- billing tests passed after Sprint 01 changes
- documents tests passed after Sprint 01 changes

### Manual / backend scenario verification
- password reset no longer leaks token
- upload ownership fix works
- dangerous file is removed
- `DEBUG` is environment-controlled

## Remaining operational follow-up outside code
- rotate previously exposed LiveKit credentials
- rotate previously exposed Django `SECRET_KEY`
- consider git history cleanup if the repo was shared while secrets were committed

## Success condition
- Sprint 01 sprint file is updated
- build tracker is updated
- folder structure is clean enough for handoff
- Sprint 01 is clearly closed in the repo