CURRENT_STATE.md — bonUP Blackboard Backend

> Status: Working draft  
> Purpose: Canonical current-state snapshot derived from repository audit passes 1–4  
> Note: This document reflects code inspection and may be refined as deeper tracing and runtime verification continue.


1. Executive Summary

The bonUP Blackboard backend is no longer a small contract API with a few supporting domains. It is a multi-domain platform backend with a strong contract lifecycle core, significant schema depth, broad API surface area, and several adjacent product domains already present in code. At the same time, the architecture is mixed in quality: some flows are well-layered through engine, services, and repositories, while many others still rely on direct ORM usage in views. Several stale, broken, duplicated, or bypassed paths also remain in the codebase.

The current backend should be understood as:

a serious contract lifecycle management system
with real payment and service obligation modeling
with execution/proof flows
with billing/subscription gating
with live negotiation/session features
with a separate SOL financial product domain
with AI, search, prep, uploads, and template-related domains at varying levels of maturity
with some live bugs and stale/dead code that must be cleaned up before trusting the architecture narrative fully.
2. System Identity

The backend is best described as a contract-centered lifecycle platform backend rather than just a contract CRUD app.

Its center of gravity is the contract domain, especially:

Contract
ContractVersion
ContractObligation
ContractServiceObligation
execution sessions and execution events
approvals
value adjustments
promotions
bonID identity
subscription gating.

But the backend already extends beyond that core through additional domains:

billing
sessions/live negotiation
SOL
search
AI
prep
uploads
documents
notifications
users
activity.

So the real identity of the system today is:

a contract lifecycle platform with adjacent platform domains already materially implemented, not merely stubbed out in docs

That said, not all those domains are equally mature. Some are tested and substantial; others are thin, placeholder, broken, or only partially integrated.

3. Architectural Layers

The declared architecture is roughly:

engine/domain layer
API layer
infrastructure/repository layer
Django ORM model layer.

This layering is real in parts but not consistently enforced.

Where the layering is clean

The cleanest areas include:

obligation lifecycle evaluation
execution evaluation and approval flow
value adjustment flow
lifecycle automation factory/runner chain
activity/notification helper flow
billing gate checks.

In these areas, the code often follows a sensible pattern:

view
service
repository
engine/domain logic
persistence.
Where the layering is muddy

Outside the cleaner flows, many domains still use:

direct ORM access in views
direct object creation in API handlers
selective helper usage without full service/repository mediation.

This is especially visible in:

payments
contract creation
sessions
SOL
AI
users
billing data writes.
Real architectural conclusion

The actual architecture today is:

mixed-pattern, partially layered, partially direct-ORM

That means the old clean architecture story is only partly true. Some flows embody it well; many others do not.

4. Domain-by-Domain Status
auth — Working

Routed, tested, and functionally real. Handles signup, email verification, JWT issuance, refresh, resend verification, and logout/blacklist behavior. Email verification gates token issuance.

contracts — Working

This is the largest and most central domain. It includes contract CRUD, versioning, signing/rejection, obligation-related endpoints, execution sessions/items, approvals, adjustments, and related lifecycle operations. Substantial tests exist around creation, version negotiation, approval guards, and role switching.

obligations — Working

Heavy API surface with substantial view code. Supports obligation handling and execution-related flows. Some tests exist indirectly through execution/approval flows, but coverage is not as clearly centralized as other domains.

payments — Working

Payment CRUD and state transitions are real and tested. However, payment architecture bypasses the intended engine payment service and uses direct ORM in views. The domain is functionally working but architecturally inconsistent.

users — Working

Users domain includes bonID identity, business entities, invitations, billing info, and profile data. It is structurally real and partly tested, but contains a broken Contact legacy path.

billing — Working

One of the strongest domains outside core contracts. Includes subscription plans, user subscriptions, invoices, Stripe checkout, portal, webhook handling, trials, and gates. Heavily tested.

sessions — Working

Live negotiation/session domain is substantial. Includes session lifecycle, participant flow, token issuance, WebSocket support, and related prep/upload hooks. Well tested.

