# Next Task

Queue of remaining work, appended over time as tasks emerge.

## Secondary backend domain documentation

Six secondary domains remain. Same audit-and-write workflow used for
the 12 primary domains and ai.md.

- notifications — called by log_activity from every audit event;
  affects deliverability across the platform
- engine — unwired engine layer; documenting it surfaces what is
  salvageable vs dead code
- negotiation_prep — has FK to LiveSession; standalone workflow
- search — read-only consumer of multiple domains
- admin — admin panel views (separate /admin/activity/ endpoint
  already noted in audit_activity.md)
- infrastructure — unknown until inspection

## AI chat runtime investigation

Backend wired but does not work in production. Different muscle than
documentation: read code looking for failure paths, possibly run
requests to reproduce. Could be quick or could be a rabbit hole.
Schedule for a session with full attention.

## Critical fixes from tech-debt.md (C1–C6)

Daylight work, sharpest brain.

- C4: restore Postgres in DATABASES setting (settings change, no
  code)
- C1: disable or patch /api/users/login/ verification bypass
- C2: make PATCH /api/payments/<id>/ status read-only
- C3: add obligation amount_paid recompute on DELETE payment
- C6: fix ImportContractView gate ordering — move
  can_create_contract check before transaction.atomic() block; if
  gate fails, return 403 before any write
- C5: add structured error logging to log_activity

## High fixes from tech-debt.md (H1–H10)

After Critical fixes. File size limit, MIME validation, lifecycle
gate on contract-scoped payment create, LiveKit token TTL,
InMemoryChannelLayer to Redis, ContractDocumentDeleteAPIView S3
cleanup, no LiveKit webhook handler, no SubscriptionPlan seed,
PaymentResolutionService divergence.

## Frontend audit

Separate beast. Same audit-and-write discipline expected.

## Branch cleanup Phase 2

Decide whether restore-before-break becomes the new main; decide on
backup branches; revisit feature/contract-import.
