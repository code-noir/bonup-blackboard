# BLACKBOARD_CONTRACT_PRO_SPEC.md

> Status: Approved phase-one model — not yet implemented
> Source: BLACKBOARD_AUTHORITY_MODEL.md Section 3 (A3)
> Purpose: Standalone implementation-ready reference for Contract Pro delegated-access design
> Scope: Phase-one rules only; deferred items are listed explicitly at the end

---

## Current backend truth

There is no Contract Pro concept in the backend today. No model, no permission class, no grant record, no route, and no schema field. The backend has no delegated-access mechanism of any kind.

The only authority model currently in code is the two-role initiator/counterparty system. See `BLACKBOARD_AUTHORITY_MODEL.md` Section 1 for the full code-level baseline.

Everything below is the approved phase-one model. None of it is implemented yet.

---

## 1. Access grant model and relationship lifecycle

Access is always explicit. There is no implicit access from messaging, session participation, subscription status, or ordinary user status.

Grant is initiated by the owner from the Oversight surface. There is no self-grant path for a Contract Pro.

### Relationship statuses

| Status | Meaning |
|---|---|
| **pending** | Owner has initiated a grant; Contract Pro has not yet accepted |
| **active** | Grant is accepted and the Contract Pro has live delegated access |
| **declined** | Contract Pro declined the pending grant |
| **revoked** | Owner revoked an active or pending grant |

### Grant scope

Two scope levels exist:

- **Business-wide** — Contract Pro is granted access across the business, subject to the permission matrix.
- **Selected-contract** — Contract Pro is granted access only on specific named contracts.

Business-level permission settings override contract-level settings. A contract-level permission cannot grant more than the business-level ceiling.

---

## 2. Tier and account prerequisite

Contract Pro is a paid tier, not a free role.

- The user must already hold a bonUP/Blackboard account.
- Full Contract Pro activation requires subscription to the Contract Pro plan ($499).
- A user on a standard Blackboard account who has not subscribed to Contract Pro cannot be activated as a full Contract Pro.

The billing system already supports subscription gating. Wiring the Contract Pro plan gate to grant activation is a named implementation dependency (deferred — see Section 9).

---

## 3. Owner/business cardinality

- One active full Contract Pro per business at any time.
- No two full Contract Pros may be active in the same business simultaneously in phase one.
- One owner may own multiple businesses.
- Different businesses under the same owner may have different Contract Pros — there is no constraint that the same person serves as Contract Pro across all of an owner's businesses.
- Phase one does not support multi-owner Contract Pro operation (two owners in one business with separate Contract Pros is out of scope).

Cardinality enforcement requires a grant record queryable at the business level. See Section 8 for the named record families.

---

## 4. Permission model

Permissions are a matrix of per-action accessible/blocked states. The matrix exists at two levels:

- **Business level** — set by the owner; applies across all contracts in the business unless a contract-level setting is more restrictive.
- **Contract level** — set by the owner per contract; may further restrict but cannot expand beyond business level.

Each business has its own independent permission matrix.

### Default: accessible

| Action |
|---|
| Create new contracts |
| Edit delegated contract workspace |
| View contract content |
| Create obligations |
| View obligations |
| Create execution sessions |
| View activity on delegated contracts |
| Message owner via Oversight |

### Default: blocked unless owner explicitly unlocks

| Action |
|---|
| Sign on behalf of owner |
| Trigger payment request |
| Change payout / banking destination |
| Approve payment release |
| Modify business-level settings |

Payment permissions are broken into separate items — there is no single payment flag. Each payment action is a distinct permission the owner can independently configure.

Owner can change permission settings at any time. Changes take effect for future actions only and do not retroactively alter completed actions.

---

## 5. Contract work and editing exclusivity

While a Contract Pro holds active delegation on a contract:

- Only the Contract Pro edits the delegated workspace.
- Owner may read, comment, request changes, message, join a session, sign where needed, and revoke.
- Owner may not co-edit while Contract Pro delegation is active.

If the owner wants direct editing control, the owner must revoke the delegation first. Revocation restores direct editing access to the owner.

If the owner later assigns a new Contract Pro to the same contract, the owner again loses direct in-place editing while the new delegation is active.

This is an intentional design constraint: delegation is exclusive editing authority, not shared editing authority.

---

## 6. Payment and money safety

These defaults are non-negotiable starting positions:

- Business-owned payment rails only. Contract Pro has no custody of business money.
- Changing the payout or banking destination is blocked by default.
- Triggering a payment request is blocked by default.
- Approving a payment release is blocked by default.

Owner may unlock individual payment permissions from the permission matrix, but the default is always locked. These defaults exist to prevent a compromised or unauthorized Contract Pro from redirecting business funds.

---

## 7. Temp / training exception

Temp is a narrow exception within the same business, distinct from full Contract Pro.

### Temp rules

