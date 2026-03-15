BONUP CONTRACT ENGINE
ARCHITECTURAL SUMMARY — CURRENT STATE

This document describes the current architecture, structure, business logic, and technical state of the Bonup Contract Engine as implemented. It is intended to be reviewed by engineers or AI systems for structural analysis, critique, and future evolution planning.

⸻

	1.	SYSTEM PURPOSE

The Bonup Contract Engine is a financial lifecycle engine designed to manage installment-based contractual obligations. Its responsibilities include:
	•	Activating signed contracts
	•	Generating installment schedules
	•	Representing financial obligations
	•	Processing payments against obligations
	•	Evaluating obligation state transitions
	•	Aggregating obligation states into contract-level status

The engine is focused specifically on monetary installment obligations and does not yet implement full legal enforcement, dispute resolution, or risk assessment logic.

⸻

	2.	ARCHITECTURAL OVERVIEW

The system is structured conceptually into three layers:

A. Domain Layer (Pure Logic)
B. Service Layer (Business Coordination)
C. Infrastructure Layer (Persistence)

The design follows a domain-first approach with repository abstractions for persistence. Domain objects are not directly coupled to ORM models.

⸻

	3.	DOMAIN LAYER

Location:
backend/engine/contracts/obligations/

This layer contains pure logic and does not directly access the database.

3.1 PaymentObligation (primitives.py)

PaymentObligation represents a single installment obligation.

Core Attributes:
	•	obligor_id
	•	obligee_id
	•	amount_due (Decimal)
	•	amount_paid (Decimal, default 0.00)
	•	due_date (datetime)
	•	state (string, default “active”)

Core Behaviors:
	•	apply_payment(amount)
	•	remaining_balance()

Behavioral Rules:
	•	amount_paid increases when apply_payment is called
	•	overpayment is capped at amount_due
	•	negative payments are rejected at service level
	•	remaining_balance = amount_due - amount_paid

The object is mutable in memory but not inherently tied to database persistence.

3.2 Obligation State Evaluator (state.py)

Function:
evaluate_obligation_state(obligation, current_time)

This is a pure function that determines the correct state of an obligation based on its data.

Current States:
	•	active
	•	overdue
	•	resolved

State Rules:
	•	If amount_paid >= amount_due → resolved
	•	Else if current_time > due_date → overdue
	•	Else → active

There is currently no implementation for:
	•	grace period
	•	defaulted
	•	cancelled
	•	disputed

3.3 Schedule Generator (scheduler.py)

Function:
generate_obligation_schedule(obligor_id, obligee_id, total_amount, installments, start_date, interval_days)

Behavior:
	•	Converts total_amount to Decimal
	•	Converts installments to int
	•	Splits total_amount evenly across installments
	•	First installment receives any remainder
	•	Generates due dates spaced by interval_days
	•	Returns list of PaymentObligation instances

This function is pure and does not persist anything.

⸻

	4.	SERVICE LAYER

Location:
backend/engine/contracts/services/
backend/engine/payments/

Services coordinate domain logic and persistence.

4.1 ContractActivationService

File:
activation_service.py

Responsibility:
Activates a signed contract and generates obligations.

Flow:
	1.	Fetch contract via ContractRepository
	2.	Fetch latest version via ContractVersionRepository
	3.	Ensure version.status == “signed”
	4.	Determine start_date (default utcnow)
	5.	Generate obligation schedule
	6.	Persist each obligation using ContractObligationRepository
	7.	Return list of generated obligations

This service acts as a bridge between domain logic and the persistence layer.

4.2 ContractCoordinator

File:
contract_coordinator.py

Responsibility:
Refresh obligation states and compute contract-level state.

Flow:
	1.	Retrieve obligations for contract via repository
	2.	For each obligation:
	•	Evaluate new state using evaluate_obligation_state
	•	Persist state change if different
	3.	Compute contract-level state based on obligations

Contract State Logic:
	•	If no obligations → active
	•	If any obligation is “defaulted” → breached
	•	If all obligations are “resolved” → fulfilled
	•	Else → active

Note:
“defaulted” is referenced but not currently produced by state evaluator.

Contract state is computed but not yet persisted to the contract model.

4.3 PaymentService

File:
backend/engine/payments/payment_service.py

