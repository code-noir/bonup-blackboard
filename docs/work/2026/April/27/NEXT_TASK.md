## Next: Domain Strengthening (D-series)

### Status: Not yet scheduled

### Context

Phase C (Authority and Boundary Confidence) is complete:
- A1–A5 done
- B1–B5 done

All D-series items (D1–D7) are currently Deferred in the build tracker. The next work is a scheduling decision: which D items to promote and in what order.

### D-series items (from tracker)

| ID | Task | Priority |
|---|---|---|
| D1 | Verify template instantiation end to end | P2 |
| D2 | Strengthen template family tests/confidence | P2 |
| D3 | Strengthen notification maturity | P2 |
| D4 | Strengthen activity/audit confidence | P2 |
| D5 | Clarify Blackboard role of uploads/documents | P2 |
| D6 | Decide whether workspace is truly phase-one scope | P2 |
| D7 | Improve admin/internal oversight confidence | P3 |

### Known follow-up items from B-lane inspection (not B-series scope, not yet scheduled)

- `session.contract` null-safety: if a contract is hard-deleted, `is_party(user, None)` is unguarded (AttributeError). Low probability path; not currently a user-facing exposure. Named here for scheduling.
- Four implementation gaps named in A5 (counterparty_user FK, signed_by FK, contract_pro plan seed, slug migration) — all deferred.
