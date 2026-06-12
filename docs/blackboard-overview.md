# Blackboard Overview

## Definition

Blackboard is the contract and agreement-centered product surface inside bonUP. In the current repository it is implemented through contract models, versioning, obligation tracking, execution events, approval flows, activity logs, documents, AI review tools, and frontend dashboard/workspace screens.

Core evidence:

- Backend contract domain: `backend/contracts/`
- Contract API: `backend/api/contracts/`
- AI contract tools: `backend/api/ai/views.py`
- Frontend workspace/review/dashboard: `frontend/src/pages/CreateContract.tsx`, `frontend/src/pages/ContractReview.tsx`, `frontend/src/pages/Dashboard.tsx`
- Existing architecture docs: `docs/current-state/architecture/contract_lifecycle.md`, `obligations_lifecycle.md`, `ai.md`

## Operational Workspace

Blackboard is not implemented as only a file vault. It has operational records:

- `Contract` stores the agreement container, initiator, counterparty email, structure type, entity context, metadata, status, and version cap.
- `ContractVersion` stores immutable contract text snapshots.
- `ContractObligation` stores payment obligations.
- `ContractServiceObligation` stores service obligations.
- `ObligationExecutionSession` and `ObligationExecutionEvent` store work/proof activity under obligations.
- `ContractApprovalRequest`, `ContractValueAdjustment`, and `ContractObligationPromotion` store workflow consequences from execution items.

The frontend currently presents Blackboard as a dashboard plus review/workspace tools, not as a fully complete operational cockpit.

## Contract Workflow Environment

The live contract lifecycle is version-based:

```text
Contract container
  -> ContractVersion v1
  -> optional v2
  -> optional v3
  -> sign or reject
```

Important rule: Blackboard contracts have a maximum of 3 versions. This is enforced by `Contract.max_versions` in `backend/contracts/models.py` and by `ContractVersionCreateAPIView` in `backend/api/contracts/version_views.py`.

After version 3, the implementation blocks additional versions. Parties must start a new contract after the cap.

## Negotiation System

Current negotiation behavior is narrow and version-based:

- Initiator creates versions.
- Counterparty signs or rejects versions.
- Rejection can include warnings near the version cap.
- `RequestChange` exists as a model but is not wired into the live API.
- Role switching exists through request/confirm endpoints, but confirmation deletes the original contract and creates a fresh contract with swapped roles.

Current negotiation is therefore not a rich two-sided clause-commenting system. It is a controlled version submission and decision loop.

## Lifecycle Management Concept

The lifecycle implementation extends beyond signing:

- Obligations can be created against a contract/version.
- Execution sessions can be opened under payment or service obligations.
- Execution items are evaluated by an engine component.
- Every current evaluator result requires approval.
- Approval can create value adjustments and promote larger execution items into side obligations.
- Proof of work can be assembled for obligations.

However, signing a contract does not automatically create obligations. Obligations are created manually through API flows, AI import flows, template instantiation, or other service paths.

## AI Workflow Engine

Blackboard AI currently has four backend capabilities:

- Chat with stored conversation history: `POST /api/ai/chat/`
- Contract analysis: `POST /api/ai/analyze-contract/`
- Counter-contract generation: `POST /api/ai/counter-contract/`
- Contract import from PDF: `POST /api/ai/import-contract/`

The AI system is implemented in `backend/api/ai/views.py`, `backend/ai/prompts.py`, `backend/ai/context.py`, and `backend/ai/models.py`. It uses Anthropic via the `anthropic` Python SDK.

The frontend currently wires contract analysis and counter-generation into `frontend/src/pages/ContractReview.tsx`. The general chat endpoint has no frontend caller found under `frontend/src/`.

## Current Product Shape

Blackboard is currently a mix of:

- Implemented backend APIs.
- Partially connected frontend workflows.
- Protected editor/workspace code in `frontend/src/pages/CreateContract.tsx`.
- Static or placeholder dashboard areas.
- Strong domain intent in docs and prompts.

This means a new AI assistant should treat Blackboard as real but incomplete: contract, AI review, obligation, proof, activity, payment, session, and document domains exist, but not all are wired into one clean user workflow.