- Temp is per-contract only, not business-wide.
- The temp user must be on the low-tier personal Blackboard plan. Temp does not require the Contract Pro plan.
- While a full Contract Pro is active on a given contract, temp may work only on a different contract within the same business. Temp and full Contract Pro may not hold active delegation on the same contract simultaneously.
- Temp compensation is commission-only. Commission is held until the return/refund policy window passes before release.

### Promotion path from temp to full Contract Pro

1. Owner revokes the temp relationship.
2. The user upgrades to the Contract Pro plan.
3. Owner activates the full Contract Pro relationship.

Temp cannot be promoted by upgrading the plan alone. The revocation step is required to clear the temp grant before a full activation can occur. Automated system-triggered promotion on plan upgrade is deferred (see Section 9).

---

## 8. Counterparty visibility

The counterparty does not see Contract Pro or temp labels.

- The role is internal.
- Internal uses: permission enforcement, Oversight display, activity/audit records, compensation tracking.
- External presentation to the counterparty uses whatever public-facing identity the owner configures.

This applies to both full Contract Pro and temp.

---

## 9. Compensation model

**Full Contract Pro:**
- Compensation structure is flexible and defined per the broader product spec.
- Compensation terms are set at the time of the grant relationship, not by the permission matrix.

**Temp:**
- Commission-only. No other compensation structure is available for temp.
- Commission is held until the return/refund policy window closes before it is released.

Compensation tracking is a named implementation dependency. The compensation engine model is not designed here (deferred — see Section 11).

---

## 10. Communication and Oversight

**Owner visibility:**
- Owner must be able to see all Contract Pro activity on delegated contracts through the Oversight surface.
- Oversight is the canonical owner view of delegated work — not a secondary or optional surface.

**Communication:**
- Owner and Contract Pro need both async and sync communication support.
- Small coordination between owner and Contract Pro should not require entering Boardroom for every exchange.
- A lighter communication channel within the Oversight surface is a named requirement. Its implementation is deferred (see Section 11).

---

## 11. Required record families (named for implementation, not yet designed)

Implementation will require at minimum:

- **Grant record** — links owner, business, Contract Pro user, scope (business-wide or per-contract), status, and timestamps.
- **Permission matrix** — per-business and per-contract permission states; keyed to a defined action list.
- **Relationship status history** — append-only log of status transitions (pending → active, active → revoked, etc.) with timestamps and acting user.

Schema design and migration belong to the implementation sprint. These are named at the model-definition level only.

---

## 12. Explicitly deferred items

These are out of scope for phase one and must not be assumed in implementation planning:

| Item | Deferred to |
|---|---|
| Multi-owner Contract Pro operation | Post-phase-one |
| Automated promotion from temp on plan upgrade | Later implementation sprint |
| Audit trail depth and record structure | A4 |
| Compensation engine model design | Later implementation sprint |
| Schema design for grant record, permission matrix, status history | Implementation sprint |
| Permission matrix UI (Oversight owner-side configuration) | UI design sprint |
| Lightweight owner/Contract Pro communication channel | Later implementation sprint |
| Billing integration (plan gate → grant activation wiring) | Implementation sprint |
| Counterparty disclosure edge cases (legal disclosure requirements) | Post-phase-one |




---------------------------------------
---------------------------------------------
---------------------------------------------------


# BLACKBOARD_CONTRACT_PRO_SPEC.md

> Status: Approved phase-one model — not yet implemented
> Source: Detailed user-provided Contract Pro phase-one specification from this session, aligned with `BLACKBOARD_AUTHORITY_MODEL.md`
> Purpose: Standalone implementation-ready reference for Contract Pro delegated-access design
> Scope: Phase-one Contract Pro rules only; deferred items are listed explicitly at the end

---

## 1. Core Intent

Contract Pro exists so a business owner can delegate real contract work to a professional operator without losing visibility, financial safety, or final owner-side authority.

This is not a cosmetic helper role.

This feature must support real-world delegated work such as:

* opening deals
* creating contracts
* negotiating terms
* running live sessions
* handling back-and-forth with counterparties
* moving deals toward payment and activation
* optionally helping manage post-close contract lifecycle work

The system must support this delegated work without:

* hidden activity
* silent authority leaks
* payment cheating
* session confusion
* owner/pro edit collisions
* fake restrictions that make the feature unusable

---

## 2. Locked Naming

### Product and plan names

* **Blackboard Core** — $149
* **Blackboard Business** — $399
* **Contract Pro** — $499
* **Blackboard Enterprise** — $999
* **Blackboard Starter / Standard personal plan** — low-tier personal Blackboard plan used as the minimum temp/training eligibility tier

### Surface names

* **Pro’s Console** — Contract Pro work surface
* **Oversight** — owner supervisory surface

### Session names

* **Boardroom** — internal owner ↔ Contract Pro session
* **External Session** — outside-facing negotiation/presentation/signing session

---

## 3. Product Positioning

