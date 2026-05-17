# Next Task — 2026-05-15

Continue remaining critical fixes from `docs/current-state/tech-debt.md`.

C1 is complete in commit `e51615f` (`Fix users login email verification
bypass`).

C2 is complete in commit `5aeddd0` (`Prevent payment status patch bypass`).

C3 is complete in commit `09a467c` (`Recompute obligation amount on payment
delete`).

Remaining critical fixes:
- C4: restore Postgres in `DATABASES` setting.

C4 is in progress, not complete:
- C4.1 complete: `requirements.txt` exists with curated Python requirements.
- C4.2 complete: `psycopg` installed in the venv and import verified.
- C4.3 complete: `.env.example` documents Postgres variables and was
  committed as `f2b6146` (`Document Postgres environment variables`).
- C4.4 started: `backend/core/settings.py` uses PostgreSQL env vars instead
  of SQLite, but this is not verified yet.

Next session: owner confirms real `.env` Postgres values privately, verify
env booleans, run `python manage.py check`, inspect the `settings.py` diff,
then commit or adjust C4.4.
