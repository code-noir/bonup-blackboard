# BLACKBOARD_PHASE1_EXECUTION_PLAN.md

> Status: Working draft  
> Scope: Blackboard phase-one execution control plan  
> Purpose: Convert the roadmap into concrete workstreams, tasks, dependencies, and done conditions

## How to Read This Plan

This document is not the same as the roadmap.

The roadmap explains **what order** matters.

This execution plan explains:
- what workstreams exist
- what tasks belong to each workstream
- what must happen before other work can begin
- what “done” means for each workstream

This document should be used to control the actual cleanup and build sequence for Blackboard phase one.

---

## Workstream A — Security Hotfixes

### Objective
Remove the immediate trust-breaking failures that block safe progress.

### Why this comes first
These issues are severe enough to make the repo unsafe to treat as stable working ground if left unresolved.

### Tasks

#### A1. Fix password reset flow
- stop returning password reset token in API response
- implement real email-based password reset delivery
- ensure reset confirmation only works through properly delivered token flow
- add tests for safe reset behavior

#### A2. Fix Stripe webhook unsafe fallback
- remove raw JSON fallback when webhook secret is missing
- require signature verification in production-safe code path
- fail closed when webhook secret is unset
- add tests for rejection of unsigned payloads

#### A3. Rotate and externalize secrets
- rotate exposed LiveKit credentials
- review whether Django secret must also be rotated
- move secrets to environment configuration
- remove hardcoded credential usage from source
- document required environment variables

#### A4. Fix debug and production settings posture
- environment-gate `DEBUG`
- environment-gate email backend
- review production-sensitive settings
- verify production server is not using unsafe debug posture

#### A5. Delete dangerous dormant contract viewset
- remove `AllowAny` dormant viewset
- verify router/import path cannot accidentally expose it later
- scan for similar dormant dangerous files

#### A6. Fix upload ownership hole in document attachment
- require ownership-safe retrieval of upload objects
- prevent attaching other users’ uploads by ID
- add tests for cross-user denial

### Dependencies
None. This is the first workstream.

### Done Condition
This workstream is done when:
- no known trust-breaking security failure from Tier 1 remains
- secrets are no longer hardcoded
- dangerous dormant public contract exposure path is gone
- password reset and webhook behavior are safe by design
- document attachment ownership is enforced

---

## Workstream B — Core Stabilization

### Objective
Repair broken core paths and make the current backend less misleading, less contradictory, and easier to trust.

### Why this comes second
After immediate security blockers are fixed, the next need is coherence.

### Tasks

#### B1. Fix lifecycle automation
- repair kwargs/signature mismatch
- verify `run_lifecycle` actually runs
- test or manually verify expected lifecycle execution behavior
- stop calling lifecycle automation “working” until confirmed

#### B2. Resolve broken contacts path
- decide whether to remove, repair, or isolate the contacts domain
- eliminate import of deleted model class
- prevent future confusion about contacts being a live domain when it is not

#### B3. Clean dead/shadowed misleading modules
- identify dead modules that look active
- identify shadowed modules that future work could mistakenly edit
- remove or clearly mark them

#### B4. Clean duplicate/confusing routes
- remove duplicate obligations route registration
- verify one canonical route surface per domain
- reduce route ambiguity

#### B5. Canonicalize contract/version flow
- identify live version creation path
- identify live sign/reject path
- identify broken version-service path and decide whether to fix or deprecate it
- document canonical version flow

#### B6. Canonicalize activation/payment/lifecycle paths
- choose one activation path
- choose one payment path
- choose one lifecycle path
- remove or mark competing paths

### Dependencies
- Workstream A should be substantially complete first

### Done Condition
This workstream is done when:
- lifecycle automation is either fixed or explicitly disabled
- broken legacy contact state no longer pollutes repo truth
- duplicate and shadowed core paths are cleaned or explicitly deprecated
- there is one documented canonical flow for versioning, activation, payment, and lifecycle

---

## Workstream C — Authority and Delegated Access Design

### Objective
Define the backend truth for authority, signing, and delegated contract access before building more sensitive collaboration behavior.

### Why this comes third
Blackboard already needs clearer authority semantics. Contract Pro cannot be safely introduced without this work.

### Tasks

#### C1. Define owner/signer/authorized-representative model
- define who is owner
- define who can sign by default
- define how explicit delegated signing authority works
- define what backend data/logic carries authority truth

#### C2. Define negotiator vs signer distinction
- define what negotiation rights mean
- define what negotiation does not imply
- ensure negotiation never silently becomes signing authority

#### C3. Define Contract Pro
- define how Contract Pro is granted
- define who can grant it
- define business-scoped vs contract-scoped access
- define what Contract Pro can do
- define what Contract Pro cannot do
- define revoke behavior
- define audit expectations

#### C4. Define delegated-access auditability
- identify what delegated actions must be traceable
- define minimum audit trail for Contract Pro and other delegated roles
- define what authority-changing events must be recorded

#### C5. Review counterparty identity model
- assess whether `counterparty_email` is acceptable for phase one
- define temporary safeguards if retained
- define migration direction if stronger party identity is needed later

### Dependencies
- Workstream B should be substantially complete enough that the live paths are clear

### Done Condition
This workstream is done when:
- Blackboard has a documented authority model
- Contract Pro is defined as a delegated-access role, not just a vague concept
- negotiation rights and signing rights are clearly separated
- authority-sensitive backend rules can be implemented against a clear model

