## Next Task: Phase C / A3 — Define Contract Pro delegated-access model

### Status: Ready to start

### Dependencies
- A1 complete: authority baseline documented in `docs/current-state/BLACKBOARD_AUTHORITY_MODEL.md`
- A2 complete: negotiator vs signer distinction documented in the same file

### What A3 starts from

The authority model doc establishes that:
- No delegated-access concept exists in the backend today
- No Contract Pro role exists as a backend concept (no model, no permission class, no route, no schema field)
- There is no existing delegation mechanism to extend — A3 starts from zero

### A3 scope (from build tracker)

Define the Contract Pro delegated-access model:
- how Contract Pro access is granted
- whether it is business-scoped, contract-scoped, or both
- default permissions
- what Contract Pro cannot do by default (negotiation rights vs signing rights distinction from A2 is relevant here)
- revocation flow
- audit trail requirements

### Done condition (from build tracker)

Contract Pro grant/revoke/scope/permissions model is defined.

### Note

A3 is a model-definition task, not an implementation task. It should produce a documented Contract Pro authority model grounded in what the backend can support, not a full implementation. Implementation belongs to a later sprint.
