# bonUP PROD-01 runtime composition

The Product Direction application boundary is a bounded AF_UNIX client. Its
only normal operations are `SUBMIT_PRODUCT_DIRECTION`, `READ_PROPOSAL`, and
`REQUEST_FOUNDER_REVIEW`; the optional observation operation is not a
projection path. The socket is `/run/bonup-agent-control/prod01.sock` and is
selected only by the root-owned
`/etc/bonup-agent-control/product-direction.json` contract. Kernel peer UID,
GID, process identity, socket ownership, mode, message size, and timeout are
validated on both sides.

Agent Control owns the fixed PROD-01 model identity, provider route, one-call
zero-tool/no-retry policy, proposal validation, and the private
`ProposalArtifactStore`. Django receives only a bounded safe proposal
projection. It never receives an artifact path, raw artifact bytes, provider
response, model credential, Founder session material, or execution metadata.

The provider credential is expected only after provisioning as the fixed
systemd credential file:

`/run/credentials/bonup-agent-control/prod01-openai-api-key`

It must be a regular root-owned `0440` file with group `bonup-agentctl`
(GID 3000), bounded to 4096 bytes, and unreadable through a symlink or a
writable ancestor. The Agent Control process reads it inside the trusted
adapter; it is never supplied through Django, a browser request, a task row,
an artifact, argv, repository files, or logs. Missing or invalid state leaves
PROD-01 unavailable.

Founder review remains an explicit Agent Control callback boundary around
`FounderIntake`, `FounderSessions`, `FounderTransport`, and
`ProductionProductReviewAdapter`. Operator JWT may initiate and observe only;
it cannot authorize a decision. Review status is observational. Normal
projection is exclusively:

`ProductReviewRecord → PRODUCT_REVIEW_COMPLETED outbox → DomainEventDeliveryWorker → TrustedDjangoProjectionBoundary → Product Direction and Blackboard consumers`

The event transport includes the verified event and the bounded safe proposal
projection so Django does not reopen Agent Control-owned artifact files. Each
consumer retains its own inbox/acknowledgement and remains idempotent.

This composition enables only PROD-01 proposal work, Founder review, Registry
v3, durable event delivery, and trusted Django projection. ARCH routing,
execution workers, other agents, Speaker, publication authority, and agent
activation remain disabled.
