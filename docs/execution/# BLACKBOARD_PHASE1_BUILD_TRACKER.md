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
| A1 | Authority / Delegated Access | Define owner/signer/authorized representative model | P1 | Done | C5,C6 | Authority roles are explicitly defined for Blackboard |
| A2 | Authority / Delegated Access | Define negotiator vs signer distinction | P1 | Done | A1 | Negotiation rights and signing rights are explicitly separated |
| A3 | Authority / Delegated Access | Define Contract Pro delegated-access model | P1 | Done | A1,A2 | Contract Pro grant/revoke/scope/permissions model is defined |
| A4 | Authority / Delegated Access | Define delegated-access auditability requirements | P2 | Done | A3 | Contract Pro and other delegated actions have minimum audit expectations defined |
| A5 | Authority / Delegated Access | Review counterparty identity model | P2 | Done | A1,A2 | Current email-based counterparty approach is accepted with safeguards or scheduled for change |
| B1 | Boundary Confidence | Verify BusinessEntity isolation in multi-business scenarios | P1 | Done | C5,C6 | Multi-business owner tests confirm default business separation |
| B2 | Boundary Confidence | Verify owner-wide aggregation is explicit, not default | P2 | Done | B1 | Aggregation behavior is explicit and tested if present |
| B3 | Boundary Confidence | Harden uploads/documents boundaries | P1 | Done | S6,C6 | Upload/document ownership and contract-boundary behavior are tested and trusted |
| B4 | Boundary Confidence | Verify notification and activity scoping | P2 | Done | C6 | Notifications and activity flows are scoped safely and tested where needed |
| B5 | Boundary Confidence | Review session edge and broadcast hardening | P2 | Done | C6 | Session broadcast/input edge cases are reviewed and tightened |
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

## bonUP Foundation Layer (AG sequence)

The AG sequence is defined in `docs/current-state/BONUP_AUTHORITY_FOUNDATION_SPEC.md`. These steps are tracked separately from the S/C/A/B/D/F workstreams.

| Step | Description | Status | Commit |
|---|---|---|---|
| AG1 | Introduce `Soul` model in new `bonup/` app | Done | `1cbfd11` |
| AG2a | Introduce `Entity` + `SoulEntity` models — additive; AG8 folded into same commit | Done | `4768fe3` |
| AG2b | Add nullable `BusinessEntity.entity` OneToOneField + data backfill | Done | `4e8261f` |
| AG3 | Migrate `Contract.entity_type` flat field to `Contract.entity` FK pointing to `Entity` | Deferred | — |
| AG4 | Introduce `AuthorityHolder` relation model | Deferred | — |
| AG5 | Migrate `BusinessEntity.owner` → `AuthorityHolder` record | Deferred | — |
| AG6 | Migrate Contract Pro grant anchor from `BusinessEntity` to `Entity` | Deferred | — |
| AG7 | Generalize `ContractProAccessGrant` as `AppointedAuthority` subtype or migrate to `AuthorityHolder` + `Entity` anchor | Deferred | — |
| AG8 | Introduce `SoulEntity` as personal operating surface record — introduced with AG2a | Done | `4768fe3` |
| AG9 | Introduce `Operator` role model | Deferred | — |

---

## Now

Phase C Boundary Confidence items (B1–B5) complete (2026-04-27).
Boundary layer verified. Two real bugs found and fixed: cross-owner BusinessEntity attachment (B1 inspection, separate commit) and cancelled-session-can-be-ended state machine gap (B5). All other paths verified by targeted tests.

bonUP Foundation Layer: AG1 (Soul), AG2a/AG8 (Entity/SoulEntity), and AG2b (BusinessEntity→Entity pointer) complete (2026-04-28). See AG sequence section above.

---

## Next

Domain Strengthening (D-series) is the next phase per the Suggested Working Order.
All D items are currently Deferred. No items promoted yet — that is a separate scheduling decision.

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
- **B1** Verify BusinessEntity isolation in multi-business scenarios
- **B2** Verify owner-wide aggregation is explicit, not default
- **B3** Harden uploads/documents boundaries
- **B4** Verify notification and activity scoping
- **B5** Review session edge and broadcast hardening
- **AG1** Introduce Soul model in new `bonup/` app
- **AG2a/AG8** Introduce Entity and SoulEntity models (additive; same commit)
- **AG2b** Add BusinessEntity→Entity OneToOneField pointer with data backfill

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
Phase C Boundary Confidence (B1–B5) complete (2026-04-27): boundary layer verified; cross-owner entity attachment bug fixed; cancelled-session end bug fixed; targeted tests added for all five items.
bonUP Foundation Layer AG sequence begun (2026-04-28): AG1 (Soul), AG2a/AG8 (Entity/SoulEntity), and AG2b (BusinessEntity→Entity pointer) complete. AG3–AG9 deferred. See `docs/current-state/BONUP_AUTHORITY_FOUNDATION_SPEC.md` for full sequence.
Next: Domain Strengthening (D-series), all currently Deferred.