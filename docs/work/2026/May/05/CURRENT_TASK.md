Task: Replace the entire contents of docs/current-task.md with this 
exact content:

# Current Task

Status: Alignment phase complete.

Branch: restore-before-break (multiple commits not yet pushed)

All 12 architecture files in docs/current-state/architecture/ are 
current and code-grounded:
- identity.md
- entity_layer.md
- authority.md
- contract_lifecycle.md
- contract_pro.md
- obligations_lifecycle.md
- payments.md
- billing.md
- audit_activity.md
- documents_uploads.md
- sessions.md
- sol.md

README.md written as the folder index.

Where to pick up: alignment is done. Decide between writing 
tech-debt.md (consolidating gaps surfaced across all 12 files), 
pushing to GitHub (auth expired, needs token regen), pasting the 
project instructions template into Claude Project settings + CLAUDE.md, 
or starting code-level fixes for the security gap on /api/users/login/.

Do not commit.