Responsibility:
Apply payments to obligations.

Flow:
	1.	Validate payment amount > 0
	2.	Apply payment to PaymentObligation
	3.	Re-evaluate obligation state
	4.	Return structured result:
	•	success (bool)
	•	new_state (string)

Supported Scenarios:
	•	Partial payment
	•	Full payment
	•	Overpayment (capped)
	•	Negative payment rejection
	•	Overdue payment evaluation

PaymentService directly mutates the in-memory PaymentObligation object.

⸻

	5.	INFRASTRUCTURE LAYER

Location:
backend/infrastructure/repositories/

Repositories abstract database interaction.

Current Repositories Used:
	•	ContractRepository
	•	ContractVersionRepository
	•	ContractObligationRepository

Responsibilities:
	•	Fetch contract entities
	•	Fetch contract versions
	•	Persist obligations
	•	Retrieve obligations by contract

Domain objects are passed into repositories for persistence.

⸻

	6.	SUPPORTED BUSINESS FLOWS

6.1 Contract Activation Flow

Input:
Signed contract

Process:
	•	Validate contract version
	•	Generate installment obligations
	•	Persist obligations

Output:
Stored obligations with installment schedule

6.2 Payment Flow

Input:
Obligation + payment amount

Process:
	•	Validate amount
	•	Apply payment
	•	Cap overpayment
	•	Recalculate state

Output:
Updated obligation state and payment result

6.3 Lifecycle Evaluation Flow

Triggered by:
ContractCoordinator.refresh_contract_obligations()

Process:
	•	Evaluate each obligation state
	•	Persist state changes
	•	Compute aggregate contract state

⸻

	7.	OBLIGATION STATE MACHINE (CURRENT)

States:
	•	active
	•	overdue
	•	resolved

Transitions:
active → overdue (if due date passed and unpaid)
active → resolved (if fully paid)
overdue → resolved (if fully paid)

No grace period or default logic exists yet.

⸻

	8.	CONTRACT STATE AGGREGATION

Contract state is derived from obligation states.

Rules:
	•	If any obligation = defaulted → breached
	•	If all obligations = resolved → fulfilled
	•	Else → active

Defaulted is not yet fully implemented in obligation state logic.

Contract state is not currently persisted.

⸻

	9.	SYSTEM STRENGTHS

	•	Clear separation between domain and persistence
	•	Deterministic schedule generation
	•	Pure state evaluation logic
	•	Repository abstraction
	•	Partial and full payments supported
	•	Overpayment capped safely
	•	Unit tests passing
	•	Core flows functioning

⸻

	10.	CURRENT LIMITATIONS AND RISKS

	•	No grace period logic
	•	No defaulted state implementation
	•	Contract state not persisted
	•	No transaction boundary definition
	•	No idempotency mechanism for payments
	•	No concurrency handling
	•	No domain event system
	•	No invariant enforcement at aggregate root level
	•	No audit trail
	•	No dispute or cancellation handling
	•	No formalized state machine structure
	•	No validation for malformed schedule inputs

⸻

	11.	DESIGN PHILOSOPHY

The engine follows a simplified domain-driven design approach:
	•	Domain primitives encapsulate behavior
	•	Pure functions evaluate state
	•	Services coordinate business workflows
	•	Repositories abstract persistence
	•	Mutable domain objects are allowed

This is not a full DDD implementation but aligns conceptually.

⸻

	12.	CURRENT ENGINE IDENTITY

The system is currently:

A deterministic installment-based contract lifecycle engine
with payment processing and obligation state evaluation.

It is not yet:
	•	A hardened financial ledger
	•	A regulatory-compliant accounting system
	•	A credit risk system
	•	A legally complete contract enforcement engine

⸻

	13.	STABILITY STATUS

	•	All current tests passing
	•	Core flows stable
	•	Architecture frozen
	•	Expandable foundation established

⸻

END DOCUMENT

⸻






flowchart TD

%% =========================================================
%% DJANGO APPLICATION LAYER
%% =========================================================

subgraph DJANGO_LAYER["Django Application Layer"]

API["API Endpoints"]
ADMIN["Django Admin"]
MODELS["Django Models"]

API --> SERVICES
ADMIN --> SERVICES
MODELS --> REPOSITORIES

