# BLACKBOARD_PHASE1_ROADMAP.md

> Status: Working draft  
> Scope: Blackboard phase-one execution roadmap  
> Purpose: Convert current repo truth, scope truth, and security truth into one practical build order

## How to Read This Roadmap

This roadmap is not the full bonUP roadmap.

It is the **Blackboard phase-one roadmap** only.

It combines:
- current backend reality
- Blackboard phase-one scope
- security review findings
- hotfix priorities
- missing role/authority work
- stabilization and cleanup work

This roadmap is organized into five execution lanes:

- **Fix now** — trust-breaking issues and broken core paths
- **Stabilize next** — make the current backend coherent and safer
- **Define before building more** — authority and delegated-access design work that must be clear first
- **Build after stabilization** — real Blackboard phase-one features that are in scope but still weak/partial
- **Defer** — not Blackboard phase-one or not worth touching yet

---

## 1. Fix Now

These items should be handled before the project is treated as safe and stable working ground.

### 1.1 Security hotfixes
These are the highest-priority blockers.

- fix password reset token disclosure
- fix Stripe webhook unsafe fallback
- rotate exposed secrets and move secrets to environment configuration
- fix debug / production settings posture
- delete dangerous dormant `AllowAny` contract viewset
- fix upload ownership hole in document attachment flow

### 1.2 Broken lifecycle automation
Lifecycle automation is part of Blackboard phase-one truth and is currently broken.

- fix the kwargs/signature mismatch in lifecycle automation path
- verify the CLI lifecycle path actually runs cleanly
- do not count lifecycle automation as working until verified

### 1.3 Broken legacy/bad signals
These are not all catastrophic by themselves, but they poison trust in the repo.

- fix or remove broken contacts path
- remove or clearly isolate dead/shadowed misleading files
- remove duplicate/confusing route registrations
- clean obviously dangerous dormant modules

### 1.4 Immediate settings/config safety
These should be part of the same hotfix window.

- gate `DEBUG` by environment
- gate email backend by environment
- gate production-sensitive settings by environment
- verify production server posture explicitly

---

## 2. Stabilize Next

After the immediate hotfixes, the next goal is coherence.

### 2.1 Canonicalize contract core flows
Blackboard contract behavior should not continue to live through multiple competing paths.

- choose one canonical contract versioning path
- choose one canonical activation path
- choose one canonical payment path
- choose one canonical lifecycle path
- document those choices in the repo

### 2.2 Business entity isolation confidence
`BusinessEntity` exists, but phase-one trust requires stronger proof.

- test one-owner / multi-business behavior
- verify default business-level separation
- verify contract/session/payment/activity/search scoping
- ensure owner-wide aggregation is explicit, not default

### 2.3 Uploads/documents hardening
These are in scope for Blackboard and need more confidence.

- fix upload/document ownership boundaries
- verify safe attachment flows
- add permission tests
- decide Blackboard-specific purpose of uploads/documents clearly

### 2.4 Cleanup of placeholder surfaces
Placeholder surfaces should not keep pretending to be meaningful product completion.

- review `workspace`
- review `tools`
- review placeholder `documents` API behavior
- remove, lock down, or clearly mark non-production placeholder paths

### 2.5 Clean false architecture signals
- remove stale/dead modules that look canonical but are not
- reduce duplicate implementations where possible
- make the current live path obvious to future work

---

## 3. Define Before Building More

These items are too sensitive to improvise later.

### 3.1 Contract Pro
Contract Pro is in Blackboard phase one, but it must be designed before implementation.

Must define:
- how Contract Pro is granted
- who can grant it
- business-scoped vs contract-scoped access
- what Contract Pro can do
- what Contract Pro cannot do
- whether Contract Pro can draft, negotiate, view, comment, approve, or only some subset
- how Contract Pro is revoked
- how Contract Pro activity is audited

### 3.2 Authority and signature model
Blackboard needs a clean backend truth for:
- owner
- signer
- authorized representative
- negotiator
- Contract Pro
- possible future delegated roles

Must define:
- default signer rules
- delegated signer rules
- explicit written authority model
- where authority lives in the backend schema/logic
- how server-side enforcement happens

### 3.3 Counterparty identity model
The current email-based counterparty design is workable for now, but fragile.

Must define:
- whether phase one keeps it temporarily
- how it is hardened if kept
- whether it needs a stronger identity linkage later
- how email-change behavior interacts with party identity

### 3.4 Security completion standard
Before more sensitive features are built, Blackboard should have a rule that no feature is called complete without:
- auth review
- authorization review
- ownership review
- entity-boundary review if relevant
- authority review if relevant
- auditability review if sensitive

---

## 4. Build After Stabilization

