# Product Philosophy

## Current Implementation Grounding

The philosophy below is not generic product advice. It is inferred from:

- `docs/vision/FOUNDERS_VISION.md`
- `docs/current-state/architecture/*.md`
- `backend/contracts/models.py`
- `backend/api/contracts/*`
- `backend/ai/prompts.py`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/ContractReview.tsx`

Where the repo only suggests a direction, this document labels it as a recommendation or future direction.

## Modern Life Requires Structure

bonUP is built around the idea that people need stronger record systems. The code expresses this by turning informal events into structured records:

- Agreements become `Contract` records.
- Agreement drafts become immutable `ContractVersion` records.
- Commitments become payment or service obligations.
- Work activity becomes execution sessions and events.
- Follow-up decisions become approvals, value adjustments, or promoted obligations.
- Activity becomes an audit trail.

This is the operational version of the vision statement that records should be useful, provable, and available when needed.

## Agreements As Operational Systems

Blackboard does not treat an agreement as only text. A contract can lead to:

- Versions.
- Sign/reject decisions.
- Obligations.
- Payment tracking.
- Service completion.
- Execution evidence.
- Approval requests.
- Adjustments.
- Activity logs.
- Documents.

The current implementation does not fully automate that chain. For example, signing does not create obligations. But the data model and APIs show the product direction: an agreement should become an operating system for what happens next.

## Clarity

Clarity appears in three implementation patterns:

- Version numbers make negotiation attempts explicit.
- AI analysis produces summaries, key terms, red flags, and questions.
- Dashboard and review UI attempt to expose status, pending items, and saved review output.

The current gap is that dashboard clarity is partly placeholder-driven. `frontend/src/pages/Dashboard.tsx` contains static contract/payment/session examples and blank stat values.

## Accountability

Accountability appears in:

- Party checks through initiator and counterparty email.
- Business ownership checks for business entities.
- Contract Pro delegated editing control.
- Counterparty-only signing/rejection.
- Approval requests for execution events.
- Activity logging for contract creation, versioning, signing, rejection, and role switching.

The current gap is that authority is distributed across inline checks and services instead of a unified authority model.

## Continuity

Continuity means the record keeps meaning after creation. In code:

- `ContractVersion` preserves snapshots.
- Obligations preserve future commitments.
- Execution sessions/events preserve work history.
- Proof of work aggregates execution evidence.
- Notifications provide a user-scoped alert surface.

The current gap is no fully connected end-to-end frontend journey from signed contract to obligation execution to proof and dashboard continuity.

## Proof

Proof is visible in:

- `ObligationExecutionEvent` as structured work evidence.
- `ContractActivity` as audit trail.
- `ContractDocument` and uploads as attachment layers.
- AI prompts and vision docs that repeatedly mention proof.

PBVD itself is not fully implemented as a dedicated registry in the inspected code. It should be treated as future platform direction unless a future code pass finds the domain.

## Verification

Verification currently exists in several narrower places:

- Signup/email verification in auth.
- Counterparty identity through email match.
- Business ownership through `BusinessEntity.owner`.
- Approval flow for execution items.
- Contract version locking after signing.

The larger PBVD verification model is vision-level, not implemented as a complete workflow.

## Operational Memory

Operational memory is the repo's strongest recurring pattern:

- AI conversations are stored in `AIConversation.messages`.
- Contract versions are immutable.
- Activity is logged.
- Execution events and approval decisions persist.
- Local frontend saved contract reviews are stored in `localStorage`.

The frontend localStorage review store is useful for UX continuity, but it is weaker than backend persistence because it is browser-local and not shared across devices or users.

## Workflow Coordination

Workflow coordination currently happens through route-specific APIs and frontend pages:

```text
Dashboard
  -> Contract Review
    -> Analyze
    -> optional Counter
    -> local saved review

Contract API
  -> Create contract
  -> Create version
  -> Sign/reject version
  -> Create obligations
  -> Execute work
  -> Approve/reject execution item
```

The main product need is to connect these pieces into clearer workflows. This is a recommendation based on observed fragmentation, not an implemented feature.

