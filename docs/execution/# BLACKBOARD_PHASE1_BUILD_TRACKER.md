# BLACKBOARD_PHASE1_BUILD_TRACKER.md

> Status: Working draft
> Scope: Blackboard phase-one live tracking board
> Purpose: Track execution of the Blackboard phase-one plan using concrete work items, dependencies, and status

## How to Use This Tracker

This tracker is the operational board for Blackboard phase one.

### Status values
- **Now** — should be worked on immediately
- **Next** — should be worked on after current items
- **Blocked** — cannot move until dependency is resolved
- **Done** — completed and verified
- **Deferred** — intentionally not active right now

### Priority values
- **P0** — immediate trust/launch blocker
- **P1** — critical stabilization item
- **P2** — important but not the first fix
- **P3** — lower urgency or dependent work

---

## Tracker Board

| ID | Workstream | Task | Priority | Status | Depends On | Done Condition |
|---|---|---|---|---|---|---|
| S1 | Security Hotfixes | Fix password reset token disclosure | P0 | Done | None | Reset token is no longer returned in API response; email-based reset flow implemented; verified |
| S2 | Security Hotfixes | Fix Stripe webhook unsafe fallback | P0 | Done | None | Webhook no longer accepts unsafe raw JSON fallback; missing secret fails closed; verified |
| S3 | Security Hotfixes | Rotate exposed secrets and move secrets to environment config | P0 | Done | None | Hardcoded secret literals removed from tracked source; env loading in place |
| S4 | Security Hotfixes | Fix debug / production settings posture | P0 | Done | None | `DEBUG` and related posture settings are environment-gated; verified |
| S5 | Security Hotfixes | Delete dangerous dormant `AllowAny` contract viewset | P0 | Done | None | Dormant dangerous file removed; no unsafe import path remains |
| S6 | Security Hotfixes | Fix upload ownership hole in document attachment flow | P0 | Done | None | Upload ownership is checked on attachment path; cross-user attachment denied; verified |
| C1 | Core Stabilization | Fix lifecycle automation path | P1 | Done | S1,S2,S3,S4,S5,S6 | `run_lifecycle` works cleanly; runner/service invocation mismatches fixed; tests added and passing |
| C2 | Core Stabilization | Resolve broken contacts path | P1 | Done | S1,S2,S3,S4,S5,S6 | Broken contacts domain clearly isolated; broken import removed; views stubbed with 501 responses |
| C3 | Core Stabilization | Clean dead/shadowed misleading modules | P1 | Done | S1,S2,S3,S4,S5,S6 | Three dead package-shadowed files deleted; verified unreachable; existing tests passing |
| C4 | Core Stabilization | Clean duplicate/confusing route registrations | P1 | Done | S1,S2,S3,S4,S5,S6 | Dead root URL config deleted; redundant obligations mount removed; duplicate route entry removed |
| C5 | Core Stabilization | Canonicalize contract/version flow | P1 | Done | C3,C4 | Live version path confirmed; broken engine-level service and inert test file marked with isolation headers |
| C6 | Core Stabilization | Canonicalize activation/payment/lifecycle paths | P1 | Done | C1,C3,C4,C5 | Live paths confirmed; four dead/misleading service files marked with isolation headers |
| A1 | Authority / Delegated Access | Define owner/signer/authorized representative model | P1 | Blocked | C5,C6 | Authority roles are explicitly defined for Blackboard |
| A2 | Authority / Delegated Access | Define negotiator vs signer distinction | P1 | Blocked | A1 | Negotiation rights and signing rights are explicitly separated |
| A3 | Authority / Delegated Access | Define Contract Pro delegated-access model | P1 | Done | A1,A2 | Contract Pro grant/revoke/scope/permissions model is defined |
| A4 | Authority / Delegated Access | Define delegated-access auditability requirements | P2 | Done | A3 | Contract Pro and other delegated actions have minimum audit expectations defined |
| A5 | Authority / Delegated Access | Review counterparty identity model | P2 | Done | A1,A2 | Current email-based counterparty approach is accepted with safeguards or scheduled for change |
| B1 | Boundary Confidence | Verify BusinessEntity isolation in multi-business scenarios | P1 | Blocked | C5,C6 | Multi-business owner tests confirm default business separation |
| B2 | Boundary Confidence | Verify owner-wide aggregation is explicit, not default | P2 | Blocked | B1 | Aggregation behavior is explicit and tested if present |
| B3 | Boundary Confidence | Harden uploads/documents boundaries | P1 | Blocked | S6,C6 | Upload/document ownership and contract-boundary behavior are tested and trusted |
| B4 | Boundary Confidence | Verify notification and activity scoping | P2 | Blocked | C6 | Notifications and activity flows are scoped safely and tested where needed |
| B5 | Boundary Confidence | Review session edge and broadcast hardening | P2 | Blocked | C6 | Session broadcast/input edge cases are reviewed and tightened |
| D1 | Domain Strengthening | Verify template instantiation end to end | P2 | Deferred | C5,C6 | Template instantiation works end to end and launch-ready subset is known |
| D2 | Domain Strengthening | Strengthen template family tests/confidence | P2 | Deferred | D1 | Template domains have enough confidence to count as real Blackboard launch surface |
| D3 | Domain Strengthening | Strengthen notification maturity | P2 | Deferred | B4 | Launch-critical notification behavior is clear and tested |
| D4 | Domain Strengthening | Strengthen activity/audit confidence | P2 | Deferred | B4 | Critical Blackboard lifecycle actions are traceable with sufficient confidence |
| D5 | Domain Strengthening | Clarify Blackboard role of uploads/documents | P2 | Deferred | B3 | Uploads/documents have a clear Blackboard-specific purpose and trusted behavior |
| D6 | Domain Strengthening | Decide whether workspace is truly phase-one scope | P2 | Deferred | C3,C4 | Workspace is either defined properly, narrowed, or explicitly deferred |
| D7 | Domain Strengthening | Improve admin/internal oversight confidence | P3 | Deferred | C6 | Admin surface is intentionally narrow, safe, and optionally better tested |
| F1 | Security Completion Standard | Define minimum security completion checklist for future features | P2 | Deferred | A1,A2,A3 | Blackboard has a repeatable feature-completion trust standard |
| F2 | Security Completion Standard | Define what counts as “security reviewed” | P2 | Deferred | F1 | Minimum evidence for future security review is documented |
| F3 | Security Completion Standard | Fold security completion standard into future build process | P3 | Deferred | F1,F2 | Future sensitive work cannot be marked complete without trust review |

