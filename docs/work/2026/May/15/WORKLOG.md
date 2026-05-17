# Worklog — 2026-05-15

## C2 Critical Fix

C2 (`PATCH /api/payments/<id>/` bypassed the payment state machine) was
fixed and committed as `5aeddd0` (`Prevent payment status patch bypass`).

Fix approach: made `PaymentSerializer.status` read-only so
`PATCH /api/payments/<id>/` cannot directly mutate payment status. Status
changes must go through dedicated transition endpoints.

Verified by owner:

```bash
python manage.py test backend.api.tests.test_payment_transitions
```

Result: Ran 22 tests in 67.261s, OK.

## C3 Critical Fix

C3 (`DELETE /api/payments/<id>/` left `ContractObligation.amount_paid`
inflated) was fixed and committed as `09a467c` (`Recompute obligation
amount on payment delete`).

Fix approach: `DELETE /api/payments/<id>/` now recomputes the linked
obligation's `amount_paid` when a payment is deleted, so deleted confirmed
payments cannot leave obligation totals inflated.

Verified by owner:

```bash
python manage.py test backend.api.tests.test_payment_transitions
```

Result: Ran 26 tests in 73.930s, OK.

## C4 Postgres Restore Prep

C4 (`DATABASES` hardcoded to SQLite instead of PostgreSQL) is in progress,
not complete.

Completed:
- C4.1: `requirements.txt` exists with curated Python requirements.
- C4.2: `psycopg` was installed in the venv and import verified.
- C4.3: `.env.example` documents Postgres variables and was committed as
  `f2b6146` (`Document Postgres environment variables`).

Started but not verified:
- C4.4: `backend/core/settings.py` has been edited to use PostgreSQL env
  vars instead of SQLite.

Remaining:
- The owner still needs to set or confirm real `.env` Postgres values
  privately.
- Next session should verify Postgres env booleans, run
  `python manage.py check`, inspect the `settings.py` diff, then commit or
  adjust C4.4.
