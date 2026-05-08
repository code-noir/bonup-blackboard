

# Next Task

Outstanding work, in roughly the order Project Claude has recommended:

1. Push to GitHub. Auth expired earlier in the project. Diagnose with 
   `git remote -v`. If https → regenerate Personal Access Token. If 
   ssh → check SSH key. Several commits sit on restore-before-break 
   that have not been pushed.

2. Write tech-debt.md. Consolidate the gaps surfaced across all 12 
   architecture files into one prioritized list. Project Claude will 
   provide the prompt when ready.

3. Paste project instructions into Claude Project settings and create 
   CLAUDE.md in repo root. Template was drafted earlier; not yet 
   pasted.

4. Branch cleanup. 6 branches exist. restore-before-break is truth. 
   Consolidate with main when ready.

5. Vision update. One or two features have been built that aren't yet 
   reflected in the founder's vision document. Reconcile.

6. Code-level fixes from gaps. Triage AFTER tech-debt.md is written. 
   Project Claude advised: small-scope security fixes during alignment 
   (e.g., /api/users/login/ bypass), larger refactors (SQLite → 
   Postgres restoration, silent except handlers, Contract Pro 
   permission matrix wiring, file size limits, LiveKit token TTL, 
   InMemoryChannelLayer → Redis) during pre-launch hardening phase. 
   Pre-launch hardening estimated 2-3 weeks total work.

7. Founder's vision audit. Confirmed current; no feature creep 
   detected.

