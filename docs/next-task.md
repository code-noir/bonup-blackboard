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

4. Code-level fixes from tech-debt.md. Triage from the Suggested Order 
   of Attack section. C1 is complete in commit `e51615f` (`Fix users 
   login email verification bypass`). C2 is complete in commit `5aeddd0`
   (`Prevent payment status patch bypass`). C3 is complete in commit
   `09a467c` (`Recompute obligation amount on payment delete`). C4 is in
   progress, not complete.
   - C4.1 complete: `requirements.txt` exists with curated Python requirements.
   - C4.2 complete: `psycopg` installed in the venv and import verified.
   - C4.3 complete: `.env.example` documents Postgres variables and was
     committed as `f2b6146` (`Document Postgres environment variables`).
   - C4.4 started: `backend/core/settings.py` uses PostgreSQL env vars
     instead of SQLite, but this is not verified yet.
   - Next session: owner confirms real `.env` Postgres values privately,
     verify env booleans, run `python manage.py check`, inspect the
     `settings.py` diff, then commit or adjust C4.4.
   
   Then H-series items (file size limit, MIME validation, lifecycle 
   gate on contract-scoped payment create, etc.).

5. Document remaining secondary backend domains: ai, notifications, 
   engine, search, negotiation_prep, infrastructure, admin. Same 
   audit-and-write workflow as the 12 already done.

6. Frontend audit. Separate beast.
