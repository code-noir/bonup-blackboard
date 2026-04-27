## Next Task: Phase C / B1 — Verify BusinessEntity isolation in multi-business scenarios

### Status: Ready to start

### Dependencies
- C5 complete: contract/version flow canonicalized
- C6 complete: activation/payment/lifecycle paths canonicalized
- A1–A5 complete: authority model fully defined

### B1 scope (from build tracker)

Verify that BusinessEntity isolation holds correctly in multi-business scenarios:
- confirm that contracts, obligations, and related records belonging to one business cannot bleed into another business owned by the same user
- confirm that default queries do not aggregate across businesses unintentionally
- confirm isolation is tested and trusted

### Done condition (from build tracker)

Multi-business owner tests confirm default business separation.