sol — Working

SOL is a real standalone financial subdomain with its own models, endpoints, payouts, contributions, notes, and contracts. It is not tied by FK to the core contract domain. Tested and materially implemented.

search — Working

Search is larger and more mature than older docs implied. It exposes multiple specialized search endpoints across contracts, obligations, payments, users, sessions, documents, activity, and SOL. Well tested.

ai — Partial to Working

AI domain is substantial in code size and tested. It persists AI conversations and supports chat/tool endpoints, but its deeper product maturity and runtime quality are beyond what structure/tests alone can prove. Still, it is clearly not a fake domain.

prep — Working

Negotiation prep is real, backed by models and tests. It is not a stub.

entities — Partial

Routed and active-looking, but has no dedicated Django app and lacks tests. Likely tied to BusinessEntity in users. Needs deeper confirmation.

uploads — Partial

Real model exists and endpoints are present, but tests are absent and storage integration depth is still uncertain from inspection alone.

documents — Partial

The model layer is real (ContractDocument), but the API surface is much thinner than the data model suggests. This domain exists more strongly in schema than in exposed product behavior.

notifications — Partial

Real model and notify helper exist, and notifications are written from activity flows, but endpoint testing is absent and delivery depth is uncertain.

activity — Partial

Real append-only event logging model and helper exist. Small API surface, not heavily tested.

templates — Partial

Backed by real contract_templates models and instantiation structures, but endpoint maturity and correctness are still less proven due to lack of tests.

obligation-templates — Stub to Partial

Real backing models exist, but endpoint surface is thin and untested.

payment-templates — Stub to Partial

Same story as obligation-templates: real backing structures, but thin exposed surface and no tests.

workspace — Dead / Placeholder

Routed, but appears placeholder-only. No meaningful evidence of real product behavior.

tools — Dead / Placeholder

Same as workspace.

contacts — Broken / Dead

Code exists, but it is unrouted and imports a Contact model class that no longer exists in users/models.py. This is broken legacy state, not a live domain.

admin — Working

Read-only admin API endpoints exist and are protected by IsAdminUser, but tests are absent. Still, surface behavior appears real.

5. Engine Reality

The engine under backend/engine/ is real and significant.

Strong engine areas

The strongest authoritative pieces appear to be:

lifecycle_core/obligations/primitives.py
lifecycle_core/state/evaluator.py
lifecycle_core/state/escalation.py
lifecycle_core/scheduler/obligation_scheduler.py
engine/contracts/obligations/lifecycle.py
execution evaluator and execution adjustment builder.

These are not decorative files. They are actually part of some real flows.

Engine areas that appear weaker or dead

Several engine paths look legacy, bypassed, or dead:

lifecycle_manager.py
instances/obligation_instance.py
adapter-driven old evaluation path
some placeholder files under engine contracts obligations
possibly parts of import/recurrence/reconstruction/projection not yet confirmed.
Engine truth statement

The engine is real, but only parts of it are truly canonical in current flows. Other parts are duplicated, stale, or bypassed.

6. Data Model Reality

The data model is much richer than older docs suggested.

Most important models

Highest-value core models include:

Contract
ContractVersion
ContractObligation
ContractServiceObligation
BonUserProfile
AssignedBonId
Payment
ObligationExecutionEvent
UserSubscription
Sol and its related SOL models.
Important schema truth

The schema clearly encodes:

immutable versioning
payment and service obligation separation
proof/execution chains
approvals
value adjustments
promotion of execution events
identity sequencing
feature gating/subscriptions
a standalone SOL product
document/upload separation
prep/live session support.
Data model weaknesses and suspect models

The main suspect model issues are:

legacy Obligation vs real obligation models
RequestChange appearing weak/orphaned
deleted Contact class with migration residue
some thin template models whose real integration depth remains uncertain.
7. API Reality

The API surface is broad and real. Estimated routable endpoints are around 165.

This is not a toy API. But it contains a mix of:

fully wired and tested domains
thin but real domains
placeholder namespaces
broken dead paths
duplicate routing inconsistencies such as obligations being mounted twice.
Important API truth