end


%% =========================================================
%% REPOSITORY LAYER
%% =========================================================

subgraph REPOSITORIES["Infrastructure Repositories"]

CONTRACT_REPO["ContractRepository"]
VERSION_REPO["ContractVersionRepository"]
OBLIGATION_REPO["ContractObligationRepository"]

end


%% =========================================================
%% CONTRACT ENGINE
%% =========================================================

subgraph CONTRACT_ENGINE["Contract Engine"]

COORDINATOR["ContractCoordinator"]
ACTIVATION["ContractActivationService"]
VERSION_SERVICE["ContractVersionService"]
RUNNER["LifecycleRunnerService"]
PROJECTION["ContractProjectionService"]
RECONSTRUCTION["ContractReconstructionService"]

end


%% =========================================================
%% DOMAIN LAYER
%% =========================================================

subgraph DOMAIN["Domain Objects"]

CONTRACT_DOMAIN["Contract Domain Object"]

end


%% =========================================================
%% LIFECYCLE ENGINE
%% =========================================================

subgraph LIFECYCLE_ENGINE["Lifecycle Core"]

MANAGER["LifecycleManager"]

subgraph STATE_ENGINE["State Engine"]

EVALUATOR["State Evaluator"]
ESCALATION["Escalation Rules"]
STATE_CONSTANTS["State Constants"]

end

subgraph EVENTS["Lifecycle Events"]

EVENT_RECORDER["EventRecorder"]
LIFECYCLE_EVENT["LifecycleEvent"]

end

subgraph INSTANCES["Lifecycle Instances"]

OBLIGATION_INSTANCE["ObligationInstance"]

end

subgraph SCHEDULER["Obligation Scheduler"]

OBLIGATION_SCHEDULER["ObligationScheduler"]

end

subgraph PRIMITIVES["Obligation Primitives"]

PAYMENT_OBLIGATION["PaymentObligation"]
SERVICE_OBLIGATION["ServiceObligation"]

end

end


%% =========================================================
%% PAYMENT ENGINE
%% =========================================================

subgraph PAYMENT_ENGINE["Payment Engine"]

PAYMENT_SERVICE["PaymentService"]
PAYMENT_GATEWAY["MockPaymentGateway"]

end


%% =========================================================
%% CONNECTIONS
%% =========================================================

SERVICES --> COORDINATOR
SERVICES --> VERSION_SERVICE
SERVICES --> ACTIVATION
SERVICES --> RUNNER
SERVICES --> PROJECTION
SERVICES --> RECONSTRUCTION

COORDINATOR --> CONTRACT_DOMAIN

ACTIVATION --> OBLIGATION_SCHEDULER
OBLIGATION_SCHEDULER --> PAYMENT_OBLIGATION
OBLIGATION_SCHEDULER --> SERVICE_OBLIGATION

RUNNER --> MANAGER

MANAGER --> EVALUATOR
MANAGER --> ESCALATION

EVALUATOR --> STATE_CONSTANTS

PAYMENT_SERVICE --> PAYMENT_GATEWAY
PAYMENT_SERVICE --> PAYMENT_OBLIGATION

EVENT_RECORDER --> LIFECYCLE_EVENT
EVENT_RECORDER --> OBLIGATION_INSTANCE

REPOSITORIES --> CONTRACT_DOMAIN

OBLIGATION_REPO --> PAYMENT_OBLIGATION
OBLIGATION_REPO --> SERVICE_OBLIGATION

CONTRACT_REPO --> CONTRACT_DOMAIN
VERSION_REPO --> CONTRACT_DOMAIN






BONUP LIFECYCLE ENGINE + CONTRACT ENGINE
ARCHITECTURE DOCUMENT
--------------------------------------------------

SYSTEM OVERVIEW
--------------------------------------------------

This system is composed of two tightly connected engines:

1) Lifecycle Engine
2) Contract Vertical Engine

The Lifecycle Engine is a generic obligation lifecycle processor.

The Contract Engine is a vertical implementation that uses the lifecycle engine to manage real-world contracts composed of obligations such as services and payments.

The architecture separates domain logic from persistence so the lifecycle engine can operate independently of Django models.


HIGH LEVEL SYSTEM PURPOSE
--------------------------------------------------

