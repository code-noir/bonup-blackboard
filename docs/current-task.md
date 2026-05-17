# Current Task

Status: C1, C2, and C3 critical fixes complete. C4 stabilization is nearly
complete and substantially progressed, but real migrations have not been
applied yet.

Branch: restore-before-break (synced with origin)

C1 (`/api/users/login/` bypassed `email_verified`) was fixed and
committed as `e51615f` (`Fix users login email verification bypass`).
The endpoint remains available and now reuses `EmailOrUsernameTokenView`,
the same verified login view used by `/api/auth/token/`.

Verified by owner:

```bash
python manage.py test backend.api.tests.test_auth_login_verification
```

Result: Ran 4 tests in 11.304s, OK.

C2 (`PATCH /api/payments/<id>/` bypassed the payment state machine) was
fixed and committed as `5aeddd0` (`Prevent payment status patch bypass`).
The fix made `PaymentSerializer.status` read-only so payment status cannot
be directly mutated through PATCH; status changes must go through the
dedicated transition endpoints.

Verified by owner:

```bash
python manage.py test backend.api.tests.test_payment_transitions
```

Result: Ran 22 tests in 67.261s, OK.

C3 (`DELETE /api/payments/<id>/` left `ContractObligation.amount_paid`
inflated) was fixed and committed as `09a467c` (`Recompute obligation
amount on payment delete`). The fix makes `DELETE /api/payments/<id>/`
recompute the linked obligation's `amount_paid` when a payment is deleted,
so deleted confirmed payments cannot leave obligation totals inflated.

Verified by owner:

```bash
python manage.py test backend.api.tests.test_payment_transitions
```

Result: Ran 26 tests in 73.930s, OK.

C4 (`DATABASES` hardcoded to SQLite instead of PostgreSQL) is substantially
progressed.

Completed C4 stabilization work:
- `requirements.txt` was added in commit `8ea3737` (`Add curated Python
  requirements`).
- `psycopg` was installed in the venv and import verified.
- `.env.example` documents Postgres variables and was committed as
  `f2b6146` (`Document Postgres environment variables`).
- `backend/core/settings.py` now uses PostgreSQL env vars and was committed
  as `92e8310` (`Use Postgres database settings`).
- `python manage.py check` passed.
- `python manage.py migrate --plan` succeeded against PostgreSQL.

Do not claim migrations were applied yet. The next session should begin with
the real migration decision, then backend/frontend/admin/auth workflow
verification against PostgreSQL.
