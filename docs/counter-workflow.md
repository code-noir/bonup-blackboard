# Counter Contract Workflow

## Purpose

The counter workflow helps a user negotiate against an uploaded or pasted contract by generating concerning clauses, counter language, a strategy, and a revised contract.

Primary implementation:

- `POST /api/ai/counter-contract/` in `backend/api/ai/views.py`
- `frontend/src/pages/ContractReview.tsx`
- Legacy page: `frontend/src/pages/Counter.tsx`

## Current Frontend Flow

The active route is `/review`. The legacy `/counter` route redirects to `/review`.

Current flow in `ContractReview.tsx`:

```text
Choose "Analyze + Counter"
  -> provide PDF or text
  -> run analysis
  -> enter counter terms
  -> generate counter
  -> save review draft to localStorage
```

## Backend Counter Flow

```text
POST /api/ai/counter-contract/
  -> read contract_text or PDF/upload_id
  -> read counter_terms or instructions
  -> create AIConversation
  -> call Anthropic with COUNTER_CONTRACT_PROMPT
  -> parse/normalize JSON
  -> return structured result
```

## Output Shape

The backend returns:

- `conversation_id`
- `summary`
- `concerning_clauses[]`
- `negotiation_strategy`
- `question_answers[]`
- `revised_contract`

Each concerning clause can include:

- `clause_reference`
- `concern`
- `counter_language`

## Outgoing Contract Generation

Current implementation distinction:

- The active `/review` workflow generates revised contract text but does not create a backend `Contract`.
- The legacy `Counter.tsx` page has a `handleSaveDraft()` path that posts to `/api/contracts/`, creates a placeholder contract, and then creates a version with the revised contract text.
- That legacy route is no longer directly reachable because `/counter` redirects to `/review`.

So outgoing contract generation exists in legacy frontend code but is not part of the active routed workflow.

## Clause Modifications

The AI returns counter language per concerning clause. These are displayed in the UI, but not persisted as backend clause modifications.

There is no inspected model for:

- clause object
- clause change
- redline
- counterparty response to a clause
- accepted/rejected clause proposal

## Workflow Transitions

The active review/counter workflow transitions are frontend-local:

```text
empty
  -> analyzed
  -> counter generated
  -> saved local review
```

It does not transition a `Contract` or `ContractVersion` record.

The contract API has separate version transitions:

```text
draft version
  -> signed
  -> rejected
  -> superseded by next version
```

These two systems are not yet integrated.

## Ownership Handling

The counter endpoint uses the authenticated user and creates an `AIConversation` owned by that user. It does not create a contract, so there is no contract owner/initiator handoff in the active route.

The legacy draft save path uses the current user as contract initiator through the contract API.

## Current Problems And Messy Areas

- Active counter workflow is local-only after AI response.
- Legacy counter draft save code exists but is no longer routed.
- AI output has no schema-backed persistence.
- No canonical clause or redline system.
- No backend negotiation object links a counter result to a contract version.
- Counter-generated revised contract does not automatically become version 2 or 3.
- Counter workflow and version negotiation workflow are separate systems.
- The AI parser includes salvage logic for malformed responses, indicating output instability.

## Recommended Direction

Recommendation, not current implementation:

- Persist review/counter results in a backend `ContractReview` or equivalent model.
- Let the user explicitly convert a revised contract into a `ContractVersion`.
- Add a clause/change model only if the product truly needs clause-level workflow.
- Keep the three-version cap when converting counter drafts into contract versions.

