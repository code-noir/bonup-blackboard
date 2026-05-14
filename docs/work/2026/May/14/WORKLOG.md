# Worklog — 2026-05-14

## C1 Critical Fix

C1 (`/api/users/login/` bypassed `email_verified`) was fixed and
committed as `e51615f` (`Fix users login email verification bypass`).

Fix approach: kept `/api/users/login/` available but changed it to
reuse `EmailOrUsernameTokenView`, the same verified login view used by
`/api/auth/token/`.

Verified by owner:

```bash
python manage.py test backend.api.tests.test_auth_login_verification
```

Result: Ran 4 tests in 11.304s, OK.
