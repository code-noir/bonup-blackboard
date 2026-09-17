# PROD-01 Synthetic Task Cycle

> Status: Development/test behavior only
> Authority: **SYNTHETIC — NON-AUTHORITATIVE — NOT APPROVED**

The cycle validates a bounded synthetic Founder direction, passes only that
validated task envelope to a deterministic fake model, validates the returned
`PRODUCT_REQUIREMENT_PROPOSAL`, and produces canonical proposal bytes, a
proposal digest, and a human-readable synthetic task document.

It proves that the PROD-01 task and proposal contracts compose deterministically;
malformed, secret-bearing, self-promoting, authority-seeking, executable, and
unbounded outputs fail closed; and the resulting document clearly identifies
itself as a human projection rather than execution authority.

It does not prove model quality, activate PROD-01, authenticate a founder,
approve a requirement, create an Agent Control Task/AgentRecord/grant, execute
commands, access a repository/database/network, persist registry state, assign
ARCH-01, or authorize implementation, integration, publication, or deployment.

The fake adapter lives only in `tests/agent_control/prod_cycle_fixtures.py` and
has no model SDK, credentials, network, shell, or production dependency. A
future real-model integration must be separately designed and authorized; it
must preserve bounded input/output validation and cannot reuse the synthetic
adapter marker as authority.

The synthetic task-document adapter is deliberately separate from authoritative
Task projection because current Agent Control ownership rules do not enable
PROD-01. It reuses deterministic metadata, evidence references, proposal digest,
and the prominent `HUMAN-READABLE PROJECTION — NOT EXECUTION AUTHORITY` boundary
without pretending that synthetic state is authoritative registry state.
