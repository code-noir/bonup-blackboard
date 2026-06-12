# bonUP Overview

## Purpose

bonUP is the platform-level ecosystem in this repository. Blackboard is one product surface inside it, but the broader bonUP direction is record discipline: helping people keep structured, useful, verifiable records around agreements, obligations, payments, proof, content, and lifecycle accountability.

The clearest source for the platform philosophy is `docs/vision/FOUNDERS_VISION.md`. The clearest source for implementation is the backend domain split:

- `backend/bonup/` for the emerging `Soul`, `Entity`, and `SoulEntity` layer.
- `backend/users/` for user profile, bonID, verification, and business entities.
- `backend/contracts/` and `backend/api/contracts/` for Blackboard.
- `backend/sol/` and `backend/api/sol/` for the rotating savings group domain.
- `backend/documents/`, `backend/uploads/`, and `backend/activity/` for proof, files, and audit records.

## What bonUP Is In The Current Repo

bonUP is implemented as a Django backend plus React frontend. Its platform model is broader than contract creation:

- Identity and account verification exist in `backend/api/auth/`, `backend/users/`, and `backend/bonup/`.
- Entity foundations exist in `backend/bonup/models.py` and `backend/users/models.py`.
- Blackboard agreement workflows exist in `backend/contracts/` and `backend/api/contracts/`.
- Billing and feature gates exist in `backend/billing/` and `backend/api/billing/`.
- SOL exists as a separate domain in `backend/sol/`.
- Documents, uploads, notifications, sessions, payments, search, and activity each have backend API modules.

The frontend reflects the platform/product split:

- `/hub` renders the bonUP hub through `frontend/src/pages/BonupHub.tsx`.
- `/dashboard`, `/review`, `/contracts/create`, `/entities`, `/billing`, and admin routes sit inside `AppShell` in `frontend/src/App.tsx`.
- Many product routes are present as placeholders or locked surfaces, which means the implementation is still uneven across domains.

## Cultural And Intelligence Layer

The repo presents bonUP as an intelligence and structure layer for ordinary people, not only institutions. `docs/vision/FOUNDERS_VISION.md` says the problem is weak, scattered, incomplete, hard-to-verify records. The implementation supports that direction through:

- Stored identity records: `BonUserProfile`, `Soul`, `Entity`, `SoulEntity`, and `BusinessEntity`.
- Contract records with versions and parties: `Contract` and `ContractVersion`.
- Obligation records with state: `ContractObligation` and `ContractServiceObligation`.
- Audit/activity records: `backend/activity/models.py` and `backend/activity/log.py`.
- Document and upload layers: `backend/documents/`, `backend/uploads/`, and `backend/api/contracts/document_views.py`.
- AI context assembly from the user's contracts, obligations, templates, SOL records, and billing tier in `backend/ai/context.py`.

The current AI layer is not a general platform brain yet. It is a set of endpoints and prompts around chat, contract analysis, counter-contract generation, and contract import in `backend/api/ai/views.py`.

## Onboarding Philosophy

The current implementation indicates a user-first onboarding model:

- Email verification is part of the active current task history in `docs/current-task.md`.
- Authentication routes live in `backend/api/auth/`.
- The frontend starts public users at login/register/reset/verify routes, then redirects authenticated users to `/hub` or staff users to `/admin` in `frontend/src/App.tsx`.
- `frontend/src/context/AuthContext.tsx` carries user/subscription state used by dashboard, locks, and billing UI.

This is implementation evidence for an onboarding path, not proof of a finished onboarding curriculum.

## Educational Layer

The education layer is visible in prompts and UI, but it is not yet a complete learning product.

Current evidence:

- `backend/ai/prompts.py` tells the assistant to explain contracts, clauses, obligations, templates, billing, platform behavior, and negotiation choices in plain language.
- `frontend/src/pages/ContractReview.tsx` displays summaries, key terms, red flags, questions, concerning clauses, negotiation strategy, revised contract text, and question/answer sections.
- `frontend/src/pages/Analysis.tsx` remains as a legacy/redirected analysis-oriented page.

This means the repo currently teaches through workflow outputs rather than through a dedicated course or education module.

## Intended User Mindset

The current product direction expects users to treat agreements and proof as ongoing operational records. That is supported by:

- Version-limited contract negotiation in `backend/api/contracts/version_views.py`.
- Payment and service obligations in `backend/contracts/models.py`.
- Execution sessions and events in `backend/api/contracts/execution_views.py`.
- Approval requests and value adjustments in `backend/api/contracts/approval_views.py` and related services.
- Dashboard surfaces for active contracts, obligations, payments, sessions, and saved contract reviews in `frontend/src/pages/Dashboard.tsx`.

## Current Limits

Several bonUP concepts are documented or partially modeled but not fully wired:

- PBVD is described in `docs/vision/FOUNDERS_VISION.md`, but there is no complete PBVD domain model or registry workflow in the inspected code.
- Studjo is described in vision docs, but no implemented Studjo module was found in the current repo inventory.
- Entity/authority foundations exist, but `AuthorityHolder` and `AppointedAuthority` are not implemented according to `docs/current-state/architecture/entity_layer.md` and `authority.md`.
- The frontend dashboard uses static demo rows for some contract/payment/session sections in `frontend/src/pages/Dashboard.tsx`.

