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

If you want next, I can generate:
	•	A “Critical Attack Review” version of this document
	•	A Risk Analysis document
	•	Or A Formal Technical RFC version

But the above is one clean, copy-paste-ready document.