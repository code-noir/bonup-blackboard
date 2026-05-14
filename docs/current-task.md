# Current Task

Status: C1 critical fix complete.

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

Where to pick up next session: continue the remaining critical fixes
from tech-debt.md. C2-C4 remain open.