The API offers much more than the old repo docs claimed. However, endpoint existence alone does not mean architectural cleanliness or equal maturity. Some important flows are well-tested and trusted; others are lightly tested or effectively placeholders.

8. End-to-End Flows
Working
signup → verify-email → JWT auth
contract creation
version negotiation/sign/reject
payment transition state machine
execution session/item/approval path
billing checkout/webhook/subscription gating
live sessions
SOL flow
search flow
prep flow
AI conversation/tool flow.
Partial / mixed
contract activation works but uses direct ORM path rather than cleaner repo/service path
documents exist more strongly in schema than in API/product behavior
uploads appear real but lightly validated by tests
entities/templates families are present but less trusted due to limited testing.
Broken / suspect
lifecycle automation CLI path appears broken by kwargs/signature mismatch
ContractVersionService appears broken if invoked
contacts domain is broken and unreachable
dead/shadowed contract view module exists.
9. Docs vs Code Drift

The docs are clearly stale in several important ways.

Confirmed drift
router/domain count is not 15; it is materially larger
test count is not 11 overall; there are large API/domain test suites
some domains previously described as stubbed are materially active
architecture docs overstate cleanliness and understate mixed direct-ORM reality
some repo files mentioned as canonical are either close in name, duplicated, or no longer the actual dominant live path.
More precise drift statement

The old docs understate implementation breadth, understate test coverage, and overstate architectural coherence.

10. What Is Present But Not Fully Realized

These concepts exist materially but are not yet fully realized, fully trusted, or fully coherent:

template family endpoints
uploads/documents productization
entities
notifications as a full product surface
some version-service / lifecycle-service abstractions
AI as a stable production-grade subsystem
broader repo-wide repository/service consistency
lifecycle automation beyond current broken invocation path.
11. What Is Missing

The biggest missing or weak areas relative to the apparent design are:

consistent repository coverage outside contracts
consistent service-layer usage outside cleaner contract subflows
removal or formal deprecation of dead legacy models/paths
repair of broken service paths
stronger test coverage for weaker domains
clear canonicalization of versioning, activation, and payment flow
reliable lifecycle automation execution
cleanup of broken contacts/domain residue
cleanup of placeholder workspace/tools surfaces
updated architecture/current-state docs aligned with repo truth.
12. Stability Assessment
Stable enough to trust
engine primitives/evaluator/scheduler
auth flow
contract creation/version negotiation
payment state transitions
billing
sessions/live negotiation
SOL
search
execution→approval flow
value adjustment layering.
Fragile or misleading
lifecycle automation
some version-service abstractions
payment architecture purity claims
contacts
old/dead lifecycle manager/adapter paths
template family maturity
uploads/documents maturity
some stale docs that still imply older system truth.
13. Recommended Canonical Summary

The bonUP Blackboard backend is currently a serious, partially mature, multi-domain platform backend with a strong contract lifecycle core and real adjacent domains including billing, sessions, SOL, search, AI, prep, uploads, and templates. Its schema and API breadth are much more advanced than old docs suggested, and several major flows are already substantively implemented and tested. However, the architecture is mixed: some important flows are cleanly layered through engine, services, and repositories, while many others still rely on direct ORM view logic. Several stale, broken, duplicated, or bypassed paths remain, including at least one likely live lifecycle automation bug, a broken contacts domain, and multiple competing canonical paths for certain operations. This backend should be treated as more advanced than the docs claimed, but less coherent than the docs claimed.

Top truths about this backend
It is much broader than a simple contracts/payments backend.
Contract is the main cross-domain anchor.
SOL is a real standalone product domain, not just a concept.
Billing is strong and heavily tested.
Search is substantial and well-tested.
Sessions/live negotiation is real and well-tested.
Execution/approval/value-adjustment paths are some of the cleanest architecture in the repo.
Payment flows work, but architecture is bypassed.
There is heavy direct ORM usage in views outside cleaner subflows.
The old docs are badly stale on counts, breadth, and cleanliness.