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
