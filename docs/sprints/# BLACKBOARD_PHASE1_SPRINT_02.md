# BLACKBOARD_PHASE1_SPRINT_02.md

> Status: Complete  
> Scope: Blackboard phase-one Sprint 02  
> Purpose: Execute the first core-stabilization batch after immediate security hotfixes

## Sprint Goal

Sprint 02 is not about adding new features.

Sprint 02 is about stabilizing the current Blackboard backend so the system stops carrying broken or misleading core paths.

This sprint should focus on:
- fixing broken lifecycle automation
- resolving the broken contacts path
- cleaning dead/shadowed misleading modules
- cleaning duplicate/confusing route registrations
- canonicalizing the contract/version flow
- canonicalizing the activation/payment/lifecycle paths

This sprint should happen after Sprint 01 trust-restoration work is complete or substantially complete.

---

## Sprint 02 Items

### C1 — Fix Lifecycle Automation Path

**Status: Complete**

#### Objective
Make lifecycle automation either actually work or be explicitly disabled until repaired.

#### Why this matters
Lifecycle automation is part of Blackboard phase-one truth. Right now it appears broken, which means the system is claiming lifecycle behavior it cannot safely execute.

#### Expected work
- repair the kwargs/signature mismatch in the lifecycle automation path
- trace the real invocation flow end to end
- verify `run_lifecycle` runs successfully
- confirm the correct lifecycle service method is being used
- decide whether unsupported or duplicate lifecycle runner paths should be removed or deprecated

#### Likely files touched
- lifecycle automation runner/factory files
- lifecycle runner service files
- management command files related to `run_lifecycle`
- tests or verification scripts if added

#### Done condition
- `run_lifecycle` executes without runtime failure
- lifecycle automation path is verified as real
- broken duplicate invocation logic is removed or clearly deprecated
- lifecycle automation is no longer counted as broken

#### Completion notes
Fixed three invocation mismatches in the runner/service call chain: wrong method called (`.run()` instead of `.tick()`), positional arg landing on wrong parameter, and `old_state` read after mutation. Two focused unit tests added and confirmed passing.

#### Risk if not done
Blackboard continues claiming lifecycle automation that is not trustworthy.

---

### C2 — Resolve Broken Contacts Path

**Status: Complete**

#### Objective
Stop the contacts area from remaining in a broken, misleading legacy state.

#### Why this matters
The contacts domain currently looks present in the repo while being broken in practice. That pollutes repo truth and creates future confusion.

#### Expected work
- decide whether contacts should be removed, repaired, or isolated
- eliminate import of deleted `Contact` model class
- ensure repo no longer presents contacts as a live usable domain when it is not
- document the decision clearly if the feature is intentionally deferred

#### Likely files touched
- `backend/api/contacts/views.py`
- `backend/api/contacts/urls.py`
- `backend/users/models.py`
- any related migrations/docs if necessary

#### Done condition
- contacts path is no longer broken and ambiguous
- either the domain is repaired or it is clearly removed/isolated
- future work cannot mistake it for a stable live feature

#### Completion notes
Contacts domain isolated. Broken `Contact` model import removed from `views.py`. Views replaced with API-safe 501 stubs and a clear deferred marker. `Contact` model class is missing from `users/models.py`; migration and DB table remain. Domain is not mounted in the router.

#### Risk if not done
Broken legacy code continues to mislead future work and may become dangerous if routed later.

---

### C3 — Clean Dead / Shadowed / Misleading Modules

**Status: Complete**

#### Objective
Reduce false signals in the repo by removing or clearly marking modules that look authoritative but are not on the real execution path.

#### Why this matters
Dead or shadowed modules waste time, confuse future edits, and can accidentally reintroduce unsafe or outdated behavior.

#### Expected work
- identify dead or shadowed backend modules that look active
- identify flat files shadowed by package directories
- remove or clearly mark misleading modules
- reduce duplicate-looking code that future workers could edit by mistake

#### Likely files touched
- dead/shadowed contract view files
- lifecycle-related duplicate modules
- any stale modules identified as misleading in Sprint 01 or current-state review

#### Done condition
- dead/shadowed misleading modules are removed or clearly marked
- repo truth becomes easier to follow
- active code paths are no longer hidden behind misleading alternatives

#### Completion notes
Deleted three confirmed-dead package-shadowed files: `api/contracts/views.py` (shadowed by `views/` package), `engine/contracts/services.py` (shadowed by `services/` package), `contracts/services.py` (shadowed by `contracts/services/` package). All were verified unreachable via Python's import resolution. 12 existing tests confirmed passing after deletions.

#### Risk if not done
Future work continues to edit the wrong files and misread the true system.

---

### C4 — Clean Duplicate / Confusing Route Registrations

**Status: Complete**

#### Objective
Make route registration canonical and reduce route-surface confusion.