### Blackboard Core

Owner-side plan for a smaller one-business setup.

### Blackboard Business

Owner-side plan for fuller business operations.

### Contract Pro

A professional operator account type for users who professionally manage contract work for one or more businesses that authorize them. In phase one, the delegated-access model is intentionally constrained to keep one active full Contract Pro per business.

### Blackboard Enterprise

Larger organizational tier with bigger scale and management depth.

---

## 4. High-Level Role Model

A single human may exist in more than one context.

### Personal context

The user’s normal personal bonUP / Blackboard account space.

### Business context

The user’s own Blackboard business or enterprise context if they own businesses.

### Contract Pro context

The delegated operating context inside **Pro’s Console**, where the Contract Pro sees businesses and contract work they were explicitly granted access to.

### Temp / training context

A narrow delegated exception used to try out or train a would-be Contract Pro inside one business on one contract. Temp is not the same thing as full Contract Pro.

### Counterparty context

The outside party on the other side of the contract.

### Critical rule

Contract Pro work must not be mixed into the user’s ordinary personal page or ordinary business page. It belongs in **Pro’s Console**.

---

## 5. Business Philosophy

The system must reflect real business behavior.

That means:

* a business can use one or many Contract Pros in real life, but phase one intentionally simplifies this
* Contract Pro must be able to actually work, not just observe
* owners must retain final authority where authority matters
* the system must support both:

  * cautious owner-controlled relationships
  * high-trust, high-speed operator relationships

Phase one simplification:

* one active full Contract Pro per business
* possible temp/training access on a different contract in the same business
* no multiple full Contract Pros in one business yet

---

## 6. Owner Visibility Principle

Everything a Contract Pro or temp does for an owner’s business must be visible to the owner.

This visibility is delivered through **Oversight**.

### Owner must be able to see

* who has access
* what contracts they are working on
* what they created
* what they edited
* what they negotiated
* what sessions they started or joined
* what payment actions they triggered
* what signatures occurred
* what compensation status exists
* what audit events occurred

### Hard rule

There is no hidden Contract Pro work from the owner.

---

## 7. Phase-One Authority Philosophy

Phase one must be strong where authority matters and simple where collaboration would otherwise become messy.

### Contract Pro may by default

* create
* draft
* edit
* negotiate
* communicate
* run workflow
* receive counterparty signature
* work toward payment and activation within configured boundaries
* optionally help manage post-close contract lifecycle work if permitted

### Contract Pro may not by default

* sign for the owner
* change business settings
* reroute money
* hide work from owner
* grant/revoke other Contract Pros
* alter audit history
* silently change authority rules

### Owner may by default

* view everything
* join sessions
* speak
* present
* direct
* request changes
* sign
* revoke access

### Owner may not in phase one

* directly edit delegated contract work in place
* silently overwrite Contract Pro work inside the delegated workspace

### Why

This avoids:

* edit collisions
* owner/pro confusion
* audit mess
* hidden overrides

---

## 8. Access Grant Model

Contract Pro access must always be explicitly granted.

### Grant source

The owner grants access from **Oversight**.

### Grant flow

1. Owner chooses to add a Contract Pro
2. Owner identifies the Contract Pro, initially by bonUP / Blackboard account email
3. Owner selects access scope
4. Owner selects access behavior / permissions where applicable
5. Invite is sent
6. Contract Pro accepts
7. Access becomes active

### No implied access

A person does not become a Contract Pro for a business:

* by messaging
* by collaborating once
* by participating in a session once
* by being a normal user
* by owning their own business

The relationship must be explicit.

### Relationship statuses

* `pending`
* `active`
* `declined`
* `revoked`

### Meaning

* **pending** — invite sent, not yet accepted
* **active** — accepted, relationship live
* **declined** — invite rejected
* **revoked** — access was previously active and has been removed

### Revocation

Owner can revoke access at any time.

Revocation:

* removes active future access immediately
* keeps historical activity visible
* does not erase audit/history
* restores full owner editing control

---

## 9. Access Scope Model

### Default scope

**Selected contracts only**

This is the default and must be the safest starting point.

### Elevated scope

**Business-wide access**

This is stronger access and must be explicitly chosen by the owner.

### Future contract rule

If access is **selected contracts only**:

* the Contract Pro gets access only to the contracts explicitly assigned
* future contracts get no automatic access

If access is **business-wide**:

* the Contract Pro may access current and future contracts within that business according to the business-wide grant and permission matrix

### Selected-contract creation rule

Even when selected-contract is the default model, Contract Pro may create new contracts by default unless the owner blocks that action. Creation rights are governed by the permission matrix, not only by scope label.

### Override rule

Business-level permission settings override contract-level settings. Contract-level settings may further restrict but may not grant more than the business-level ceiling.

---

## 10. Phase-One Owner / Business Cardinality

### Full Contract Pro rules

