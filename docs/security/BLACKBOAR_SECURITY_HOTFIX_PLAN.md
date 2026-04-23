# BLACKBOARD_SECURITY_HOTFIX_PLAN.md

> Status: Working draft  
> Scope: Immediate and near-term security remediation plan for Blackboard phase one  
> Purpose: Convert `BLACKBOARD_SECURITY_REVIEW.md` findings into a practical fix order

## How to Read This Plan

This plan is not a complete engineering roadmap.

It is a security hotfix ordering document built from the current Blackboard security review.

The purpose is to answer:
- what must be fixed immediately
- what should be fixed before treating the repo as stable project context
- what must be fixed before launch
- what must be defined before more authority-sensitive features are added

Priority labels:
- **Tier 1 — Immediate hotfix**: trust-breaking issue; should be fixed before moving forward
- **Tier 2 — Fix before trusted project-context use**: dangerous or misleading repo state; should be fixed or clearly contained before relying on the repo as stable context
- **Tier 3 — Fix before launch**: important security or trust issue, but not necessarily the very first patch
- **Tier 4 — Structural security design**: design work that must be defined before expanding sensitive capabilities

---

## Tier 1 — Immediate Hotfix

These are the highest-priority issues. They are not polish work. They are active trust breakers.

### 1. Password Reset Token Disclosure
**Status:** Critical  
**Finding:** Password reset endpoint returns reset token in API response body  
**Why it matters:** This creates an account-takeover path for any known registered email  
**Required action:**
- stop returning reset token in the response
- implement actual email-based reset delivery
- verify reset confirm flow only works through properly delivered token flow
- add tests for safe reset behavior

### 2. Stripe Webhook Unsafe Fallback
**Status:** Critical  
**Finding:** Webhook accepts raw JSON when `STRIPE_WEBHOOK_SECRET` is unset  
**Why it matters:** Crafted webhook payloads could manipulate subscription state  
**Required action:**
- remove unsafe fallback behavior
- require verified webhook signature in production-safe code path
- fail closed when secret is missing
- verify environment config immediately
- add tests for missing-secret rejection

### 3. Hardcoded Secrets in Source
**Status:** Critical  
**Finding:** LiveKit credentials and Django secret material are hardcoded in code  
**Why it matters:** These must be treated as exposed secrets  
**Required action:**
- rotate exposed LiveKit credentials
- rotate Django secret if needed based on deployment usage
- move all secrets to environment configuration
- confirm no additional secrets remain hardcoded
- document required env vars clearly

### 4. Debug / Production Settings Posture
**Status:** Critical  
**Finding:** `DEBUG = True` is hardcoded while a public server IP is present in `ALLOWED_HOSTS`  
**Why it matters:** This strongly suggests unsafe production posture risk  
**Required action:**
- environment-gate `DEBUG`
- verify production is not running in debug mode
- environment-gate email backend and other production-sensitive settings
- review production-safe defaults in settings

### 5. Dangerous Dormant `AllowAny` Contract Viewset
**Status:** Critical  
**Finding:** A dormant `ContractViewSet` with `AllowAny` and `Contract.objects.all()` exists in an active package  
**Why it matters:** It is one bad import away from exposing all contracts publicly  
**Required action:**
- delete the file or neutralize it completely
- confirm router and imports cannot accidentally pick it up later
- review for other dormant dangerous files

### 6. Upload Ownership Hole in Document Attachment
**Status:** High  
**Finding:** Document attachment path loads upload by `pk` only, not by ownership  
**Why it matters:** A user may attach another user’s upload to a contract document if they know the upload ID  
**Required action:**
- require `user=request.user` or equivalent ownership/party-safe validation
- review any related attachment flows for the same pattern
- add tests for cross-user attachment denial

---

## Tier 2 — Fix Before Trusted Project-Context Use

These issues may not all be immediately exploitable at the same level as Tier 1, but they make the repo dangerous or misleading as a trusted system context.

### 7. Broken Contacts Domain
**Status:** High  
**Finding:** Contacts domain is broken, unrouted, and imports a deleted model class  
**Why it matters:** It is broken legacy state and a false signal in the repo  
**Required action:**
- remove it, repair it, or clearly isolate it
- do not leave it in ambiguous broken state
- make sure future project context does not treat it as a live domain

### 8. Shadowed / Dead / Misleading Modules
**Status:** High  
**Finding:** Some files/modules are dead, shadowed, duplicated, or stale but still look authoritative  
**Why it matters:** They mislead future work and can accidentally reactivate unsafe paths  
**Required action:**
- identify dead/shadowed modules clearly
- remove or mark them explicitly
- reduce false canonical paths

### 9. Duplicate Route / Surface Confusion
**Status:** Medium  
**Finding:** At least some routes, such as obligations, are duplicated or confusingly mounted  
**Why it matters:** Duplicate or ambiguous route registration increases maintenance/security confusion  
**Required action:**
- remove redundant route registrations
- keep one canonical mounted path
- reduce surface ambiguity