#### Why this matters
Duplicate or confusing route registration creates maintenance risk and can hide which path is truly live.

#### Expected work
- remove redundant route registrations
- confirm one canonical mounted path per domain
- review the obligations double-registration issue
- verify root routing structure is intentional and not stale

#### Likely files touched
- `backend/core/urls.py`
- `backend/api/router.py`
- any duplicate domain URL includes

#### Done condition
- redundant route registrations are removed
- one canonical route path exists per domain
- route structure is simpler and easier to trust

#### Completion notes
Deleted dead root URL config `backend/urls.py` (ROOT_URLCONF points to `core/urls.py`; this file was never loaded). Removed redundant `path("api/obligations/", ...)` re-mount from `core/urls.py` (already mounted via router). Removed exact duplicate `approval-requests` list pattern in `obligations/urls.py`. 37 tests confirmed passing after changes.

#### Risk if not done
Route ambiguity remains and future maintainers may change the wrong path.

---

### C5 — Canonicalize Contract/Version Flow

**Status: Complete**

#### Objective
Identify the real live contract/version flow and remove or clearly isolate broken or misleading competing paths.

#### Done condition
- one canonical contract/version flow is clearly identifiable in code
- broken, dead, or misleading competing version paths are removed, isolated, or explicitly marked

#### Completion notes
Live path confirmed as `api/contracts/version_views.py` (create/sign/reject), mounted directly in the contracts URL config. The engine-level `ContractVersionService` is not wired to any live view and has broken `version_repo.get()` calls (method does not exist in the repository). `test_full_contract_cycle.py` runs 0 tests due to an indentation bug — `test_full_contract_cycle` is a nested function inside `setUp`. Both files marked with explicit broken/inert headers. 20 live version negotiation tests confirmed passing.

---

### C6 — Canonicalize Activation / Payment / Lifecycle Paths

**Status: Complete**

#### Objective
Identify the real live activation, payment, and lifecycle paths and clearly isolate broken, bypassed, dead, or misleading competing paths.

#### Done condition
- one canonical activation path is clearly identifiable in code
- one canonical payment path is clearly identifiable in code
- one canonical lifecycle path is clearly identifiable in code
- competing paths in the narrow inspected set are isolated or explicitly marked

#### Completion notes
Live paths confirmed: activation via `obligations_views.py` → `ContractLifecycleService.create_obligation()` (per-obligation, not schedule-based); payment via `api/payments/views.py` direct ORM with inline `process_obligation_lifecycle()` calls; lifecycle automation via `run_lifecycle` → `execute_lifecycle_automation()` → `LifecycleRunnerService.tick()`. Four dead/misleading service files marked with isolation headers: `contracts/services/activation.py` (no live callers), `engine/contracts/services/activation_service.py` (only referenced by C5-marked dead code), `engine/contracts/services/payment_service.py` (dead and broken — calls nonexistent repo methods), `engine/payments/payment_service.py` (working engine-level service, tested, but not wired to the live API). 20 payment transition tests and 5 engine payment tests confirmed passing.

---

## Sprint Rules

Sprint 02 should stay focused on stabilization.

Do not expand this sprint into:
- Contract Pro implementation
- authority model implementation
- BusinessEntity redesign
- template strengthening
- notifications work
- workspace building
- broader UI/UX work

This sprint is only for core stabilization and repo truth cleanup.

---

## Sprint Dependencies

Sprint 02 assumes Sprint 01 is complete enough that the repo is no longer carrying its worst immediate trust breakers.

Minimum expected prior progress:
- password reset hotfix done
- webhook hotfix done
- secrets/config posture under control
- dangerous dormant public contract exposure removed

---

## Sprint Verification Requirements

Sprint 02 is not done just because code was cleaned.

For each item:
- the real path must be confirmed
- broken or misleading paths must be removed or clearly deprecated
- route or lifecycle behavior must be verified logically or by test/manual execution
- the repo should become easier to reason from after the sprint

At the end of Sprint 02:
- update the build tracker
- move completed stabilization items to **Done**
- unblock the next authority and boundary work

---

## Sprint Success Condition

Sprint 02 is successful if:
- lifecycle automation is no longer broken or ambiguous
- contacts are no longer broken repo noise
- dead/shadowed misleading modules are cleaned
- route registration is clearer and canonical
- the canonical contract/version flow is identifiable and competing paths are isolated
- the canonical activation/payment/lifecycle paths are identifiable and competing paths are isolated

All six conditions met. Sprint 02 is complete.

That means Blackboard will be standing on cleaner backend truth before moving into authority and boundary design.

---

## Summary

Sprint 02 is the first core-stabilization sprint.

Its purpose is simple:

> remove broken and misleading core paths so the Blackboard backend becomes cleaner, more trustworthy, and easier to build on