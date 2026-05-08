## 2026-05-06

Alignment phase — domain MD verification + payments.md.

- Ran inventory audit on docs/current-state/architecture/. Found 6 
  substantive files + 7 stubs.
- Verification audits on all 6 substantive files:
  - entity_layer.md — 20/22 verified, 2 partial → tighten
  - authority.md — 38/38 verified → no change
  - contract_pro.md — 27/30 verified, 3 partial → tighten
  - contract_lifecycle.md — 48/50 verified, 2 partial → tighten
  - identity.md — 23/24 verified, 1 partial (security gap: 
    /api/users/login/ bypasses email_verified) → tighten
  - obligations_lifecycle.md — 30/43 verified, 4 mismatch → regenerate
- Regenerated obligations_lifecycle.md from code (commit 45cef06).
- Tightened 4 domain files (commit 8e981e3).
- Wrote payments.md from code with safe workflow (commit da51194).
- 3 commits on restore-before-break, not pushed (GitHub auth expired).

Findings to log in tech-debt.md when written:
- Security: /api/users/login/ bypasses email_verified gate
- Security: PATCH /api/payments/<id>/ bypasses state machine
- Bug: DELETE payment doesn't recompute amount_paid on obligation
- Inconsistency: ContractPaymentListCreateAPIView POST missing 
  lifecycle gate
- Architecture: SQLite hardcoded — was supposed to be Postgres, 
  AI swapped it silently at some point
- Architecture: Contract Pro permission matrix not wired to API
- Architecture: Engine-layer PaymentService unwired
- 5 open questions in payments.md
- Open questions in obligations_lifecycle.md (Obligation template, 
  obligation_templates module, payment_templates module, 
  process_obligation_lifecycle internals)

Confirmed during alignment: no feature creep — code matches founder's 
vision domains.

Next: 5 stubs remaining (billing, audit_activity, documents_uploads, 
sessions, sol) + README last.

---

### 2026-05-06 (continued)

Alignment phase complete. 5 stubs + README written from code.

- billing.md written from code (3 models, 10 routes, 5 webhook 
  handlers, 17 gate functions, 19 cross-domain call sites).
- audit_activity.md written from code (1 model, log_activity helper, 
  2 read endpoints, 25 call sites across 4 domains).
- Follow-up audit confirmed CreateContract.tsx ACTIVITY panel is a 
  static placeholder; user-facing /api/activity/ endpoints are 
  orphaned with zero frontend consumers. Logged as gap #6 in 
  audit_activity.md.
- documents_uploads.md written from code (2 models, 6 real routes, 
  5 stub routes, 4 storage call sites).
- sessions.md written from code (1 model, 9 HTTP routes, 1 WebSocket 
  consumer, 3 inbound + 4 outbound event types, LiveKit token 
  generation isolated to one file).
- sol.md written from code (7 models, 12 HTTP views, 2 PDF views, 
  4 billing gate call sites, fully self-contained domain).
- README.md written as folder index with reading order and 
  maintenance rules.
- Header alignment: 5 previously-tightened files (identity, 
  entity_layer, authority, contract_lifecycle, contract_pro) had 
  outdated "Status: Draft" headers; updated to "Status: Current" 
  to match content.

Additional findings to log in tech-debt.md when written:

Billing:
- No SubscriptionPlan seed/fixture in repo
- _MAX_BUSINESSES contains both legacy and current slug sets
- SubscriptionAPIView.post() bypass when STRIPE_SECRET_KEY unset
- billing_period always written as "monthly" by Stripe sync
- start_trial defined and tested but never called from production

Audit/Activity:
- contract_updated activity_type defined but never written
- backend/api/activity/serializers.py is a stale, dead file
- log_activity silently swallows notification failures
- No atomicity enforcement at helper level
- session_held fires from three distinct call sites in sessions views
- User-facing /api/activity/ endpoints have zero frontend consumers; 
  CreateContract.tsx ACTIVITY panel is a static placeholder

Documents/Uploads:
- No file size limit anywhere
- No MIME type or magic byte validation
- No file name sanitization in storage key construction
- DocumentsViewSet at /api/documents/ is a stub returning hardcoded 
  strings
- ContractDocumentDeleteAPIView orphans Upload rows and S3 objects
- is_draft_document field exists and is filterable but never set
- AWS_QUERYSTRING_AUTH not configured

Sessions:
- LiveKit access token has no explicit TTL
- CHANNEL_LAYERS uses InMemoryChannelLayer; broken in multi-process 
  deployment
- LiveSession.contract is nullable but POST requires contract_id
- No LiveKit webhook handler
- presentation_controller updated via WebSocket only, never returned 
  via HTTP
- Scheduled sessions can be transitioned directly to ended

Sol:
- No audit trail; zero log_activity calls
- No services layer; all business logic inline in views
- No automated status transitions
- No reminders, escalations, or background processing
- Co-manager permission enforcement is inline
- SolContract.signed_by_member never enforced
- Naming clash with contracts.Contract
- Member self-service blocked for non-bonUP participants
- SolContribution backfill covers only first open payout
- Deactivated member's pending contributions not cleaned up

State at end of session:
- 12 architecture files all current and code-grounded
- 8 commits on restore-before-break, not pushed (GitHub auth still 
  expired)
- tech-debt.md not yet written
- CLAUDE.md not yet created in repo root
- Project instructions not yet pasted into Claude Project settings

Next: write tech-debt.md, then push to GitHub, then move into 
pre-launch hardening (security fixes, Postgres restore, file size 
limits, etc.).

---

## 2026-05-07

Tech-debt consolidation + workflow codification.

- GitHub auth fixed. Personal Access Token regenerated. credential.helper 
  configured. push.autoSetupRemote configured globally. 
  restore-before-break pushed and tracking origin/restore-before-break.
- Wrote docs/current-state/tech-debt.md consolidating gaps from all 12 
  architecture files plus 2026-05-06 worklog findings. 41 items: 5 
  Critical, 10 High, 15 Medium, 9 Low, plus open questions grouped by 
  domain. Each item cites source architecture file and underlying code 
  citation. Includes severity legend, suggested order of attack, and 
  update rule.
- Updated CLAUDE.md with Section 19 (Workflow Conventions Established 
  2026-05-06 / 2026-05-07). Five subsections: repo orientation, 
  audit-and-write workflow, commit discipline, status header 
  convention, severity language. Sections 1-18 preserved unchanged.
- Pattern observed: Claude Code truncates large appends with nested 
  formatting (markdown code blocks inside markdown blocks). Workaround: 
  use 4-space-indented text instead of fenced code blocks for examples 
  when appending. Section 19.4 had to be rewritten once for this 
  reason.

State at end of session:
- 13 documentation files current and pushed: 12 architecture files + 
  README + tech-debt.md + CLAUDE.md.
- 10+ commits on restore-before-break, all pushed.
- Project instructions still not pasted into Claude.ai settings.
- Branch cleanup not yet done.
- No code-level fixes started yet.

Next session: project instructions paste, branch cleanup, then begin 
C1-C4 critical code fixes.
