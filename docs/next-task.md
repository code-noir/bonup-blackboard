# Next Task

Outstanding work, in roughly the order Project Claude has recommended:

1. Paste project instructions into Claude.ai project settings. Template 
   was drafted by ChatGPT earlier in the project. Not yet pasted into 
   the web interface. Separate from CLAUDE.md (which is for Claude 
   Code in the terminal); this one is for Project Claude in chat.

2. Branch cleanup. 6 branches exist. restore-before-break is truth and 
   is now pushed. Run `git branch -a` to see what is there. Decide 
   what to delete and whether to consolidate with main.

3. Vision update. One or two features have been built that are not yet 
   reflected in the founder's vision document. Reconcile.

4. Finish C4 Postgres stabilization and app-level verification. C1 is
   complete in commit `e51615f` (`Fix users login email verification
   bypass`). C2 is complete in commit `5aeddd0` (`Prevent payment status
   patch bypass`). C3 is complete in commit `09a467c` (`Recompute obligation
   amount on payment delete`). C4 is substantially progressed:
   - `requirements.txt` was added in commit `8ea3737` (`Add curated Python
     requirements`).
   - `psycopg` was installed in the venv and import verified.
   - `.env.example` documents Postgres variables and was committed as
     `f2b6146` (`Document Postgres environment variables`).
   - `backend/core/settings.py` now uses PostgreSQL env vars and was
     committed as `92e8310` (`Use Postgres database settings`).
   - `python manage.py check` passed.
   - `python manage.py migrate --plan` succeeded against PostgreSQL.
   - Real migrations have not been applied yet.
   - Immediate next sequence: make the real migration decision, then verify
     backend/frontend/admin/auth workflows against PostgreSQL.
   
   Then H-series items (file size limit, MIME validation, lifecycle 
   gate on contract-scoped payment create, etc.).

5. Document remaining secondary backend domains: ai, notifications, 
   engine, search, negotiation_prep, infrastructure, admin. Same 
   audit-and-write workflow as the 12 already done.

6. Frontend audit. Separate beast.
