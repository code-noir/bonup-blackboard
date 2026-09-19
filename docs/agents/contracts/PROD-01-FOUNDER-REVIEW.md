# PROD-01 Founder Proposal Review

> Status: Synthetic/non-executable review contract
> Authority: **PRODUCT KNOWLEDGE APPROVAL ONLY**

The review contract accepts one validated `PRODUCT_REQUIREMENT_PROPOSAL` and one
explicitly synthetic Founder review context. A deterministic immutable review
record binds the task ID, proposal ID, and canonical proposal SHA-256 digest to
exactly one decision: `ACCEPT`, `REJECT`, or `REQUEST_CHANGES`.

- `ACCEPT` records that the exact proposal is accepted as `APPROVED_INTERNAL`
  product direction.
- `REJECT` leaves it at `WORKING` and preserves the bounded reason and proposal
  as historical evidence.
- `REQUEST_CHANGES` leaves it at `WORKING`. A revision must use a new proposal
  ID and digest and name the prior proposal as predecessor; the reviewed proposal
  is never edited in place.

The review record never modifies proposal bytes. Any later proposal change or a
different proposal identity breaks the binding. No decision can produce
`PUBLICATION_ELIGIBLE`.

The v1 reviewer context is explicitly `SYNTHETIC_TEST_ONLY`; it is not
`AuthenticatedContext`, cryptographic enrollment, Genesis, or production Founder
authentication. Its fields are shaped for future attributable Founder review
without weakening the existing authentication architecture.

`ACCEPT` does not approve an ATS, assign ARCH-01, create an AgentRecord,
ExecutionGrant, reservation, fencing authority, command, repository permission,
push, deployment, activation, implementation, or publication. It only makes the
exact product proposal eligible as approved internal input to a future,
separately authorized ARCH-01 task. This contract performs no routing.

The synthetic reviewed task document records the proposal, review identity and
digest, Founder decision, resulting knowledge state, and result while retaining
the `HUMAN-READABLE PROJECTION — NOT EXECUTION AUTHORITY` boundary.

## Future authenticated review boundary

The production authentication contract uses the existing Founder root and
FounderSessions mechanism with purpose `PROD_PROPOSAL_REVIEW`. Its signed,
canonical binding contains only the binding version, exact persisted artifact
identity and digest, task ID, proposal ID and digest, one decision
(`ACCEPT`, `REJECT`, or `REQUEST_CHANGES`), and a bounded reason.

The challenge remains bound to the existing Founder root, nonce, freshness,
peer/process, boot, enrollment generation, and one-use session protections.
Challenge issuance is not a review decision. A future installed review adapter
must load and verify the immutable artifact before requesting the challenge;
this contract does not create a review record, change `WORKING`, create
authority, or route to ARCH. `SyntheticFounderReviewContext` remains
`SYNTHETIC_TEST_ONLY` and is never production authentication.

The software-side production adapter is `ProductionProductReviewAdapter`. It
loads the artifact through `ProposalArtifactStore`, consumes the one-use
session through `FounderSessions`, and writes a typed immutable
`ProductReviewRecord` through the controller Registry v2 transaction. The
record is published through the existing audit/outbox chain and contains only
the artifact/proposal binding, Founder root/session evidence, decision, bounded
reason, and knowledge-state result. Registry v2 migration is an explicit
precondition; it does not provision Founder authentication. No review is
accepted before the installed Founder transport can establish that session.