The system models real-world agreements as executable lifecycle objects.

A contract produces obligations.
Obligations move through lifecycle states.
Lifecycle automation evaluates obligations over time.

The system supports:

- Payment obligations
- Service obligations
- Recurring schedules
- Lifecycle automation
- Default escalation
- Contract state projection
- Payment processing
- Contract reconstruction (importing existing real-world contracts)

The engine is designed so the lifecycle logic can operate independently of the database.


ARCHITECTURAL LAYERS
--------------------------------------------------

The system is structured into several layers.

backend
│
├ engine
│   ├ lifecycle_core
│   ├ contracts
│   └ payments
│
├ infrastructure
│   └ repositories
│
└ contracts (Django models)


The separation is intentional:

Lifecycle Engine → pure domain logic
Contract Engine → business logic
Infrastructure → database persistence


LIFECYCLE ENGINE (CORE ENGINE)
--------------------------------------------------

Location:

backend/engine/lifecycle_core/

This engine is responsible for evaluating obligations over time.

It contains no business logic about contracts.
It only processes obligations.

The lifecycle engine consists of:

primitives
state evaluation
escalation rules
event recording
scheduling


LIFECYCLE ENGINE STRUCTURE
--------------------------------------------------

backend/engine/lifecycle_core

obligations/
    primitives.py

scheduler/
    obligation_scheduler.py

state/
    evaluator.py
    escalation.py
    constants.py

events/
    event_recorder.py

lifecycle_manager.py


PRIMITIVES (CORE DOMAIN OBJECTS)
--------------------------------------------------

File:
lifecycle_core/obligations/primitives.py

Defines the two fundamental obligation types.

PaymentObligation

Attributes:
- obligor_id
- obligee_id
- amount_due
- amount_paid
- due_date
- state

Key methods:
apply_payment()
remaining_balance()
is_past_due()

Payment obligations transition to RESOLVED when fully paid.


ServiceObligation

Attributes:
- obligor_id
- obligee_id
- description
- due_date
- state
- completed_at

Key methods:
mark_completed()
is_past_due()

Service obligations transition to RESOLVED when the service is completed.


OBLIGATION SCHEDULER
--------------------------------------------------

File:
lifecycle_core/scheduler/obligation_scheduler.py

This module generates obligations from contract parameters.

Example:

generate_parallel_schedule()

Creates paired obligations:

Service obligation
Payment obligation

Example output:

Cycle 1
    ServiceObligation
    PaymentObligation

Cycle 2
    ServiceObligation
    PaymentObligation

Cycle 3
    ServiceObligation
    PaymentObligation

This models real service agreements where work is performed and payment follows.


STATE EVALUATION
--------------------------------------------------

File:
lifecycle_core/state/evaluator.py

This module determines the lifecycle state of obligations.

Possible states:

ACTIVE
OVERDUE
RESOLVED

Rules:

If fully paid → RESOLVED
If past due → OVERDUE
Otherwise → ACTIVE


DEFAULT ESCALATION
--------------------------------------------------

File:
lifecycle_core/state/escalation.py

Escalates long-running default conditions.

Example rule:

If an obligation remains defaulted longer than a threshold
→ escalate to BREACHED.


EVENT RECORDING
--------------------------------------------------

File:
lifecycle_core/events/event_recorder.py

Records lifecycle events.

Examples:

service_completed
service_issue
payment_received
note_added

Events create an audit trail of obligation activity.


LIFECYCLE PROCESSOR
--------------------------------------------------

File:
engine/contracts/obligations/lifecycle.py

This function processes lifecycle state transitions.

process_obligation_lifecycle()

Flow:

1) Evaluate lifecycle state
2) Persist state changes
3) Apply escalation rules

Pseudo flow:

evaluate_obligation_state()
    ↓
update state
    ↓
evaluate_default_escalation()


LIFECYCLE RUNNER
--------------------------------------------------

File:
engine/contracts/services/lifecycle_runner_services.py

This service runs lifecycle automation across obligations.

Example:

LifecycleRunnerService.run()

Process:

Fetch obligations
Loop through each
Call process_obligation_lifecycle()

This is typically triggered by:

scheduled jobs
background workers
Celery tasks


CONTRACT ENGINE
--------------------------------------------------

