# Repository Architecture

## Top-Level Shape

```text
bonup-blackboard/
  backend/      Django apps, API modules, domain models, services, engine helpers
  frontend/     React + Vite app
  docs/         architecture notes, work logs, specs, product direction
  dev/          local scripts, logs, specs, cheat sheets
  manage.py     Django entrypoint
```

## Backend Structure

The backend is a Django project under `backend/`.

Important areas:

- `backend/core/`: Django settings, URLs, ASGI/WSGI, Celery wiring.
- `backend/api/`: HTTP API modules grouped by domain.
- `backend/contracts/`: Blackboard contract and lifecycle models.
- `backend/ai/`: AI conversation model, prompts, and user context builder.
- `backend/billing/`: plans, subscriptions, feature gates, Stripe integration.
- `backend/bonup/`: platform entity foundation (`Soul`, `Entity`, `SoulEntity`).
- `backend/users/`: user profile and business entity models.
- `backend/contract_pro/`: delegated business contract authority.
- `backend/contract_templates/`: templates and instantiation service.
- `backend/engine/`: engine primitives/evaluators/state-machine style logic.
- `backend/infrastructure/repositories/`: repository wrappers used by services.
- `backend/activity/`: contract activity/audit logging.
- `backend/payments/`, `backend/sol/`, `backend/documents/`, `backend/uploads/`, `backend/notifications/`, `backend/sessions/`: supporting product domains.

## API Routing

`backend/core/urls.py` mounts API URLs under `/api/`.

`backend/api/router.py` includes:

- `/api/admin/`
- `/api/ai/`
- `/api/entities/`
- `/api/activity/`
- `/api/auth/`
- `/api/billing/`
- `/api/contracts/`
- `/api/documents/`
- `/api/notifications/`
- `/api/obligations/`
- `/api/payments/`
- `/api/prep/`
- `/api/search/`
- `/api/sessions/`
- `/api/sol/`
- `/api/obligation-templates/`
- `/api/payment-templates/`
- `/api/templates/`
- `/api/tools/`
- `/api/uploads/`
- `/api/users/`
- `/api/workspace/`

## Contract API Structure

`backend/api/contracts/urls.py` combines a DRF router for `ContractViewSet` with explicit paths for:

- obligations
- proof of work
- execution sessions/events
- approval requests
- value adjustments
- payment/service resolution
- management summary
- activity
- sessions
- documents
- versions
- role switching

This makes contracts the densest operational API module in the repo.

## Services And Repositories

There is a layered pattern in parts of the backend:

```text
API view
  -> application service
    -> engine primitive/evaluator
    -> infrastructure repository
      -> Django model
```

Examples:

- `ContractLifecycleService` creates obligations using engine primitives and repositories.
- `ObligationExecutionService` records execution items, runs `ExecutionEvaluator`, and creates approval requests.
- `ApprovalService` approves/rejects execution approvals and may create value adjustments or promotions.
- `TemplateInstantiationService` creates contracts and obligations from templates.

The pattern is not universal. Some API views still write models directly, especially `backend/api/ai/views.py`.

## AI Orchestration Layers

Current AI layers:

- `backend/ai/models.py`: stores conversations.
- `backend/ai/context.py`: builds user account context for chat.
- `backend/ai/prompts.py`: tiered chat prompts.
- `backend/api/ai/views.py`: routes, inline document prompts, Anthropic calls, parsing, action execution, contract import.

The AI domain has mixed responsibilities. `views.py` contains HTTP logic, prompt constants, JSON parsing, Anthropic client creation, action execution, PDF text extraction, and database writes.

## Workflow And State Systems

Main state-bearing models:

- `Contract.status`, `Contract.state`, and `Contract.version`.
- `ContractVersion.status` and `superseded`.
- `ContractObligation.state`.
- `ContractServiceObligation.state`.
- `ObligationExecutionSession.status`.
- `ContractApprovalRequest.status`.
- `ContractRoleSwitchRequest.status`.
- `Payment.status` in `backend/payments/models.py`.
- `Notification.is_read`.

Important caution: not every state field is actively driven by API transitions. Existing architecture docs identify several unused or partially used fields, especially on `Contract`.

## Frontend Structure

The frontend is a Vite React app.

Important areas:

- `frontend/src/App.tsx`: routing and high-level auth/admin shells.
- `frontend/src/api/client.ts`: Axios client with JWT attachment and refresh retry.
- `frontend/src/context/AuthContext.tsx`: auth and subscription state.
- `frontend/src/components/layout/`: app shell, sidebar, header, top/action/ad bars.
- `frontend/src/pages/`: product pages.
- `frontend/src/pages/admin/`: staff/operator pages.

## Frontend Routes

Current public routes:

- `/login`
- `/register`
- `/forgot-password`
- `/reset-password`
- `/verify-email`

Current authenticated routes:

- `/hub`
- `/dashboard`
- `/contracts/create`
- `/review`
- `/entities`
- `/profile`
- `/billing`
- `/contacts`

Several product routes redirect or render placeholders:

- `/contracts` and `/contracts/new` redirect to `/dashboard`.
- `/analysis` and `/counter` redirect to `/review`.
- `/ai`, `/templates`, `/search`, `/settings` are placeholders.
- obligations, payments, sessions, sol, and notifications use a Pay-As-You-Go lock surface in some cases.

## State Management

Frontend state is local React state plus `localStorage`:

- Auth tokens are stored under `bb_access` and `bb_refresh`.
- Contract reviews are stored under `bb_contract_reviews`.
- Legacy counter drafts are stored under `bb_counter_drafts`.
- Contacts use `frontend/src/lib/contacts.ts`.

There is no inspected Redux/Zustand/global workflow store.

## Current Architectural Pattern

The repo is a pragmatic Django/React application with partial domain layering. Some domains use service/repository boundaries; others are direct view-to-model implementations. The architecture is moving toward operational systems, but many workflows are still split across backend APIs, frontend local state, and placeholder UI.

