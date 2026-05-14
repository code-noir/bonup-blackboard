# Next Task — 2026-05-14

Continue remaining critical fixes from `docs/current-state/tech-debt.md`.

C1 is complete in commit `e51615f` (`Fix users login email verification
bypass`).

Remaining critical fixes:
- C2: make PATCH `/api/payments/<id>/` status read-only
- C3: add obligation `amount_paid` recompute on DELETE payment
- C4: restore Postgres in `DATABASES` setting