* one active full Contract Pro per business at any time
* no two full Contract Pros may be active in the same business simultaneously in phase one
* one owner may own multiple businesses
* different businesses under the same owner may have different Contract Pros
* phase one does not support multi-owner Contract Pro operation

### Practical meaning

An owner can run more than one business and use delegated operators across those businesses, but each business stays clean with one active full Contract Pro relationship.

---

## 11. Temp / Training Exception

Temp is a narrow exception within the same business, distinct from full Contract Pro.

### Temp eligibility

* temp must be a Blackboard user
* temp must be on the low-tier personal Blackboard plan
* temp does not require the full Contract Pro plan

### Temp scope rules

* temp is per-contract only, not business-wide
* while a full Contract Pro is active in a business, temp may work only on a different contract within that same business
* temp and full Contract Pro may not hold active delegation on the same contract simultaneously

### Temp permission model

Temp starts from the same broad contract-work permission model as full Contract Pro, with owner-set blocks. Blackboard does not create a separate reduced temp bundle by default.

### Temp compensation

* commission only
* no hourly, flat fee, or hybrid temp model in phase one
* commission stays held until the return / refund policy window passes before release

### Promotion path from temp to full Contract Pro

1. Owner revokes the temp relationship
2. The user upgrades to the Contract Pro plan
3. Owner activates the full Contract Pro relationship

Temp cannot be promoted by plan upgrade alone. The revoke-then-activate path is required.

---

## 12. Permission Matrix Model

Permissions are defined as a clear action list with per-action `accessible` / `blocked` states.

Permissions exist at two levels:

* **Business level** — set by the owner; applies across all contracts in the business
* **Contract level** — set by the owner per contract; may further restrict but may not expand beyond business level

Each business has its own independent permission matrix.

### Default allowed

Contract Pro may by default:

* create new contracts
* view assigned contracts
* edit contract drafts
* negotiate terms
* send contracts for negotiation
* receive and track counterparty responses
* receive counterparty signatures
* upload contract-related documents
* start or join Boardroom sessions
* start or join external sessions for assigned work
* request owner review
* update contract workflow / progress within allowed boundaries
* create obligations and work contract workflow where permitted
* message owner through Oversight or the owner/Pro communication surface

### Default blocked

Contract Pro may not by default:

* sign for the owner
* trigger payment request
* change payout / banking destination
* approve payment release
* change business settings
* grant or revoke other Contract Pros
* hide activity from the owner
* alter audit/history
* access unassigned contracts unless business-wide access was granted or the contract was explicitly assigned

### Payment permissions must be split

Payment-related permissions are broken into separate items. There is no single big payment flag.

Examples of separate payment items:

* structure payment terms
* trigger payment request
* view payment status
* manage payment lifecycle after payment
* change payout / banking destination

### Change effect rule

Owner can change permission settings at any time. A change affects future actions; it does not retroactively alter completed actions.

---

## 13. Contract Creation Rule

By default, Contract Pro **can create new contracts**.

### Why

This role is meant to reflect real sales and contract operator work.

A Contract Pro may:

* find an opportunity
* open the contract
* negotiate it
* move it forward while the owner is away, busy, or delegating

The system should not require the owner to manually create every contract.

### Safety comes from

* owner visibility
* no default owner-side signing authority
* system-owned payment rails
* audit logs
* optional tighter owner-set blocks if desired

---

## 14. Signature and Activation Boundary

A Contract Pro may:

* create the contract
* negotiate the contract
* get the counterparty to sign

But owner-side final authority still matters where owner signature is required.

### Rule

A contract may be far advanced by Contract Pro, including counterparty signature, but it does not become fully owner-authorized / active until required owner-side signature occurs.

### Meaning

The Contract Pro can land the deal operationally.
The owner still completes the owner-side authority step.

This supports real-world flow:

* pro moves fast
* owner signs when available
* contract does not become falsely owner-approved without owner signature

---

## 15. Editing Exclusivity Rules

While a Contract Pro holds active delegation on a contract:

* only the Contract Pro edits the delegated workspace
* owner may read, comment, request changes, message, join a session, sign where needed, and revoke
* owner may not co-edit while Contract Pro delegation is active

If the owner wants direct editing control:

* owner must revoke the Contract Pro first
* after revocation, owner regains direct editing access

If the owner later assigns a new Contract Pro to the same contract or business:

* the owner again loses direct in-place editing while the new delegation is active

This is intentional. Delegation is exclusive editing authority, not shared editing authority.

---

## 16. Oversight

**Oversight** is the owner-side supervisory surface.

### Purpose

Oversight exists so the owner can:

* see which Contract Pros are active
* see which businesses / contracts they can access
* see what they are doing
* see current and historical activity
* see session activity
* see payment triggers
* see compensation state
* revoke access when necessary

### Owner actions in Oversight

The owner may:

* view all Contract Pro activity
* comment
* request changes
* message
* initiate live discussion / session
* sign when needed
* revoke Contract Pro access

