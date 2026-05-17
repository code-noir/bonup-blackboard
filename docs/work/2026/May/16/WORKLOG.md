# Worklog — 2026-05-16

## Project State Rollover

The May 15 stabilization session is closed out. C1, C2, and C3 are complete.
C4 is substantially progressed, but not fully complete.

Latest stabilization commits:
- `8ea3737` (`Add curated Python requirements`)
- `f2b6146` (`Document Postgres environment variables`)
- `92e8310` (`Use Postgres database settings`)

C4 status:
- `requirements.txt` was added.
- `psycopg` was installed in the venv and import verified.
- `.env.example` documents Postgres variables.
- `backend/core/settings.py` now uses PostgreSQL env vars.
- `python manage.py check` passed.
- `python manage.py migrate --plan` succeeded against PostgreSQL.

Important boundary: real migrations have not been applied yet.

Next session should begin with the real migration decision, then
backend/frontend/admin/auth workflow verification against PostgreSQL.
