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