### Owner actions not allowed in phase one

The owner may not:

* directly edit delegated contract work in place
* silently overwrite Contract Pro changes in the delegated workspace

If the owner wants changes:

* request them
* discuss them
* message them
* open a session
* the Contract Pro performs the actual edit

---

## 17. Communication Model

Owner and Contract Pro should be able to communicate without requiring a Boardroom for every small issue.

### Required behavior

* lightweight async communication
* lightweight sync communication when both are present
* notifications when a message is sent
* Boardroom reserved for larger live discussion, review, planning, or rehearsal

### Product requirement

The exact communication implementation is deferred, but the system should support:

* quick messages
* note-board style communication
* notification-driven owner/Pro coordination

---

## 18. Session Model Overview

There are exactly two session types in phase one:

* `boardroom`
* `external`

No third casual type exists in phase one.

If users are “just talking,” it still belongs to one of these:

* internal business prep / review = `boardroom`
* outside-facing interaction = `external`

This keeps the model clean.

---

## 19. Boardroom

### Definition

Boardroom is the internal live-session mode used by:

* owner
* Contract Pro

for:

* strategy
* preparation
* review
* rehearsal
* internal discussion
* draft walkthrough
* deal planning
* problem-solving before external engagement

### Boardroom rules

* internal session type
* no counterparty
* may exist without a linked contract
* may exist with a linked contract
* belongs to a business context
* consumes the owner account minute pool
* remains internal for its full lifecycle
* never converts into an external session

### Contract linkage

Boardroom may exist:

* with no contract attached
* with a contract attached

But it remains a Boardroom either way.

If outside-party engagement is later needed, a new External Session must be created with:

* a new token
* a new session record
* its own lifecycle

### Internal-only rule

Boardroom is for internal owner ↔ Contract Pro work only.
It is not a temporary waiting room for counterparty engagement.

---

## 20. External Session

### Definition

External Session is the outside-facing live-session mode used when:

* counterparty is involved
* negotiation is happening with the outside party
* presentation is happening with the outside party
* signing discussion is happening with the outside party

### External Session rules

* outside-facing session type
* separate token
* separate session record
* may involve owner, Contract Pro, counterparty
* belongs to a business context
* consumes the owner account minute pool
* never comes from converting a Boardroom

### Why separate from Boardroom

A Boardroom session and an External Session must remain different because they serve different purposes:

* Boardroom = internal prep / review / rehearsal
* External Session = outside-facing negotiation / presentation / signing

This separation keeps:

* audit cleaner
* role boundaries cleaner
* billing/session logic cleaner
* permission logic cleaner

---

## 21. Session Roles and Behavior

### Contract Pro in session

Contract Pro may:

* speak
* present
* edit
* negotiate
* operate the delegated workspace
* extend according to session extension policy

### Owner in session

Owner may:

* join
* view
* speak
* lead discussion
* present
* sign
* request changes
* direct verbally

Owner may not in phase one:

* directly edit delegated work

### Counterparty in session

Counterparty may:

* join External Session
* view
* speak
* negotiate
* sign if appropriate

Counterparty does not:

* control owner-side workspace
* edit owner-side delegated work

### Important distinction

Presentation control is not editing control.
The owner may lead the meeting and present without being allowed to edit the delegated workspace.

---

## 22. Owner-Led Session Behavior

The owner may absolutely lead a session.

That means the owner may:

* host discussion
* present
* walk parties through terms
* explain pricing
* explain service structure
* clarify business intent
* act as principal decision-maker

The owner may do all that while still not directly editing delegated contract work in phase one.

### Clean rule

The owner may lead and present in session, but the Contract Pro remains the editing operator in phase one.

---

## 23. Session Identity

Every live session must have one unique session identity.

### Session identity model

Use:

* `session_id`
* `session_type`

### Session status values

Use:

* `scheduled`
* `live`
* `ended`
* `cancelled`

### Why one ID model

Boardroom and External Session should share one session architecture and be distinguished by `session_type`, not separate identity systems.

This keeps:

* logging unified
* event tracking unified
* participant tracking unified
* recording logic unified
* extension logic unified

---

## 24. Session Start Durations

Both Boardroom and External Session support:

* `15 minutes`
* `30 minutes`

### Default

* `30 minutes`

If the creator chooses nothing, the session starts at 30 minutes.

---

## 25. Session Extension Model

### Extension trigger point

During the final minute of any session block, the system must enter an **extension countdown state**.

### What must appear on screen

During the final minute, users must see:

* visible countdown
* `Extend 15 minutes`
* `Extend 30 minutes`
* `End session`

### Extension choices

Regardless of how the session started:

* 15-minute session can extend by 15 or 30
* 30-minute session can extend by 15 or 30

### End rule

If nobody chooses anything before countdown reaches zero:

* the session ends automatically

---

