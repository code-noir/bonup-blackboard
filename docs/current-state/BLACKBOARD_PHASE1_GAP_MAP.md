BLACKBOARD_PHASE1_GAP_MAP.md

Status: Working draft
Scope: Blackboard phase-one backend/system scope only
Purpose: Compare Blackboard phase-one intent against current backend reality
Note: This document does not evaluate broader bonUP/PBVD platform scope unless a concept directly affects Blackboard phase one.

How to Read This Document

This gap map is not measuring whether the product is visually polished or fully complete in front-end UX terms.

It is measuring whether a Blackboard phase-one capability is:

Backend working — materially present and functioning at the backend/system level
Backend partial — materially present, but incomplete, thin, or not yet fully trusted
Backend broken — present, but known-broken
Backend disconnected — present in code, but not on the active path
Backend not started — not materially present yet
Out of scope for Blackboard phase 1 — belongs to broader bonUP / PBVD / later vertical work

This document is about Blackboard phase-one backend truth.

1. Blackboard Contract and Agreement Core
Phase-one intent

Blackboard is the contract- and agreement-centered product surface. It must support contract creation, revision, signing, activation, and downstream lifecycle consequences.

Current backend state

Backend working

The backend already supports:

contract creation
contract versioning
role-aware signing and rejection
contract-linked obligations
contract-linked payments
contract-linked sessions
contract-linked activity
contract-linked uploads/documents
contract-linked AI conversations
Gap
canonicalize the true contract/version path
reduce duplicated contract/version implementations
confirm which version-service path is actually authoritative
remove confusion from dead or shadowed contract modules
2. Contract Lifecycle Engine
Phase-one intent

Blackboard phase one depends on a real lifecycle engine that can evaluate obligation state over time and track whether agreements are being fulfilled, delayed, defaulted, escalated, or resolved.

Current backend state

Backend working, with caveats

The backend has:

obligation primitives
lifecycle evaluator
escalation logic
obligation scheduler
lifecycle processor
payment/service obligation separation
Gap
fix broken lifecycle automation invocation
retire or formally mark legacy lifecycle paths
define one canonical lifecycle path
ensure lifecycle automation is counted as working only after repair
3. Contract Activation
Phase-one intent

A validly signed agreement should become active and generate downstream obligations through a reliable backend flow.

Current backend state

Backend working, but architecturally mixed

Activation exists and works, but the live path appears to use direct ORM writes instead of the cleaner repository/service-oriented activation path.

Gap
decide the one canonical activation path
either officially keep the direct ORM path
or repair and adopt the service/repository path
remove competing duplicate activation implementations
4. Payment and Service Obligations
Phase-one intent

Blackboard must model and track both payment obligations and service obligations as distinct, meaningful parts of the contract lifecycle.

Current backend state

Backend working

The backend clearly supports:

payment obligations
service obligations
lifecycle state evaluation
contract-linked execution structures
payment linkage
Gap
make canonical obligation models explicit
remove confusion caused by the old legacy Obligation model
ensure no live API path depends on obsolete obligation structures
5. Execution, Approvals, and Adjustments
Phase-one intent

Blackboard should capture execution activity and support approvals, disputes, and value adjustments tied to actual contract activity.

Current backend state

Backend working

This is one of the strongest realized backend areas:

execution sessions
execution events
approval requests
value adjustments
obligation promotions
Gap
protect this area as a core Blackboard strength
document this chain as canonical Blackboard execution logic
tighten any thin edges but avoid destabilizing it unnecessarily
6. Payment Flow and Payment State Management
Phase-one intent

Payments should be recorded, transitioned safely, and reflected in the lifecycle/accountability of the agreement.

Current backend state

Backend working, but architecturally inconsistent

Payment state transitions are real and tested, but the intended payment engine/gateway abstraction is bypassed on the live path in favor of direct ORM view logic.

Gap
choose the canonical payment processing path
either keep the current direct ORM path intentionally
or repair and adopt the formal engine payment service path
remove false architectural duplication
7. Authority, Signature, and Role Integrity
Phase-one intent

Blackboard must distinguish between:

owner
signer
authorized representative
negotiator
delegated contract actor

By default, final authority should stay with the owner or explicitly authorized signer.

Current backend state

Backend partial

There is evidence of:

role-aware signing
state-machine enforcement
permission-aware version flows

But the fuller authority model from the Founder’s Vision is not yet clearly implemented as a complete backend authority system.

Gap
define the authority model explicitly
decide where authority lives in backend design
separate negotiator behavior from signer behavior
ensure signing authority is explicit, not implied
8. Contract Pro
Phase-one intent

Contract Pro is in scope for Blackboard phase one.

The system already needs a clearer distinction between:

owner
signer
negotiator
delegated contract professional