Location:

backend/engine/contracts/

The contract engine builds on the lifecycle engine.

Contracts contain obligations.
Contracts derive their state from obligation states.


CONTRACT DOMAIN MODEL
--------------------------------------------------

Domain contract object:

engine/contracts/domain/contract.py

Contracts contain:

contract_id
obligations
state

Contracts refresh their state based on obligations.

Rules:

If all obligations resolved → contract fulfilled
If some overdue → contract at risk
Otherwise → contract active


CONTRACT SERVICES
--------------------------------------------------

The contract engine contains several services.

contract_coordinator

Coordinates contract lifecycle updates.

contract_version_service

Manages contract revisions.

activation_service

Creates obligations when a contract becomes active.

lifecycle_runner_service

Runs lifecycle automation.

contract_projection_service

Builds a projection of contract state for UI or APIs.


PAYMENT ENGINE
--------------------------------------------------

Location:

backend/engine/payments/

This engine processes payments against obligations.

PaymentService

Handles payment processing.

MockPaymentGateway

Used for testing.


PAYMENT ALLOCATION
--------------------------------------------------

File:

engine/contracts/obligations/payments.py

apply_payment_to_obligations()

Algorithm:

Sort obligations by due date.
Apply payment to oldest obligation first.

Example:

Obligation A: $200
Obligation B: $150
Obligation C: $300

Payment: $500

Allocation:

A → $200
B → $150
C → $150


INFRASTRUCTURE LAYER
--------------------------------------------------

Location:

backend/infrastructure/repositories/

These classes persist engine objects to Django models.

Repositories:

ContractRepository
ContractVersionRepository
ContractObligationRepository

Responsibilities:

Create records
Fetch records
Update lifecycle state


DJANGO MODEL LAYER
--------------------------------------------------

Location:

backend/contracts/models.py

Defines database models.

Models include:

Contract
ContractVersion
Obligation
RequestChange
ContractObligation

ContractObligation represents the persisted obligation instance.


TEST SYSTEM
--------------------------------------------------

Multiple tests validate the engine.

Tests cover:

Contract lifecycle
Payment processing
Contract reconstruction
Full integration cycle


EXAMPLE TESTS
--------------------------------------------------

test_contract_lifecycle.py

Ensures a contract becomes fulfilled when all obligations resolve.

test_full_contract_cycle.py

Tests:

Contract creation
Version signing
Contract activation
Lifecycle automation
Projection

test_payment_service.py

Tests:

Partial payments
Full payments
Overpayments
Invalid payments


CURRENT SYSTEM CAPABILITIES
--------------------------------------------------

The system currently supports:

Recurring service/payment schedules
Lifecycle automation
Payment processing
Contract activation
Contract projection
Contract reconstruction
Lifecycle escalation
Integration tests


WHAT IS COMPLETE
--------------------------------------------------

Lifecycle primitives
Lifecycle state engine
Payment engine
Contract activation
Contract projection
Repository layer
Django models
Lifecycle runner
Integration tests


WHAT IS PARTIALLY COMPLETE
--------------------------------------------------

Service obligation lifecycle coverage
Event driven processing
State standardization
Lifecycle visualization


WHAT IS NOT COMPLETE YET
--------------------------------------------------

Service obligation event handling
Unified lifecycle state machine
Advanced breach logic
Event-driven architecture
Contract negotiation workflows
Dispute resolution flows


DESIGN PHILOSOPHY
--------------------------------------------------

The architecture follows several principles:

Separation of domain logic and persistence
Composable lifecycle primitives
Explicit lifecycle state transitions
Service-oriented contract processing

The lifecycle engine is intentionally generic so it can support:

contracts
subscriptions
service agreements
payment plans


CURRENT SYSTEM STATUS
--------------------------------------------------

The engine is operational.

Contracts can be created, activated, and processed.

Lifecycle automation works.

Payment processing works.

Integration tests validate the core system.


FUTURE DIRECTION
--------------------------------------------------

Next development stages include:

Service obligation lifecycle parity
Event-driven lifecycle engine
Contract negotiation workflows
Dispute resolution flows
Analytics and reporting

Long term this architecture supports building a full contract execution platform.


END OF DOCUMENT
--------------------------------------------------