## 26. Session Extension Policy

Each session has an extension policy set at creation time.

### Supported extension policy values

* `any_participant`
* `host_only`
* `owner_side_only`
* `no_extension`

### Meanings

* **any_participant** — any active participant may extend
* **host_only** — only host may extend
* **owner_side_only** — only owner-side participants may extend
* **no_extension** — no extension is allowed

### Default recommendation

Keep `any_participant` as default for phase one.

---

## 27. Session Event Logging

Every session event must be recorded in backend logs.

### Session events that must be loggable

* session created
* session scheduled
* session started
* participant joined
* participant left
* final-minute countdown shown
* extension applied
* session ended
* recording started
* recording stopped
* signature occurred during session
* payment request triggered from session if applicable

### Extension event record must include

* `session_id`
* `session_type`
* `business_id`
* `extended_by_bonID`
* `extension_minutes`
* `extended_at`
* `new_session_end_time`
* `extension_policy_at_time`
* `warning_shown`
* minute-usage state at time of extension

---

## 28. Recording Model

### Key distinction

A session existing is not the same as a replayable recording existing.

These must remain separate concepts.

### Session always has system record

Even when no replayable media exists, Blackboard must still store:

* session metadata
* participant metadata
* linked business
* linked contract if any
* timestamps
* actions that happened
* signature occurrence if any
* payment trigger events if any

### Official recording

If recording exists, Blackboard should own the official recording.

Do not rely on participant-side private recordings as system truth.

### Official recording rule

If recorded:

* Blackboard stores the single official replayable version
* not three competing participant-owned platform copies

### Visibility rule

Participants must know when recording exists or is active.
The platform should never be sneaky about recording.

---

## 29. Recording Access Philosophy

Long-term philosophy:

* people should be able to access legitimate records without feeling skimmed on every view
* replay access should feel normal
* monetization should come from plan design and infrastructure design, not petty replay friction

### Replay access

Legitimate participants should be able to replay the official recording.

### Avoid

Do not design replay like:

* “3 views left”
* “pay again to open your own record”
* constant tiny replay penalties

### Better control levers

Use:

* plan pricing
* retention policy
* archive policy
* storage class
* export/download rules
* enterprise-grade retention controls later

---

## 30. Minute Ownership and Billing Model

### Core rule

Minutes are tied to the **owner user account / bonID**, not separately to each business.

### Meaning

If a user owns multiple businesses, they do not get separate minute pools for each business unless future product design explicitly changes that.

They get one shared monthly pool tied to their account.

### Contract Pro rule

When Contract Pro acts for a business:

* minutes do not come from the Contract Pro’s personal pool
* minutes come from the owner account that owns the business relationship

### Business context still matters

Every session should still know:

* which business it belongs to
* which contract it belongs to if any
* which Contract Pro relationship it belongs to if relevant

So:

* **billing owner** = account pool source
* **business context** = work context

These are not the same field and should not be collapsed.

---

## 31. Monthly Usage and Overrun Logic

### Business and Enterprise

Business and Enterprise may overrun included monthly minute allowances.

### Rules

* user should be warned when near monthly limit
* user should be warned when crossing included monthly limit
* there must be a hard overrun cap
* exact cap numbers remain to be finalized

### Important separation

Do not mention money every time session extension appears.

There are two different prompts:

* **session extension prompt** = time-control prompt
* **monthly usage warning** = billing/allowance awareness prompt

---

## 32. Payment Request Authority

This is a major trust point.

### Phase-one default after clarification

Sensitive payment actions are blocked by default unless the owner explicitly unlocks them in the permission matrix.

That includes at minimum:

* trigger payment request
* approve payment release
* change payout / banking destination

### Why

Safety comes from:

* business-owned payment rails
* owner visibility
* audit logs
* configurable owner-side permission control
* no Contract Pro custody of funds

---

## 33. Payment Custody and Safety Rules

Contract Pro should not control business money by default.

### Contract Pro may

* structure payment terms in the contract if permitted
* define deposit or milestone structure in allowed ways
* trigger payment request if the owner explicitly unlocked that action
* see payment status if allowed
* move workflow based on payment state where allowed

### Contract Pro may not by default

* change payout destination
* change business banking details
* reroute funds to their own account
* withdraw business funds
* own the payment rails

### Hard rule

Money moves through business-owned payment infrastructure, not Contract Pro-controlled rails.

---

## 34. Counterparty Payment vs Contract Pro Compensation

The system must keep these as two separate money flows.

### Money flow A

Counterparty pays the business.

### Money flow B

Business compensates the Contract Pro.

These flows must not be blurred together.

---

## 35. Contract Pro Compensation Philosophy

The platform should not assume one universal payment style for full Contract Pros.

### Supported full Contract Pro compensation modes

* `hourly`
* `flat_fee`
* `commission_only`
* `hybrid`

### Why multiple modes

Because some Contract Pros are:

