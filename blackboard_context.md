# BLACKBOARD SYSTEM — MASTER CONTEXT

This document provides the full architectural context for the Blackboard system. Any AI assistant or developer must read and understand this file before making changes to the codebase.

This file exists so that project knowledge can be transferred to new AI sessions without losing system context.

------------------------------------------------------------

PROJECT NAME

Blackboard

------------------------------------------------------------

PROJECT PURPOSE

Blackboard is a lifecycle-driven platform designed to manage agreements, obligations, and events over time.

The system is not simply a contract management system. It is a Lifecycle Engine capable of modeling relationships, obligations, payments, and state transitions over time.

The engine is intended to support future applications including:

- contract lifecycle management
- obligation tracking
- financial obligations and payments
- legal workflow automation
- event-driven lifecycle systems
- business agreement monitoring

The architecture is designed to scale and eventually support thousands of users and multiple integrated systems.

------------------------------------------------------------

CORE ARCHITECTURAL PRINCIPLE

Blackboard is built around a Lifecycle Engine.

The lifecycle engine governs how obligations and contracts change state over time.

Examples of lifecycle states include:

- pending
- active
- overdue
- resolved
- defaulted
- breached

The engine ensures that transitions between states follow deterministic rules and cannot be violated by external systems.

------------------------------------------------------------

SYSTEM LAYERS

The backend system is organized into clear architectural layers.

backend/
    engine/
    api/
    infrastructure/
    core/

Each layer has a distinct responsibility.

------------------------------------------------------------

ENGINE LAYER

Location:

backend/engine/

This layer contains the core business logic of the system.

The engine layer must remain framework independent and must not depend on Django or any web framework.

Responsibilities of the engine layer include:

- lifecycle processing
- domain entities
- domain services
- business rules
- deterministic state transitions
- contract and obligation logic

This layer is the most important part of the system.

------------------------------------------------------------

ENGINE MODULES

Major engine modules include:

backend/engine/contracts/
backend/engine/payments/
backend/engine/lifecycle_core/

Contracts module handles contract domain logic.

Payments module handles payment processing and payment services.

Lifecycle core module manages state transitions for obligations.

------------------------------------------------------------

CONTRACT DOMAIN

Location:

backend/engine/contracts/domain/contract.py

The Contract domain object represents the aggregate root for obligations.

Responsibilities of the Contract object include:

- holding obligations
- aggregating obligation states
- computing overall contract state
- coordinating contract lifecycle

Contract states include:

- active
- fulfilled
- breached

Contract state is derived from the state of its obligations.

Aggregation rules include:

If any obligation is defaulted or breached → contract becomes breached.

If all obligations are resolved → contract becomes fulfilled.

Otherwise → contract remains active.

------------------------------------------------------------

OBLIGATION LIFECYCLE

Location:

backend/engine/contracts/obligations/lifecycle.py

This module determines lifecycle transitions for obligations.

Supported obligation states include:

- pending
- active
- overdue
- resolved
- defaulted
- breached

State transitions depend on:

- due dates
- time progression
- payment activity

The lifecycle engine must be deterministic.

------------------------------------------------------------

PAYMENT OBLIGATION PRIMITIVE

The payment obligation object handles financial responsibilities associated with contracts.

Responsibilities include:

- amount due
- amount paid
- remaining balance
- payment application
- payment validation
- preventing overpayment

Payments may partially or fully resolve obligations.

Payment activity may trigger lifecycle recalculation.

------------------------------------------------------------

PAYMENT SERVICE

Location:

backend/engine/payments/payment_service.py

Responsibilities include:

- validating payment amounts
- applying payments to obligations
- preventing negative or excessive payments
- updating payment balances
- triggering lifecycle recalculations

Payment service is responsible for payment application logic.

------------------------------------------------------------

CONTRACT COORDINATOR

Location:

backend/engine/contracts/services/contract_coordinator.py

The coordinator orchestrates contract lifecycle operations.

Responsibilities include:

- loading contracts
- loading obligations
- executing obligation lifecycle processing
- refreshing contract state
- persisting updated objects

The coordinator acts as an orchestration layer between domain logic and repositories.

------------------------------------------------------------

INFRASTRUCTURE LAYER

Location:

backend/infrastructure/

This layer handles persistence and repository patterns.

Repositories translate domain entities into database representations.

Examples include:

backend/infrastructure/repositories/contract_repository.py  
backend/infrastructure/repositories/contract_obligation_repository.py  

Repositories isolate database access from domain logic.

------------------------------------------------------------

API LAYER

Location:

backend/api/

The API layer exposes engine functionality via REST endpoints.

This layer uses Django REST Framework.

The API layer must not contain business logic. It should only orchestrate calls to engine services.

------------------------------------------------------------

API DOMAINS

The API is organized into multiple domains.

Examples include:

contracts  
payments  
obligations  
activity  
notifications  
search  
documents  
users  
billing  
templates  
workspace  
tools  
sessions  

Each domain typically contains:

views.py  
urls.py  

------------------------------------------------------------

EXAMPLE API ENDPOINTS

Examples of REST endpoints include:

GET /api/contracts  
POST /api/contracts  
GET /api/contracts/{id}  
PUT /api/contracts/{id}  
DELETE /api/contracts/{id}

Additional contract related endpoints include:

POST /api/contracts/{id}/payments  
GET /api/contracts/{id}/obligations  
POST /api/contracts/{id}/obligations  

These endpoints expose lifecycle engine functionality to external clients.

------------------------------------------------------------

CURRENT DEVELOPMENT STAGE

The system is currently in the API construction phase.

The lifecycle engine core has been partially implemented.

Work currently underway includes:

- expanding API endpoints
- stabilizing endpoint structure
- preparing Django admin integration
- preparing frontend integration

------------------------------------------------------------

FUTURE SYSTEM COMPONENTS

Planned system components include:

Admin management interface  
Frontend user application  
Live session module  
Template builder  
Workspace tools  
User collaboration tools

------------------------------------------------------------

DEVELOPMENT PHILOSOPHY

Key architectural principles include:

1. Domain logic must remain inside the engine layer.

2. The API layer should only orchestrate engine operations.

3. Infrastructure layer handles persistence and repositories.

4. State transitions must always remain deterministic.

5. Controllers must never contain business logic.

6. Domain services must remain independent of framework logic.

------------------------------------------------------------

AI ASSISTANT USAGE

When using AI to assist development:

The AI must read this context document before producing any code.

AI must respect the architectural separation between:

engine layer  
API layer  
infrastructure layer

AI should not introduce architectural changes that violate these rules.

------------------------------------------------------------

PROJECT GOAL

The long-term goal of Blackboard is to build a scalable lifecycle platform capable of supporting thousands of users and multiple workflow systems.

The platform prioritizes:

- deterministic lifecycle transitions
- modular architecture
- domain driven design
- long term extensibility
- clear system boundaries

------------------------------------------------------------

END OF CONTEXT