---

## Now

A5 (counterparty identity model) complete (2026-04-27).
Email-only identity named as insufficient final contracting identity. Invite target vs real identity rule defined. Plan naming locked. Four implementation gaps named. Documented in `docs/current-state/BLACKBOARD_AUTHORITY_MODEL.md` Section 6.

Next scheduled work: Phase C Boundary Confidence items — B1 through B5.

---

## Next

Phase C Boundary Confidence items (B1–B5) are next per the Suggested Working Order.

See Suggested Working Order for the established sequencing. No items have been promoted or reprioritized here — that is a separate scheduling decision.

---

## Done

- **S1** Fix password reset token disclosure
- **S2** Fix Stripe webhook unsafe fallback
- **S3** Remove hardcoded secret literals from tracked source and move secrets to environment loading
- **S4** Fix debug / production settings posture
- **S5** Delete dangerous dormant `AllowAny` contract viewset
- **S6** Fix upload ownership hole in document attachment flow
- **C1** Fix lifecycle automation path
- **C2** Resolve broken contacts path
- **C3** Clean dead/shadowed misleading modules
- **C4** Clean duplicate/confusing route registrations
- **C5** Canonicalize contract/version flow
- **C6** Canonicalize activation/payment/lifecycle paths
- **A1** Define owner/signer/authorized representative model
- **A2** Define negotiator vs signer distinction
- **A3** Define Contract Pro delegated-access model
- **A4** Define delegated-access auditability requirements
- **A5** Review counterparty identity model

---

## Deferred

- **D1** through **D7**
- **F1** through **F3**

---

## Suggested Working Order

### Phase A — Trust restoration
- S1
- S2
- S3
- S4
- S5
- S6

### Phase B — Core stabilization
- C1
- C2
- C3
- C4
- C5
- C6

### Phase C — Authority and boundary work
- A1
- A2
- A3
- A4
- A5
- B1
- B2
- B3
- B4
- B5

### Phase D — Domain strengthening
- D1
- D2
- D3
- D4
- D5
- D6
- D7

### Phase E — Ongoing security discipline
- F1
- F2
- F3

---

## Summary

Sprint 01 (S1–S6) is complete and verified.
Sprint 02 (C1–C6) is complete and verified.
The backend is no longer carrying broken or misleading core paths.
A1, A2, A3 (Phase C authority definitions) are complete.
Contract Pro foundation implementation sprint complete (2026-04-27): backbone built, 59 tests passing.
A4 (delegated-access auditability requirements) complete (2026-04-27): minimum audit coverage defined.
A5 (counterparty identity model) complete (2026-04-27): email-only identity named insufficient; plan naming locked; four implementation gaps named.
Next: Phase C Boundary Confidence items (B1–B5).