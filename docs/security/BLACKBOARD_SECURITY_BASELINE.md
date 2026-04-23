# BLACKBOARD_SECURITY_BASELINE.md

> Status: Working draft  
> Scope: Minimum phase-one security standard for Blackboard backend/system  
> Purpose: Define the security baseline Blackboard must meet before launch readiness is claimed

## 1. Security Position

Security is a phase-one foundation of Blackboard.

Blackboard is not just a document app. It handles:
- contracts
- identities
- business entities
- negotiations
- obligations
- approvals
- payment state changes
- subscription and billing state
- live sessions
- uploads/documents
- SOL-related financial structures

Because of that, Blackboard must be treated as a system that requires serious trust protection, even if it is not operating at the scale of the largest platforms.

The goal is not to pretend Blackboard already has Google- or Meta-level security maturity. The goal is to build Blackboard so that:
- unauthorized access is hard
- weak backend boundaries do not create easy sabotage
- secrets are protected
- role and authority rules are enforced
- business data stays separated correctly
- sensitive actions are traceable
- dead or placeholder paths do not remain open as attack surfaces

Security is not a later polish pass. Security is part of feature completion.

## 2. Phase-One Security Goals

Blackboard phase one should guarantee, at minimum:

1. users cannot access records that do not belong to them
2. one business entity cannot see another business entity’s records by default
3. sensitive actions require the right actor, role, and authority
4. contract negotiation rights do not automatically become signing rights
5. Contract Pro access is explicit, scoped, and revocable
6. payments and billing flows do not trust unsafe client-side assumptions
7. secrets are not committed, exposed, or casually reused
8. uploads and document flows do not become unsafe entry points
9. broken, dead, or placeholder endpoints do not remain casually exposed
10. security-relevant actions are logged or at least traceable
11. production settings do not remain in a weak development posture
12. the system has a documented minimum security standard before launch

## 3. Core Security Domains

### 3.1 Authentication

Blackboard must have strong authentication behavior.

Minimum expectation:
- JWT authentication is enforced on protected endpoints
- refresh and logout behavior works correctly
- email verification is enforced where intended
- protected endpoints are not accidentally anonymous
- admin-only surfaces remain admin-only

Current reality:
- JWT auth exists
- email verification before token issuance exists
- admin-only protection exists on admin endpoints

Security requirement:
- keep auth behavior explicit
- review token lifetime/refresh/logout behavior before launch
- confirm there are no accidental unauthenticated surfaces except those intentionally public, such as required billing webhook entry points

### 3.2 Authorization

Authentication is not enough. Blackboard must also enforce correct authorization.

Minimum expectation:
- resource ownership checks exist
- role-based access checks exist
- contract-scoped permissions are enforced
- business-scoped permissions are enforced
- approval/signature authority checks are enforced

This matters for:
- contracts
- contract versions
- approvals
- role switches
- sessions
- uploads/documents
- SOL actions where relevant
- admin routes

Current reality:
- there is evidence of ownership/access-control testing in some areas
- role-aware signing exists
- state-machine enforcement exists in contract/version/payment flows

Security requirement:
- no major flow should be treated as complete until its authorization model is explicit and verified

### 3.3 Business Entity Isolation

Blackboard must support one owner managing multiple businesses while keeping those businesses separate by default.

This is a foundational security rule, not just a UI preference.

Minimum expectation:
- contracts created under Business A stay under Business A by default
- activities, sessions, payments, searches, and related records do not silently bleed across businesses
- owner-wide views, if allowed, must be explicit
- default behavior must preserve business boundary separation

Current reality:
- `BusinessEntity` is real and linked into the contract model
- the domain is present, but not yet one of the most trusted/tested backend areas

Security requirement:
- multi-business-owner behavior must be tested explicitly
- entity scoping must be reviewed across list, retrieve, search, activity, payment, and session flows
- owner aggregation must never be mistaken for default scoping

### 3.4 Authority and Signature Integrity

Blackboard must distinguish clearly between:
- owner
- signer
- authorized representative
- negotiator
- delegated contract actor

