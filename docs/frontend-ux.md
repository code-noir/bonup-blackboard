# Frontend UX Structure

## App Shell And Routing

Frontend entrypoints:

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/layout/AppShell.tsx`

The React app uses `react-router-dom`. Public auth routes sit outside the app shell. Authenticated product routes mostly sit inside `AppShell`.

## bonUP Ecosystem Mode

`/hub` is the main ecosystem route and renders `BonupHub`. It is authenticated but not wrapped in the Blackboard app shell. This separates platform-level bonUP entry from the Blackboard operational workspace.

## Blackboard Operational Mode

Blackboard routes inside `AppShell` include:

- `/dashboard`
- `/contracts/create`
- `/review`
- `/entities`
- `/contacts`
- `/billing`
- `/profile`
- admin routes

Several older routes redirect into the newer review/dashboard model:

- `/contracts` -> `/dashboard`
- `/contracts/new` -> `/dashboard`
- `/analysis` -> `/review`
- `/counter` -> `/review`

## Dashboard Philosophy

The dashboard currently aims to be an operational overview:

- stats cards
- viewing-as selector
- trial/subscription banners
- power tools
- saved contract reviews
- recent activity
- contracts overview
- upcoming obligations
- recent payments
- upcoming live sessions

But several sections are static placeholders or locked panels, so the implementation is not yet a true live command center.

## Workflow Mode

The clearest active workflow screen is `ContractReview.tsx`:

```text
Start New Review
  -> choose analysis only or analysis + counter
  -> provide PDF/text
  -> analyze
  -> optionally generate counter
  -> save review draft
```

The protected editor in `CreateContract.tsx` is a large workspace-style page with tools for contract details, sections, parties, obligations, payments, attachments, templates, calculator, calendar, permissions, analytics, analysis, counter, settings, and tutorial. The file header warns not to modify it without explicit approval and documents known issues.

## State-Driven UI

Current frontend state patterns:

- Auth/subscription state comes from `AuthContext`.
- Axios tokens live in localStorage.
- Saved contract reviews live in localStorage.
- Legacy counter drafts live in localStorage.
- Dashboard locks some features for Pay-As-You-Go users.
- Many route surfaces are placeholders.

There is no inspected global workflow state manager.

## Current Screens

Implemented or partially implemented:

- Login/register/reset/verify
- bonUP Hub
- Dashboard
- Contract Review
- Create Contract workspace
- Contacts
- Entities
- Profile
- Billing
- Admin pages

Placeholder or redirect surfaces:

- AI Assistant
- Templates
- Search
- Settings
- old Contracts list/new route
- old Analysis/Counter routes

## Current UX Gaps

- Dashboard mixes live localStorage review data with static demo rows.
- Contract review saves locally, not as backend records.
- The active review workflow does not convert revised contracts into contract versions.
- The contract editor is protected and known to have hardcoded/static areas.
- Obligations/payments/sessions are backend domains but not fully visible as live frontend workflows.
- Some billing/plan text in frontend may not match backend plan naming and should be audited before user-facing release.
- The app has multiple modes but lacks a single clear workflow map for users.