These are in-scope Blackboard phase-one items that should move forward after the hotfix and stabilization layers are handled.

### 4.1 Template confidence and readiness
Templates are already partially present and should be brought to stronger phase-one confidence.

- verify template instantiation end to end
- identify launch-ready template subset
- improve tests for template families
- reduce thin/ambiguous template behavior

### 4.2 Notification maturity
Notifications exist, but confidence is weaker than the strongest domains.

- verify notification list/read behavior
- verify notification scoping
- define which notification flows are truly phase-one critical
- strengthen tests where needed

### 4.3 Activity/audit confidence
Activity logging exists and is useful, but launch trust may require stronger confidence.

- verify activity scoping by user/entity/business
- verify critical actions are captured
- identify gaps for sensitive events

### 4.4 Workspace, only if still truly in scope
Workspace is currently weak/placeholder-like.

Do not build this blindly.

First decide:
- what Blackboard phase-one actually means by workspace
- whether existing behaviors already cover the real need
- whether workspace is launch-critical or can remain thin

### 4.5 Admin/internal oversight improvements
Lower priority than the contract/security core, but still useful.

- verify admin endpoint safety
- add targeted tests if needed
- keep admin scope intentionally narrow

---

## 5. Protect What Already Works

These areas are already among the strongest parts of Blackboard and should be treated carefully.

### 5.1 Billing
- protect billing gates
- do not casually refactor Stripe/webhook logic without controlled review
- keep subscription logic stable while fixing unsafe fallback behavior

### 5.2 Sessions
- keep session access rules stable
- avoid breaking WebSocket auth and party checks
- harden edges without destabilizing the core

### 5.3 SOL
- treat SOL as a real Blackboard domain
- avoid casually destabilizing a domain that already has meaningful shape and tests
- clarify how it is presented through Blackboard

### 5.4 Search
- keep search stable
- later verify entity/business scoping thoroughly
- do not treat search breadth as a reason to refactor prematurely

### 5.5 Execution / approvals / adjustments
This is one of the cleanest architecture zones and should be protected.

- keep this flow stable
- use it as a reference for cleaner Blackboard patterns going forward

---

## 6. Defer

These items should not distract Blackboard phase-one execution.

### 6.1 Out of Blackboard phase one
These belong to broader bonUP / PBVD scope, not Blackboard phase one.

- formal PBVD subsystem
- PBVD verification / registration / certificate model
- Studjo
- storage billing / storage entitlement
- general creator monetization
- broader user-owned content platform systems

### 6.2 Nice-to-have but not urgent now
- deeper architectural elegance work that does not improve real trust or launch readiness
- speculative refactors of already-stable domains
- low-value cleanup that does not reduce risk or confusion

---

## 7. Phase-One Execution Order

### Phase A — Trust Restoration
Handle the biggest trust breakers first.

- password reset fix
- webhook fallback fix
- secret rotation / env migration
- debug/settings posture fix
- delete dangerous dormant code
- fix upload ownership hole
- fix lifecycle automation
- clean broken contacts path

### Phase B — Coherence Restoration
Make Blackboard’s backend stop contradicting itself.

- canonicalize contract/version/activation/payment/lifecycle paths
- clean dead/shadowed modules
- clean duplicate routes
- reduce false architecture signals

### Phase C — Boundary Confidence
Prove Blackboard respects the boundaries it claims.

- business entity isolation verification
- upload/document access confidence
- notification/activity scoping review
- counterparty identity review

### Phase D — Authority Definition
Define what Blackboard means by authority before expanding delegated roles.

- authority/signature model
- Contract Pro model
- delegated-access rules
- audit expectations

### Phase E — In-Scope Phase-One Strengthening
Strengthen partial Blackboard domains after the trust and authority base is repaired.

- templates
- notifications
- workspace if still truly in scope
- admin/internal oversight

---

## 8. What This Roadmap Means

Blackboard phase one is not blocked because nothing exists.

It is blocked because:
- some critical security failures exist
- some core paths are duplicated or misleading
- some important authority/boundary systems are not formalized yet

That means the work now is not “build everything from zero.”

The work now is:
- repair the trust layer
- stabilize the core
- define authority and delegated access
- then strengthen the real in-scope phase-one subsystems

---

## 9. Summary

Blackboard phase one already has a serious amount of real backend work in place:
- contract core
- lifecycle structures
- billing
- sessions
- SOL
- search
- execution/approval mechanics

The next step is not more broad discovery.

The next step is disciplined sequencing.

The most important roadmap truth is:

> Blackboard phase one should move forward by fixing immediate trust failures first, stabilizing the real core second, defining authority and Contract Pro before expanding sensitive access, and only then strengthening the weaker in-scope domains.