By default, final signing authority should remain with the owner or the explicitly authorized signer.

Minimum expectation:
- negotiation does not automatically imply signing authority
- signer authority is explicit
- role and signer checks are not ambiguous
- final activation depends on valid authority, not just workflow completion

Current reality:
- version signing/rejection and state enforcement are real
- broader authority semantics are not yet clearly implemented as a complete backend rule system

Security requirement:
- authority must be encoded as a formal backend rule set, not left implicit in UI behavior or assumptions

### 3.5 Contract Pro Access and Delegated Authority

Contract Pro is a security-sensitive role inside Blackboard.

Contract Pro is not merely a convenience label. A Contract Pro represents delegated access into contract-related business activity. That means Contract Pro belongs inside the security and trust model.

Minimum expectation:
- a user does not become a Contract Pro by accident or implication
- Contract Pro access is explicitly granted
- Contract Pro access is scoped to the relevant business, not global by default
- Contract Pro permissions are clearly defined
- negotiation rights and signing rights are separate
- Contract Pro does not automatically gain final signing authority
- if signing authority is granted, it is explicit and traceable
- Contract Pro access is revocable
- Contract Pro actions are auditable

Blackboard phase one must answer:
- how is Contract Pro access granted
- who can grant it
- whether it is business-wide or contract-specific
- what exact permissions it includes
- what exact permissions it excludes
- how revocation works
- how delegated actions are logged

Current reality:
- Contract Pro is not yet visible as a first-class backend subsystem in the current backend audit
- authority/role structure is therefore incomplete from a security standpoint

Security requirement:
- Contract Pro must be treated as both a product role and a delegated-access security role

### 3.6 Billing and Payment Safety

Billing and payment flows must resist misuse and false claims.

Minimum expectation:
- payment state transitions are validated
- state changes are not accepted from arbitrary invalid states
- idempotency is respected where intended
- billing truth is not determined by client-side claims
- webhook verification is enforced
- billing gates remain server-side enforced

Current reality:
- payment state transitions are real and tested
- billing, checkout, portal, webhooks, trials, and gates are real and heavily tested
- billing is one of the strongest backend areas

Security requirement:
- keep billing/payments among the most protected areas
- confirm webhook verification and production secret handling before launch
- avoid weakening billing logic through convenience shortcuts

### 3.7 Upload and Document Safety

Uploads and documents are a potential attack surface.

Minimum expectation:
- upload access respects ownership and scope
- file access is not casually open
- allowed file types and size limits are defined
- uploaded files are not assumed to be harmless
- storage references are controlled
- document attachments do not bypass contract/entity/user boundaries

Current reality:
- uploads and documents are real in backend shape
- they are less trusted than stronger domains because test confidence and maturity are weaker

Security requirement:
- uploads/documents must be reviewed explicitly before launch
- placeholder maturity should not be mistaken for security readiness

### 3.8 API Surface Hardening

Every routed path is part of the attack surface.

Minimum expectation:
- broken legacy routes are removed or kept safely unrouted
- placeholder endpoints are removed, locked down, or clearly non-production
- duplicate routes are reviewed
- shadowed or dead files do not create ambiguity about which logic is real
- dead code is not left callable accidentally

Current reality:
- `contacts` is broken and unrouted
- `workspace` and `tools` look placeholder-like
- obligations routing is duplicated
- at least one contract views module is dead/shadowed

Security requirement:
- reduce exposed ambiguity
- remove or lock down non-real surfaces
- treat dead/broken paths as security debt, not just code clutter

### 3.9 Auditability and Traceability

Sensitive actions should be explainable after the fact.

Minimum expectation:
- contract creation is traceable
- signing/rejection is traceable
- approvals/disputes are traceable
- payment state changes are traceable
- delegated actions are traceable
- security-sensitive transitions are not silent

Current reality:
- activity logging exists
- notification hooks exist
- some sensitive flows already produce trace-like records

Security requirement:
- confirm coverage of audit-worthy actions
- ensure Contract Pro and authority-sensitive actions become traceable when introduced

