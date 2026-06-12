# AI Architecture

## Overview

The AI domain currently supports:

- Tier-aware chat with stored conversation history.
- Contract analysis.
- Counter-contract generation.
- Contract import from PDF into backend records.

Implementation files:

- `backend/ai/models.py`
- `backend/ai/context.py`
- `backend/ai/prompts.py`
- `backend/api/ai/views.py`
- `backend/api/ai/urls.py`

## Model Provider

The backend uses the Anthropic SDK through `anthropic.Anthropic(...)`. The model name is read from `settings.ANTHROPIC_MODEL`, with a default in settings and `backend/api/ai/views.py`.

Anthropic client construction is repeated inside API views instead of centralized in an AI client service.

## Conversation Model

`AIConversation` stores:

- user
- optional contract
- conversation type
- messages JSON array
- timestamps

The messages array uses:

```json
{"role": "user", "content": "message"}
```

or:

```json
{"role": "assistant", "content": "message"}
```

## Prompt Layers

Tiered chat prompts live in `backend/ai/prompts.py`:

- `BASIC_PROMPT`
- `ADVANCED_PROMPT`
- `FULL_PROMPT`

They include `{{user_context}}`, replaced at runtime by `AIChatView`.

Document prompts live inline in `backend/api/ai/views.py`:

- `ANALYZE_CONTRACT_PROMPT`
- `COUNTER_CONTRACT_PROMPT`
- `IMPORT_CONTRACT_PROMPT`

This split is an architectural inconsistency.

## User Context

`backend/ai/context.py` builds chat context from:

- bonID/profile data.
- user name/email.
- billing/subscription.
- recent contracts.
- upcoming payment obligations.
- upcoming service obligations.
- active templates.
- SOL management and membership data.

This context is used only by the chat workflow, not by analyze/counter/import document endpoints.

## AI Chat Flow

```text
POST /api/ai/chat/
  -> get AI tier
  -> load/create AIConversation
  -> build user context
  -> select tier prompt
  -> append user message
  -> call Anthropic
  -> append assistant message
  -> if full tier, parse JSON action block
  -> optionally create records
  -> save conversation
```

Full-tier action blocks can call:

- `instantiate_template`
- `create_contract`

These actions can write contracts, versions, and obligations.

## Contract Analysis Flow

```text
POST /api/ai/analyze-contract/
  -> accept contract_text, file, or upload_id
  -> extract text if PDF
  -> create AIConversation
  -> call Anthropic with analysis prompt
  -> parse JSON block
  -> return summary, key_terms, red_flags, questions
```

The frontend calls this in `frontend/src/pages/ContractReview.tsx`.

## Counter-Generation Flow

```text
POST /api/ai/counter-contract/
  -> accept contract_text, file, or upload_id
  -> accept counter_terms / instructions
  -> create AIConversation
  -> call Anthropic with counter prompt
  -> parse and normalize JSON
  -> return clauses, strategy, question_answers, revised_contract
```

The parser includes salvage helpers for malformed AI JSON, especially around revised contract text.

## Import Flow

```text
POST /api/ai/import-contract/
  -> require full AI tier
  -> accept PDF only through file/upload_id
  -> extract PDF text
  -> call Anthropic with import prompt
  -> parse extracted JSON
  -> create Contract
  -> create ContractVersion
  -> create obligations only if counterparty user exists
  -> save AIConversation
  -> increment billing usage if can_create_contract passes
```

Current implementation issue: the billing creation gate is checked after the contract is already created.

## Review System

The review system is the product workflow that combines analysis and counter-generation:

- Backend endpoints are separate.
- Frontend `ContractReview.tsx` combines them into one user workflow.
- Saved reviews are stored in browser `localStorage`, not in a backend review model.
- Admin review route exists in frontend (`AdminContractReviews.tsx`), but saved user reviews are local browser records.

## Clause Extraction

Clause extraction exists only as AI output shape:

- `concerning_clauses[]`
- `clause_reference`
- `concern`
- `counter_language`

There is no canonical clause extraction model or persistent clause database table.

## Lifecycle Intelligence

The lifecycle evaluator in `backend/engine/lifecycle_core/execution/evaluator.py` is deterministic rule logic, not an LLM call. It currently:

- Always returns `approval_required`.
- Always uses `separate_charge`.
- Suggests side obligation when duration is at least 120 minutes or estimated cost is at least 150.
- Otherwise keeps the item as an event.

This is a first-pass workflow intelligence layer, not a full AI reasoning system.

## Current AI Limitations And Problems

Current implementation issues found in code and existing architecture docs:

- AI views mix HTTP handling, prompts, parsing, provider calls, and database writes.
- Anthropic client setup is repeated.
- Document prompts are inline in views instead of in `backend/ai/prompts.py`.
- Chat action execution trusts model-emitted JSON with minimal schema validation.
- No inspected AI rate limiting or token/cost tracking.
- Missing API key validation before request-time provider calls.
- General `/api/ai/chat/` has no frontend integration found under `frontend/src/`.
- Contract analysis/counter endpoints are connected to frontend, but saved output is local-only.
- Import creates records before `can_create_contract` is checked.
- Clause handling is output-only, not canonical.

## Recommended Separation

Recommendation, not current implementation:

- Move provider calls into `backend/ai/client.py`.
- Move document prompts into `backend/ai/prompts.py`.
- Move parsing/normalization into `backend/ai/parsers.py`.
- Move action execution/import persistence into services.
- Add schema validation for AI action blocks.
- Add AI usage logging, throttling, and cost controls.
- Persist contract reviews server-side if they are product records.

