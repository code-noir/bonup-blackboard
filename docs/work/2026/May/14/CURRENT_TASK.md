# Current Task — 2026-05-14

Status: C1 critical fix complete.

C1 (`/api/users/login/` bypassed `email_verified`) was fixed and
committed as `e51615f` (`Fix users login email verification bypass`).

Verified by owner:

```bash
python manage.py test backend.api.tests.test_auth_login_verification
```

Result: Ran 4 tests in 11.304s, OK.

Next code agenda: continue remaining critical fixes from
`docs/current-state/tech-debt.md`. C2-C4 remain open.