---

## Workstream D — Boundary Confidence and Access Hardening

### Objective
Prove that Blackboard respects user, business, and resource boundaries in the places that matter most.

### Why this comes now
After security hotfixes and path cleanup, the next trust layer is enforcing and proving correct boundaries.

### Tasks

#### D1. Verify business entity isolation
- test one-owner / multiple-business scenarios
- verify default separation across contracts
- verify separation across sessions
- verify separation across payments
- verify separation across activity
- verify separation across search results

#### D2. Verify owner-wide aggregation behavior
- determine whether any owner-wide aggregation exists
- ensure it is explicit and not default
- ensure aggregation does not silently break business boundaries

#### D3. Harden upload/document boundaries
- verify upload create/list/delete boundaries
- verify document list/retrieve/delete boundaries
- verify contract-linked attachments respect both party and ownership rules

#### D4. Verify notification and activity scoping
- review whether users can only see their own relevant notifications
- review whether activity visibility respects contract/entity/user boundaries
- add tests if weak

#### D5. Review session access and edge cases
- verify participant boundaries
- verify token issuance safety
- review any client-controlled fields in session broadcast/update behavior

### Dependencies
- Workstream A complete
- Workstream B mostly complete

### Done Condition
This workstream is done when:
- business boundary behavior is explicitly verified
- upload/document/resource boundaries are tested and trusted
- notification/activity/session access rules are no longer uncertain

---

## Workstream E — Blackboard In-Scope Domain Strengthening

### Objective
Strengthen Blackboard phase-one domains that are real but still partial, thin, or under-trusted.

### Why this comes after the trust layer
These domains matter, but they should be improved after immediate security and coherence problems are under control.

### Tasks

#### E1. Template confidence
- verify template instantiation end to end
- identify launch-ready template subset
- strengthen test coverage
- clarify which template paths are real vs thin

#### E2. Notification maturity
- confirm launch-critical notification flows
- strengthen endpoint confidence
- make notification behavior intentional, not just incidental

#### E3. Activity confidence
- confirm sufficient trace coverage for Blackboard launch
- strengthen tests where needed
- ensure activity meaning is clear in contract lifecycle context

#### E4. Uploads/documents maturity
- clarify Blackboard-specific role
- decide whether uploads/documents are only support infrastructure or a visible feature surface
- strengthen behavior accordingly

#### E5. Workspace decision
- decide whether workspace is truly Blackboard phase-one scope
- if yes, define what it actually means
- if no, stop pretending placeholder scaffolding counts as meaningful completion

#### E6. Admin/internal oversight improvements
- verify admin endpoints remain narrow and safe
- add targeted tests if needed
- keep this support-focused, not feature-sprawling

### Dependencies
- Workstreams A through D should be far enough along that the system is trustworthy enough to strengthen partial domains without building on bad ground

### Done Condition
This workstream is done when:
- the weaker in-scope Blackboard domains are either strengthened, explicitly narrowed, or intentionally deferred
- no partial domain is being mistaken for launch-ready without evidence

---

## Workstream F — Security Completion Standard

### Objective
Create a repeatable rule so future Blackboard features cannot be called complete without trust review.

### Why this matters
Without this, the project can drift back into “feature exists, therefore done” thinking.

### Tasks

#### F1. Define completion checklist for future Blackboard features
Every sensitive feature should be reviewed for:
- authentication
- authorization
- ownership/resource scoping
- business/entity boundary behavior if relevant
- authority/signature behavior if relevant
- delegated-access behavior if relevant
- auditability if sensitive
- production-config implications if relevant

#### F2. Define what “security reviewed” means
- determine minimum evidence
- determine when tests are required
- determine when manual inspection is enough
- determine when environment/config review is required

#### F3. Fold trust review into phase-one process
- ensure no future feature is marked complete without security review
- ensure role/authority-sensitive changes are reviewed against authority model
- ensure new domains do not bypass the baseline

### Dependencies
- Workstream C should exist first so authority-sensitive review has a real model
- Workstream A security blockers should already be fixed

### Done Condition
This workstream is done when:
- Blackboard has a repeatable definition of secure-enough feature completion
- future work no longer relies on vague trust assumptions

---

## Execution Order Summary

### Phase A — Trust Restoration
- Workstream A

### Phase B — Core Stabilization
- Workstream B

### Phase C — Authority Definition
- Workstream C

### Phase D — Boundary Confidence
- Workstream D

### Phase E — Domain Strengthening
- Workstream E

### Phase F — Ongoing Security Discipline
- Workstream F

---

## What This Plan Means

Blackboard phase one does not need to be rebuilt from scratch.

But it also should not move forward as if the current backend is already coherent, trustworthy, and launch-ready.

The right execution logic is:

1. remove the immediate trust breakers
2. stabilize the real live core
3. define authority and delegated access
4. prove the system respects its boundaries
5. strengthen the weaker in-scope domains
6. establish a repeatable trust standard for future work

---

## Summary

This execution plan turns the current truth into real work.

The most important execution truth is:

> Blackboard phase one should move through controlled workstreams: immediate trust repair first, core stabilization second, authority design third, boundary confidence fourth, and only then broader strengthening of weaker in-scope Blackboard domains