# EDITOR_PROTECTION.md

This file documents the protection status of the contract editor/workspace and its dependencies.
It is the authoritative reference for any AI agent or contributor working in this repository.

---

## Protected Files

| File | Role | Protection Level |
|------|------|-----------------|
| `frontend/src/pages/CreateContract.tsx` | Contract editor/workspace — the primary product surface | **FROZEN** |
| `frontend/src/lib/contacts.ts` | localStorage contacts store consumed by the editor | **FROZEN** |

---

## Why These Files Are Protected

### `CreateContract.tsx`

This is the contract editor — the highest-priority asset in the bonUP Blackboard frontend. It is a
~3,900-line component that owns the full contract creation and editing experience. It has taken
significant iteration to reach its current state and must not be casually modified.

The file contains known issues that are intentionally left in place pending scoped approvals:
- `const USER_TIER = 'business'` — hardcoded tier (real value should come from AuthContext)
- `const ACTIVITY = [...]` — static hardcoded activity feed (no live data)
- `POST /api/contracts/analyze/` — wrong URL (real endpoint: `/api/ai/analyze-contract/`)
- `POST /api/contracts/counter/` — wrong URL (real endpoint: `/api/ai/counter-contract/`)
- Contract content (title, obligations, payments) is not persisted to the backend on save
- `bb_wip_contract_title` / `bb_wip_contract_id` written to localStorage but not synced to backend

These are **known, documented issues** — not things to silently fix. Each requires a dedicated,
scoped change with explicit approval.

### `frontend/src/lib/contacts.ts`

The editor imports and calls these exports directly:
- `loadContacts()` — used to populate the counterparty picker
- `saveContactFromParty()` — called after a counterparty is added to a contract
- `getContactInitials()` — used to render contact avatar initials in the editor UI
- `getContactDisplayName()` — used to render contact names in the editor UI
- `Contact` interface — shape must remain stable

A backend contacts API exists at `/api/contacts/` (fully implemented). Migration from localStorage
to the API is a planned task. Until that migration is explicitly approved and scoped, this module
must remain localStorage-backed and its exports must not be renamed or restructured.

---

## Rules

1. **No refactoring** of protected files without explicit written approval from the project owner.
2. **No renaming** of files, components, exports, or props in protected files.
3. **No cleanup** — do not remove "dead" code, consolidate state, or reorganize sections.
4. **No bug fixes** inside protected files unless the fix is explicitly scoped and approved.
5. **No splitting** — do not extract sub-components or hooks from CreateContract.tsx.
6. **No deletion** of protected files or their exports.
7. **Documentation and comments only** are permitted without approval (freeze notices, inline notes).

---

## Editor Entry Protocol

The editor is entered via URL query params:

```
/contracts/create?id=<contract-uuid>&entity=personal|<biz-uuid>[&name=<encoded-biz-name>]
```

All navigation into the editor must use this format. Do not add new entry patterns without
updating this document.

---

## Instructions for Future AI Interactions

If you are an AI agent reading this file:

- Do **not** refactor, reorganize, or "improve" `CreateContract.tsx` or `contacts.ts`.
- Do **not** fix the known issues listed above unless the user has given you explicit, scoped
  approval that references this file.
- If asked to work on the editor, read this file first and confirm the scope of the request
  before making any changes.
- If you are unsure whether a change affects the editor or its dependencies, **stop and ask**.
- The protection in this file overrides general coding conventions (DRY, cleanup, etc.).

---

## Change Log

| Date | Change | Approved By |
|------|--------|-------------|
| 2026-04-12 | Initial protection applied; freeze comments added to CreateContract.tsx and contacts.ts; CLAUDE.md updated | project owner |