### 3.10 Secrets and Environment Management

No serious system survives sloppy secret handling.

Minimum expectation:
- secrets are not hardcoded in repo
- environment-based config is used
- dev/staging/prod secrets are separated
- exposed secrets are rotated
- development conveniences do not remain active in production carelessly

Current reality:
- the repo audits flagged concern about stale/broken paths and operational uncertainty
- no formal security baseline existed before now
- production-hardening settings were not yet fully reviewed

Security requirement:
- perform an explicit secrets/config review
- rotate anything exposed historically
- separate environment concerns clearly

### 3.11 Operational Production Security

Launch security is broader than app logic.

Minimum expectation:
- production debug posture is safe
- hosts/cors/cookies are reviewed
- email delivery settings are production-ready
- backups/recovery basics exist
- deployment and dependency hygiene are reviewed
- incident response basics are documented

Current reality:
- the audit noted development-oriented email behavior and other environment uncertainties that would need production review

Security requirement:
- production deployment posture must be reviewed before launch readiness is claimed

## 4. Current Security Reality

From current repo understanding, Blackboard already has some useful security foundations:
- JWT authentication
- email verification before token issuance
- billing gates
- admin permissions
- ownership/access tests in some areas
- role-aware contract behavior
- state-machine enforcement in some flows

But the audits also show risk factors:
- stale docs
- broken contacts legacy path
- broken lifecycle automation path
- inconsistent architecture boundaries
- placeholder routes still present
- mixed direct-ORM and service-layer enforcement
- uncertain confidence around business-entity isolation
- no formalized security baseline until now

So current state should be treated as:

> security-aware in parts, but not yet security-disciplined as a full Blackboard system

## 5. Minimum Phase-One Security Requirements

Before Blackboard phase one is treated as launch-ready, these must be true.

### Required
- auth-protected endpoints verified
- ownership checks verified across major domains
- business-entity default isolation verified
- authority and signer rules verified
- Contract Pro delegated-access model defined
- broken contacts path resolved
- lifecycle automation bug fixed or intentionally disabled
- duplicate/shadow/placeholder routes reviewed
- secrets handling reviewed
- production settings reviewed
- billing/webhook verification confirmed
- upload/document safety reviewed

### Strongly Recommended
- rate limiting for sensitive endpoints
- admin action auditing
- security checklist in release process
- dependency review before launch
- environment-by-environment deployment security checklist

## 6. Immediate Security Work Items

### Priority 1 — Stop obvious trust breaks
- repair or remove broken contacts path
- fix lifecycle automation path
- review duplicate obligations routing
- identify shadow/dead modules that confuse enforcement

### Priority 2 — Verify access boundaries
- user ownership checks
- business-entity isolation
- entity-scoped listing and search behavior
- contract/session/upload/document access checks

### Priority 3 — Verify authority and delegated access
- signer vs negotiator vs owner logic
- Contract Pro grant model
- Contract Pro revoke model
- role-switch consequences
- delegated-action auditability

### Priority 4 — Operational hardening
- secrets/config review
- environment separation review
- production email/security settings review
- upload restrictions and file safety review

## 7. Security Standard for Planning

Going forward, no Blackboard phase-one feature should be treated as complete unless it is also reviewed for:

- authentication
- authorization
- ownership
- business/entity boundary behavior
- signer/authority behavior if relevant
- Contract Pro delegated-access behavior if relevant
- auditability if sensitive
- operational secret/config safety if relevant

Security is not separate from completion.
Security is part of completion.

## 8. Summary

Blackboard phase one already has some real security foundations, but it does not yet have a formalized security posture.

The purpose of this baseline is to make security explicit, measurable, and reviewable so that launch readiness is based on trustworthiness, not just feature presence.

The most important security truth is:

> Blackboard already has meaningful security pieces, but it still needs explicit authority rules, Contract Pro delegated-access controls, business-entity isolation confidence, secrets review, and surface hardening before it can be trusted as a launch-ready system