Contract Pro is not only a workflow role. It is also a delegated-access and authority-sensitive role.

Current backend state

Backend not started as a formal role and authorization subsystem

There may be nearby role logic, but the audit does not show Contract Pro as a first-class backend concept yet.

Gap
define Contract Pro as a formal Blackboard role
define how Contract Pro access is granted
define whether it is business-scoped, contract-scoped, or both
define default permissions
define non-permissions by default
separate negotiation rights from signing rights
define revocation flow
define audit trail requirements
9. Business Entity Support
Phase-one intent

A single owner may manage multiple businesses, but each business must remain separate by default.

Contracts, activities, payments, sessions, and related records should stay scoped to the correct business unless the system explicitly provides an owner-level aggregation view.

Current backend state

Backend partial

BusinessEntity is real and active in schema and tied to contracts, but the domain is not yet one of the most trusted or thoroughly proven areas.

Gap
verify one-owner / multiple-business behavior
verify default business-level separation
verify that list/search/activity/payment/session behavior does not bleed across businesses by default
ensure owner-wide aggregation, if allowed, is explicit and not implicit
strengthen testing for entity scoping
10. Sessions / Live Negotiation
Phase-one intent

Blackboard phase one includes live negotiation/session functionality as part of real agreement workflow.

Current backend state

Backend working

Sessions are one of the stronger domains:

live session lifecycle
participant flow
token issuance
WebSocket support
Gap
make sure sessions stay integrated into Blackboard workflows
document how sessions connect to contracts, prep, and agreement progression
11. Negotiation Prep
Phase-one intent

Prep is part of Blackboard’s negotiation support flow.

Current backend state

Backend working

Prep is materially real with models, endpoints, and tests.

Gap
mostly workflow clarity, not backend existence
ensure it remains connected to Blackboard use cases and not treated like an orphan subsystem
12. Templates
Phase-one intent

Templates are part of Blackboard phase one.

Current backend state

Backend partial to working

The backend already includes:

contract templates
guided fields
clauses
obligation patterns
obligation templates
payment templates
Gap
verify template instantiation end to end
determine which template flows are truly launch-ready
improve confidence in thin template endpoints
keep template scope tied to Blackboard, not broader PBVD future systems
13. Workspace
Phase-one intent

Workspace is part of the early Blackboard surface.

Current backend state

Backend partial / placeholder

There is a routed workspace namespace, but it currently looks more like scaffolding than a mature Blackboard subsystem.

Gap
define what Workspace should mean in Blackboard phase one
determine whether some workspace behavior already exists elsewhere
either build it properly or stop counting the placeholder as meaningful completion
14. Notifications
Phase-one intent

Notifications are part of Blackboard phase-one operational workflow.

Current backend state

Backend partial

Notification model and helper logic are real, and activity-linked notification writing exists, but the endpoint/product maturity is weaker than stronger domains.

Gap
verify delivery behavior
verify list/read flows
improve endpoint tests
define what notification behavior is launch-critical
15. Operational Workflow
Phase-one intent

Blackboard phase one must behave like an operational system, not just a record container.

Current backend state

Backend partial

Real workflow-like mechanisms already exist:

approvals
disputes
lifecycle transitions
role switch requests
session transitions
payment transitions
execution approval chains
prep workflow
Gap
document the canonical operational workflows
identify which workflows are launch-critical
repair broken automation paths
reduce duplicated service/logic paths
16. Billing / Blackboard Subscription
Phase-one intent

Blackboard is a paid product surface with subscription gating.

Current backend state

Backend working

Billing is one of the strongest domains:

plans
subscriptions
checkout
portal
webhooks
trials
gates
Gap
preserve billing as a strong stable area
verify gates align with actual Blackboard launch scope
keep Blackboard subscription separate from later PBVD/storage economics
17. Search
Phase-one intent

Search should support Blackboard workflows where needed.

Current backend state

Backend working

Search is broad and well-tested across multiple domains.

Gap
mostly UI/product integration work
keep backend stable
verify entity/business scoping later
18. SOL
Phase-one intent

SOL is definitely part of Blackboard phase one.

It may be marketed distinctly, but users access it through Blackboard. From a system and backend perspective, SOL is in Blackboard scope.

Current backend state

Backend working

SOL is one of the strongest realized domains:

self-contained models
routes
contributions
payouts
notes
tips
tests
Gap
determine launch readiness and rules
define how SOL is positioned inside Blackboard
keep it in Blackboard scope, not floating as an optional maybe-domain
19. Uploads and Documents for Blackboard Use
Phase-one intent

Blackboard needs attachments and supporting materials within its contract lifecycle context.

Current backend state

Backend partial

Uploads and documents exist, but are less mature than some stronger domains:

uploads are present
documents are real in schema
API/product maturity is weaker than the schema suggests
Gap
improve trust in upload/document flows
clarify Blackboard-specific role of uploads/documents
keep this separate from future Studjo or PBVD systems
20. Activity / Audit-Like Trail
Phase-one intent

Blackboard should preserve enough activity visibility to support lifecycle accountability and internal trust.

Current backend state

Backend partial to working

Activity model and helper flows are real and broadly used, but the area is not as heavily validated as stronger domains.

Gap
confirm activity coverage is sufficient for launch
improve tests if needed
ensure business/entity scoping is respected
21. Lifecycle Automation
Phase-one intent

Lifecycle accountability over time is part of Blackboard phase one.

Current backend state

Backend broken

The architecture exists, but the CLI lifecycle automation path appears broken because of the kwargs/signature mismatch found in the audit.

Gap
fix this before claiming lifecycle automation is phase-one ready
treat it as a launch-critical repair item
22. Admin / Internal Oversight
Phase-one intent

Operational oversight matters, even if it is not the center of Founder’s Vision.

Current backend state

Backend working, lightly trusted

Read-only admin endpoints exist and are protected, but tests are limited.

Gap
keep as a support surface
lower priority than lifecycle, authority, entity, and contract flow fixes
23. Security and Trust Foundation
Phase-one intent

Security must be a first-class foundation of Blackboard.

Blackboard phase one must protect against:

unauthorized access
cross-user data leakage
cross-business data leakage
weak authority enforcement
exposed secrets
unsafe payment and billing flows
broken or placeholder endpoints becoming attack surfaces
sabotage through weak backend boundaries

Security is not a side concern. It is part of Blackboard’s product foundation.

Current backend state

Backend partial

The backend already has some real security-related foundations:

JWT authentication
email verification before token issuance
billing gates for feature access
admin-only protection on admin endpoints
ownership and access-control tests in some areas
state-machine enforcement in contract/version/payment flows
role-aware signing behavior in contract negotiation

But security is not yet formalized as a complete Blackboard phase-one foundation.

Known concerns include:

stale and broken code paths still present
inconsistent architecture boundaries
unclear confidence around business-entity isolation
broken legacy domains still in the repo
placeholder surfaces still routed
no canonical security baseline document until now
no confirmed full review of secrets handling, environment separation, or production hardening settings
Gap
create and maintain BLACKBOARD_SECURITY_BASELINE.md
verify secrets handling and remove exposed secrets
verify owner/business isolation rules
verify user/resource ownership checks across domains
verify authority and signer rules
harden uploads and thin/placeholder endpoints
remove or lock down broken/dead surfaces
define minimum production security controls
Explicitly Out of Scope for Blackboard Phase 1

These are part of broader bonUP / PBVD direction, but should not be treated as missing Blackboard phase-one backend features:

formal PBVD subsystem
PBVD verification / registration / certificate system
Studjo
storage billing / storage entitlement model
general creator monetization system
broader platform-wide user-owned content framework as a product subsystem

These should be tracked separately at the bonUP / PBVD level.

Blackboard Phase-One Readiness Snapshot
Backend working now
auth
contracts core
lifecycle core
payment transitions
billing/subscriptions
sessions
prep
search
SOL
execution / approvals / value adjustments
Backend partial now
authority/signature depth
business entity behavior
templates
workspace
notifications
operational workflow cohesion
uploads/documents
activity confidence
security posture as a formalized system layer
Backend broken now
lifecycle automation
contacts broken legacy path
some version service paths if reached
dead/shadowed modules creating confusion
Backend not started but in Blackboard scope
Contract Pro as a formal subsystem / delegated-access role model
Immediate Blackboard Priorities
Priority 1 — Repair truth-breaking issues
fix lifecycle automation bug
clean up broken contacts legacy path
determine whether version-service bug affects live paths
mark or remove dead/shadowed modules
Priority 2 — Canonicalize Blackboard core flows
activation
versioning
payment path
lifecycle path
Priority 3 — Strengthen Blackboard foundation
business entity isolation/default scoping
authority/signature model
Contract Pro design
template confidence
notifications confidence
uploads/documents confidence
security baseline enforcement
Priority 4 — Protect what already works
billing
sessions
SOL
search
execution/approval chain
core contract flow
Summary

Blackboard phase one is not starting from scratch.

A large part of the Blackboard backend foundation already exists and is materially real:

contracts
lifecycle structures
sessions
billing
SOL
search
execution/approval mechanics

The real problem is not total absence. The real problem is:

coherence
canonical paths
a few critical broken areas
missing role/authority formalization
missing first-class security formalization

The most important truth is:

Blackboard phase one is partly already built, partly partially realized, partly inconsistent, and still missing a few important role, authority, and security systems