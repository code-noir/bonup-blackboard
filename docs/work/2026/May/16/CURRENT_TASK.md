# Current Task — 2026-05-16

Status: stabilization phase nearly complete.

C1, C2, and C3 critical fixes are complete.

C4 (`DATABASES` hardcoded to SQLite instead of PostgreSQL) is substantially
progressed:
- `requirements.txt` was added in commit `8ea3737` (`Add curated Python
  requirements`).
- `psycopg` was installed in the venv and import verified.
- `.env.example` documents Postgres variables and was committed as
  `f2b6146` (`Document Postgres environment variables`).
- `backend/core/settings.py` now uses PostgreSQL env vars and was committed
  as `92e8310` (`Use Postgres database settings`).
- `python manage.py check` passed.
- `python manage.py migrate --plan` succeeded against PostgreSQL.

Do not claim migrations were applied yet.

Current focus: begin with the real migration decision, then verify
backend/frontend/admin/auth workflows against PostgreSQL.
