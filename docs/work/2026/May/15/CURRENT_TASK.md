# Current Task — 2026-05-15

Status: C1, C2, and C3 critical fixes complete.

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

C4 (`DATABASES` hardcoded to SQLite instead of PostgreSQL) is in progress,
not complete.

Completed C4 prerequisites:
- C4.1: `requirements.txt` exists with curated Python requirements.
- C4.2: `psycopg` was installed in the venv and import verified.
- C4.3: `.env.example` documents Postgres variables and was committed as
  `f2b6146` (`Document Postgres environment variables`).

C4.4 has started: `backend/core/settings.py` has been edited to use
PostgreSQL env vars instead of SQLite, but it has not been verified yet.
The owner still needs to set or confirm real `.env` Postgres values
privately.

Next code agenda: finish C4.4 safely. Verify Postgres env booleans, run
`python manage.py check`, inspect the `settings.py` diff, then commit or
adjust C4.4. Do not claim C4 complete until verified.