### 10. Placeholder Surfaces in Live Router
**Status:** Medium  
**Finding:** Placeholder-like endpoints exist for workspace/tools/documents behaviors  
**Why it matters:** Even authenticated-only placeholders create false success semantics and unnecessary surface area  
**Required action:**
- remove, disable, or explicitly mark non-production placeholders
- do not leave fake-success routes casually exposed

---

## Tier 3 — Fix Before Launch

These are important security and trust issues that may not block the next day of work, but they must be addressed before real launch confidence.

### 11. Business Entity Isolation Confidence
**Status:** High  
**Finding:** `BusinessEntity` exists, but default multi-business separation is not yet one of the most trusted/tested areas  
**Why it matters:** Blackboard must preserve business separation by default  
**Required action:**
- add explicit multi-business-owner tests
- verify list/retrieve/search/activity/payment/session scoping by entity
- ensure owner-wide aggregation is explicit, not default

### 12. Authority and Signature Formalization
**Status:** High  
**Finding:** Two-party signing rules are present, but the broader authority model is still thinner than phase-one needs  
**Why it matters:** Blackboard needs explicit owner/signer/authorized-representative logic  
**Required action:**
- define authority model explicitly
- verify server-side enforcement for authority-sensitive actions
- remove ambiguity between negotiation and signing power

### 13. Counterparty Identity Weakness
**Status:** High  
**Finding:** Counterparty identity depends on `counterparty_email` string rather than a stronger user/party model  
**Why it matters:** Email-driven identity creates fragility around party identity and email change flows  
**Required action:**
- review whether phase one can tolerate this model safely
- harden email-change behavior first
- plan migration path if stronger identity linkage is needed

### 14. Uploads and Documents Security Review Completion
**Status:** Medium  
**Finding:** Uploads/documents are real, but not yet among the most trusted domains  
**Why it matters:** File flows are common abuse surfaces  
**Required action:**
- review file type restrictions
- review file size limits
- review object association safety
- add permission tests for document access and attachment behavior

### 15. Notification / Activity Security Confidence
**Status:** Medium  
**Finding:** Activity and notifications exist, but full security confidence is not as strong as the most mature domains  
**Why it matters:** Sensitive actions should remain properly scoped and traceable  
**Required action:**
- verify notification list/read scoping
- verify activity visibility by user/entity scope
- strengthen audit coverage where needed

### 16. WebSocket / Session Edge Hardening
**Status:** Medium  
**Finding:** Core session access looks solid, but some client-provided broadcast fields remain lightly validated  
**Why it matters:** Real-time systems can become trust leaks if edge handling stays loose  
**Required action:**
- review broadcast payload validation
- ensure no session metadata can be abused through client-controlled fields

---

## Tier 4 — Structural Security Design

These are design-critical items that must be defined before expanding sensitive collaboration or authority features.

### 17. Contract Pro Delegated-Access Model
**Status:** Not started  
**Why it matters:** Contract Pro is a security-sensitive role, not just a workflow role  
**Must define:**
- who can grant Contract Pro access
- whether access is business-scoped or contract-scoped
- what permissions are included
- what permissions are excluded
- how revocation works
- how actions are audited
- how negotiation rights stay separate from signing rights

### 18. Canonical Authority Model
**Status:** Partial / not formalized  
**Why it matters:** Blackboard phase one needs a clear backend truth about:
- owner
- signer
- authorized representative
- negotiator
- Contract Pro
- other delegated roles if introduced

**Must define:**
- default signer rules
- explicit delegation rules
- data model location for authority
- enforcement points in backend flows

### 19. Canonical Security Completion Standard
**Status:** Not formalized  
**Why it matters:** Features should not be called complete without security review  
**Must define:**
- what minimum auth/authz review every feature needs
- what entity/ownership review every feature needs
- what auditability review every sensitive feature needs
- what production-config review is needed before launch

---

## Recommended Execution Order

### First sequence
1. password reset fix
2. webhook unsafe fallback fix
3. secret rotation and environment migration
4. debug/settings posture fix
5. delete dangerous dormant contract viewset
6. fix upload ownership hole

### Second sequence
7. repair/remove contacts broken legacy path
8. remove/mark dead or shadowed misleading modules
9. clean duplicate/placeholder exposed routes

### Third sequence
10. business entity isolation verification
11. authority/signature formalization
12. counterparty identity review
13. uploads/documents hardening completion
14. activity/notification security confidence pass

### Fourth sequence
15. Contract Pro delegated-access design
16. canonical authority model
17. security completion standard for future work

---

## What This Plan Means

Fixing Tier 1 does not solve most of the repo’s total problems.

What it does is remove the most dangerous immediate trust failures.

That means:
- the repo becomes safer to reason from
- future project knowledge files are less likely to inherit dangerous false-safe assumptions
- launch trust stops being blocked by catastrophic security flaws
- future architecture cleanup can happen on safer ground

---

## Summary

The immediate Blackboard security problem is not that everything is insecure.

The real problem is that a small number of high-severity failures currently outweigh the system’s real strengths.

This plan exists to remove those failures first, then strengthen the trust model, then define the authority and delegated-access systems Blackboard phase one still needs.