* pure closers
* ongoing operators
* lifecycle managers
* short-term negotiators
* part sales / part service professionals

One model will not fit every case.

### Strong phase-one recommendation

For mature full Contract Pro relationships, the strongest default recommendation is:

* monthly retainer + optional commission

---

## 36. Temp Compensation Rule

Temp compensation is much narrower than full Contract Pro compensation.

### Temp compensation model

* `commission_only`

### Temp commission hold rule

Commission stays **held until the return / refund policy window passes** before it becomes safely releasable.

This protects the owner against:

* refund
* cancellation
* chargeback
* failed payment plan
* collapsed deal after apparent close

---

## 37. Compensation State Logic

### Critical distinction

**Earned** does not always mean **immediately payable**.

### Compensation state values

* `tracked`
* `earned`
* `held`
* `releasable`
* `paid`
* `reversed`
* `disputed`

### Meanings

* **tracked** — compensation terms exist, not yet earned
* **earned** — trigger event occurred
* **held** — earned, but not yet safe to release
* **releasable** — safe to pay under release rules
* **paid** — compensation paid
* **reversed** — previously earned/held amount reversed due to refund/cancel/etc.
* **disputed** — compensation under dispute

---

## 38. Compensation Policy Object

Owner should define compensation policy for each full Contract Pro relationship.

### Required compensation policy concepts

* compensation type
* earned trigger
* release rule
* reversal rule

### Earned trigger examples

* contract created
* counterparty signed
* owner signed
* first payment received
* full payment received
* specific lifecycle milestone

### Release rule examples

* immediately
* after refund window
* after X days
* after first successful payment cycle
* after milestone completion

### Reversal rule examples

* refund
* cancellation
* chargeback
* payment plan failure
* contract collapse after signature

---

## 39. Payment Trigger and Compensation Are Different

The system must keep these separate:

### Payment trigger

When does the counterparty get asked to pay?

### Compensation trigger

When does the Contract Pro earn compensation?

These are not automatically the same event.

### Example

* payment request can be triggered after business-approved workflow
* compensation may still not be releasable until money is received and hold window passes

---

## 40. Compensation Tracking in Phase One

Phase one should support structured compensation tracking inside Blackboard.

That means the platform should know:

* what the owner promised the Contract Pro
* what was earned
* what is held
* what is releasable
* what was paid
* what was reversed
* what is disputed

### Phase-one caution

Full automatic Contract Pro payout / disbursement is a larger system and should not be rushed if it introduces:

* escrow complexity
* refund complexity
* reversal complexity
* tax/reporting complexity
* payroll-like obligations

It is acceptable in phase one for the platform to track compensation rigorously before full payout automation is built.

---

## 41. Business Ownership Backbone

A business must always resolve back to an owning bonID.

### Core business identity

* `business_id`
* `owner_bonID`

### Why

That ownership link determines:

* minute ownership
* authority
* payment rail authority
* Contract Pro access authority
* owner-side Oversight power

### Rule

A business never floats alone.
It always resolves back to owner identity.

---

## 42. Required Backend Record Families

### A. Business record

Minimum fields:

* `business_id`
* `owner_bonID`
* `business_name`
* `business_type`
* `business_status`

### B. Contract Pro access grant record

Minimum fields:

* `access_grant_id`
* `owner_bonID`
* `contract_pro_bonID`
* `business_id`
* `access_type`
* `access_status`
* `granted_at`
* `accepted_at`
* `revoked_at`

### C. Contract assignment record

Minimum fields:

* `contract_assignment_id`
* `access_grant_id`
* `contract_id`
* `assignment_status`
* `assigned_at`
* `unassigned_at`

### D. Session record

Minimum fields:

* `session_id`
* `session_type` (`boardroom` / `external`)
* `business_id`
* `billing_owner_bonID`
* `created_by_bonID`
* `host_bonID`
* `session_status`
* `token`
* `linked_contract_id` (nullable)
* `initial_duration_minutes`
* `extension_policy`
* `started_at`
* `ended_at`

### E. Session participant record

Minimum fields:

* `session_participant_id`
* `session_id`
* `participant_bonID`
* `participant_role`
* `joined_at`
* `left_at`

Possible participant roles:

* owner
* contract_pro
* counterparty

### F. Session extension event record

Minimum fields:

* `session_extension_event_id`
* `session_id`
* `extended_by_bonID`
* `extension_minutes`
* `extension_policy_at_time`
* `extended_at`
* `new_end_time`
* `warning_shown`
* `minute_usage_state_at_extension`

### G. Recording record

Minimum fields:

* `recording_id`
* `session_id`
* `recording_status`
* `recording_started_by_bonID`
* `recording_started_at`
* `recording_stopped_at`
* `recording_storage_ref`
* `recording_access_policy`

### H. Payment action / audit record

Minimum fields:

