# Dashboard System

## Current Dashboard File

Primary file:

- `frontend/src/pages/Dashboard.tsx`

The dashboard is routed at `/dashboard` in `frontend/src/App.tsx`.

## Current Structure

The dashboard renders:

- intro text
- stat cards
- viewing-as selector
- trial banners
- Sol member banner
- Power Tools
- Saved Contract Reviews
- Recent Activity
- Contracts Overview
- Upcoming Obligations
- Recent Payments
- Upcoming Live Sessions

## Workflow Dashboard Concept

The dashboard is trying to become the Blackboard operational home:

```text
Dashboard
  -> contract review tool
  -> saved reviews
  -> contract status
  -> obligations
  -> payments
  -> sessions
  -> activity
```

This concept is only partially implemented.

## Operational Widgets

Current widgets:

- Active Contracts
- Obligations Due
- Pending Payments
- Upcoming Sessions

These currently display dash values rather than live counts.

## Pending Actions

Potential pending-action concepts exist in backend:

- pending role switch requests
- pending approval requests
- due obligations
- unread notifications
- unsigned/rejected contract versions

The current dashboard does not yet aggregate those backend states.

## Contract States

The dashboard displays a static contracts table with statuses such as Active, Pending, Completed. This is not currently fetched from `/api/contracts/`.

Backend contract/version state is more complex:

- `Contract.status`
- `Contract.state`
- `ContractVersion.status`
- obligation states

The dashboard should eventually decide which state is user-facing and how it maps backend state to UX labels.

## Calendar Integration Ideas

Recommendation, not current implementation:

The dashboard could use due dates from:

- `ContractObligation.due_date`
- `ContractServiceObligation.due_date`
- sessions
- payments
- approval deadlines
- role switch expiration dates

No complete calendar UI was found in the inspected active dashboard.

## Ecosystem / Intelligence Layer

The dashboard imports review data from localStorage and points users to the review tool. It does not currently surface AI chat, user context, or AI recommendations.

Recommendation:

- Show live pending actions first.
- Show AI review drafts and next steps as operational records.
- Distinguish bonUP ecosystem items from Blackboard contract work.
- Pull data from backend APIs instead of static rows/local browser records where the record must persist.

## Current Risks

- Static data can mislead users.
- Browser-local review drafts can disappear or fail to sync.
- Paywall lock copy and backend billing gates need alignment.
- No central dashboard API exists in the inspected code; data would require multiple calls or a new aggregation endpoint.

