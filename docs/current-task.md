# Current Task

Status: May 18 active session.

Branch: restore-before-break

May 17 work is closed. PostgreSQL migrations were applied successfully,
the superuser was created, and the signup email verification flow was
completed. Resend HTTPS email delivery replaced SMTP for production email
because SMTP timed out from the VPS. A fresh signup email was sent
successfully, the verification link worked, the account became verified,
and sign-in worked.

Verified flow was committed as:

```text
a819051 Complete signup email verification flow
```

May 18 starting focus: continue app workflow verification after
auth/signup. Do not claim May 18 verification is complete yet.

Next checks for this active session:
- login/logout
- password reset/change
- BON ID
- admin/operator console
- desktop Blackboard workflow audit
