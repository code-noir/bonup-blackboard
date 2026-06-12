# Current Technical Debt

## Architecture Risks

- Some domains use service/repository layering while others write models directly in views.
- `backend/api/ai/views.py` mixes routing, prompts, provider calls, parsing, and persistence.
- Authority is enforced through inline checks and service checks, not through one unified authority model.
- Contract state fields exist but are not consistently driven by API transitions.
- Frontend state is mostly local component state and localStorage.

## Workflow Confusion

- Contract review/counter workflow is separate from contract version workflow.
- A counter-generated revised contract does not automatically become version 2 or 3.
- Legacy `Counter.tsx` contains backend draft save logic, but `/counter` redirects to `/review`.
- `RequestChange` exists but is not wired.
- `sent` and `negotiating` version statuses exist but are not live transitions.

## Frontend Complexity

- `CreateContract.tsx` is protected, large, and known to contain static/hardcoded issues.
- `Dashboard.tsx` mixes static rows, localStorage records, and subscription locks.
- Several routes are placeholders while backend APIs exist.
- Review drafts are local-only.

## AI Instability

- Prompt output is parsed from model text.
- Counter response normalization includes fallback salvage logic for malformed JSON.
- Full-tier chat can execute AI-emitted JSON actions with minimal schema validation.
- No inspected rate limits, token accounting, or cost tracking.
- Anthropic client creation is repeated.
- Missing API key validation occurs at request time rather than startup or service boundary.

## State Inconsistencies

- `Contract.status`, `Contract.state`, `Contract.is_active`, and `Contract.version` are not the central live lifecycle drivers.
- `ContractVersion.status` is the strongest live contract negotiation state.
- Payment and service obligations use different state choices.
- Execution approvals are separate from contract acceptance but can be confused by naming.

## Scaling Risks

- Dashboard lacks backend aggregation.
- AI calls lack usage controls.
- Browser-local saved reviews are not durable product records.
- Counterparty identity by email string limits richer authorization and collaboration.
- Role switching deletes the original contract and cascades related records.

## Coupling Problems

- AI import writes contracts and obligations directly.
- AI actions create contracts without a dedicated validation/service boundary.
- Frontend review workflow depends on localStorage keys rather than backend contracts.
- Billing gates are inconsistent across AI endpoints.

## High-Risk Items

- `ImportContractView` checks `can_create_contract()` after creating the contract.
- Full-tier AI action execution writes database records based on model output.
- Role switch confirmation deletes the original contract.
- Static dashboard data may be mistaken for real records.

