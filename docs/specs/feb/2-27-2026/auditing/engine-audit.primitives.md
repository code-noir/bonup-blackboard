backend/engine/lifecycle_core/obligations/primitives.py

⸻

✅ What This File Actually Implements

This file defines:

1️⃣ BaseObligation (Engine-Level Lifecycle Unit)
	•	Tracks:
	•	obligor_id
	•	obligee_id
	•	due_date
	•	grace_days
	•	state (default = “active”)
	•	created_at
	•	Implements:
	•	deadline() → includes grace period
	•	is_past_due() → time-based state check

This is real lifecycle behavior.

Not database.
Not Django.
Pure engine logic.

⸻

2️⃣ PaymentObligation

Extends BaseObligation.

Implements:
	•	amount_due
	•	amount_paid
	•	apply_payment()
	•	auto-resolve when fully paid
	•	overpayment prevention
	•	remaining_balance()
	•	is_fully_paid()

This is real automation logic.

It automatically changes state to “resolved”.

That is lifecycle enforcement at the obligation level.

⸻

3️⃣ ServiceObligation

Extends BaseObligation.

Implements:
	•	mark_completed()
	•	auto-set resolved
	•	completion timestamp

Again — lifecycle enforcement at unit level.

⸻

🧠 What This Means Architecturally

You DO have lifecycle logic.

But at the obligation primitive level.

This file:
	•	Does NOT manage contract lifecycle
	•	Does NOT manage version lifecycle
	•	Does NOT orchestrate multiple obligations
	•	Does NOT connect to database
	•	Does NOT auto-generate installments
	•	Does NOT enforce contract state transitions

It is a behavioral building block.

It is the lowest-level lifecycle unit.

And it is solid.

⸻

⚠️ What Is Missing

Missing layers:
	•	No contract activation trigger
	•	No obligation generation orchestrator
	•	No lifecycle state machine
	•	No state transition enforcement
	•	No automatic overdue promotion
	•	No payment recording integration
	•	No event hooks

This is primitive logic only.

⸻

📄 SPEC ENTRY — Copy This

You can paste this into:

docs/specs/engine-audit.md






### backend/engine/lifecycle_core/obligations/primitives.py

Purpose:
Defines engine-level lifecycle primitives for obligation behavior.
Pure logic layer independent of Django models.

Implements:
- BaseObligation with deadline and past-due detection
- PaymentObligation with payment tracking and auto-resolution
- ServiceObligation with completion tracking
- Grace period handling
- Overpayment protection
- Auto state transition to "resolved"

Missing:
- No contract lifecycle integration
- No version lifecycle integration
- No obligation generation orchestration
- No automatic overdue state progression
- No event hooks to engine
- No database persistence wiring

Status:
Foundational behavioral primitives complete.
Higher-level orchestration and lifecycle enforcement missing.


