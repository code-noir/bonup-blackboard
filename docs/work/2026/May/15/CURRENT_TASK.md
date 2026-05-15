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

Next code agenda: continue remaining critical fixes from
`docs/current-state/tech-debt.md`. C4 remains open.
