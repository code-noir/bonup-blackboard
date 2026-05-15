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
   (`Prevent payment status patch bypass`). C3-C4 remain the
   smallest-scope highest-priority open items:
   - C3: add obligation amount_paid recompute on DELETE payment
   - C4: restore Postgres in DATABASES setting
   
   Then H-series items (file size limit, MIME validation, lifecycle 
   gate on contract-scoped payment create, etc.).

5. Document remaining secondary backend domains: ai, notifications, 
   engine, search, negotiation_prep, infrastructure, admin. Same 
   audit-and-write workflow as the 12 already done.

6. Frontend audit. Separate beast.