* `payment_event_id`
* `business_id`
* `owner_bonID`
* `contract_id`
* `actor_bonID`
* `action_type`
* `amount`
* `payment_destination_reference`
* `created_at`

Examples of `action_type`:

* payment_request_created
* deposit_requested
* payment_link_sent
* payment_received
* payment_status_changed

### I. Compensation policy record

Minimum fields:

* `compensation_policy_id`
* `business_id`
* `owner_bonID`
* `contract_pro_bonID`
* `policy_scope` (`business_level` / `contract_level`)
* `compensation_type`
* `earned_trigger`
* `release_rule`
* `reversal_rule`
* `created_at`
* `updated_at`

### J. Compensation ledger record

Minimum fields:

* `compensation_record_id`
* `compensation_policy_id`
* `business_id`
* `owner_bonID`
* `contract_pro_bonID`
* `contract_id` (nullable if business-level)
* `compensation_status`
* `tracked_amount`
* `earned_amount`
* `held_amount`
* `releasable_amount`
* `paid_amount`
* `reversed_amount`
* `disputed_amount`
* `earned_at`
* `released_at`
* `paid_at`
* `reversed_at`

### K. Oversight / audit event record

Minimum fields:

* `oversight_event_id`
* `business_id`
* `actor_bonID`
* `event_type`
* `object_type`
* `object_id`
* `event_payload`
* `created_at`

Examples of `event_type`:

* contract_created
* contract_updated
* counterparty_signed
* owner_review_requested
* session_started
* session_extended
* recording_started
* payment_triggered
* access_granted
* access_revoked

---

## 43. Notification / Visibility Expectations

The owner should not feel blind.

### Visibility timing principle

Important Contract Pro actions should appear in Oversight quickly enough that the owner experiences the system as near-real-time or close enough to trust.

Important events include:

* contract created
* important draft saved
* counterparty signed
* session started
* payment request triggered
* access granted / revoked
* compensation state changed

---

## 44. What Phase One Is Deliberately Not Doing

To keep phase one controlled, do not overbuild these yet:

* owner direct in-place editing of delegated workspace
* Contract Pro default signing authority
* marketplace / discovery economy for Contract Pros
* fully automatic payroll-grade Contract Pro disbursement if backend is not ready
* excessive role matrix explosion
* multiple casual session types beyond Boardroom and External Session
* participant-side unofficial recordings as system truth
* per-view replay penalties as the core record-access model
* multi-owner Contract Pro operation
* multiple full Contract Pros inside one business

---

## 45. Phase-One Defaults Summary

### Access

* explicit invite by owner
* selected contracts only by default
* business-wide must be explicit

### Authority

* Contract Pro can create / negotiate by default
* no default owner-side signature authority
* owner sees everything
* owner does not directly edit delegated work in phase one

### Sessions

* session types: boardroom / external
* 15 or 30 minute start
* default 30
* final-minute countdown
* extension by 15 or 30
* auto-end if nobody chooses
* default extension policy = any participant

### Recording

* official Blackboard recording if recording exists
* platform-owned official version
* replay access for legitimate participants
* no petty replay-meter design

### Billing

* minutes tied to owner bonID account pool
* not per business
* Business and Enterprise may overrun with warning and hard cap

### Payment

* sensitive payment actions blocked by default unless owner explicitly unlocks them
* money rails belong to business, not Contract Pro

### Compensation

* full Contract Pro supports multiple models
* owner chooses policy
* temp is commission-only
* earned / held / releasable / paid / reversed logic required

---

## 46. Final Backbone Statement

Contract Pro is a Blackboard phase-one delegated contract operating system in which a business owner explicitly authorizes a professional operator to create, negotiate, manage, and advance contract work through Pro’s Console while the owner supervises everything through Oversight. The owner retains final owner-side authority where required, the delegated workspace remains under exclusive editing control while delegation is active, session and money boundaries stay clean, and the platform tracks access, actions, sessions, money triggers, and compensation through structured backend records.

---

## 47. Immediate Implementation Meaning

Implementation should proceed in this order:

1. access grant model and records
2. selected-contract vs business-wide scope enforcement
3. one-full-Contract-Pro-per-business enforcement
4. permission matrix backbone and enforcement points
5. Oversight event visibility backbone
6. exclusive editing delegation rules
7. session model
8. payment trigger authority and payment safety boundaries
9. compensation policy and compensation ledger
10. recording and replay access policy implementation

---

## 48. Explicitly Deferred Items

The following remain deferred beyond this phase-one spec or to later implementation work:

* audit trail depth and structure for delegated-access events (A4)
* billing integration wiring for Contract Pro plan activation
* permission matrix UI details in Oversight
* lightweight owner/Contract Pro communication implementation
* automated temp promotion
* compensation engine / payout engine design
* multi-owner Contract Pro operation
* legal / disclosure edge cases where counterparty role labeling may be required by policy or law
* full schema and migration design details beyond the named record families
