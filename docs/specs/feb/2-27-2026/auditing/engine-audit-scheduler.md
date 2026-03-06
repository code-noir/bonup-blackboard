
File: scheduler.py (you pasted it)

✅ Generates obligation instances (engine primitives)
	•	Creates PaymentObligation objects with:
	•	amount_due split across installments
	•	first installment gets the remainder (so totals match)
	•	due_date based on start_date + i * interval_days
	•	grace_days via payment_grace
	•	Creates ServiceObligation objects with:
	•	description = "Service cycle {i+1}"
	•	same due_date
	•	grace_days via service_grace
	•	Returns a flat list alternating: payment, service, payment, service…

✅ Correct rounding behavior for money split
	•	Uses Decimal
	•	Uses integer division (//) so it avoids float issues
	•	Applies remainder once (first installment), which keeps total exact.

What it does NOT do (❌ missing / not present)

This is the important part for your “lifecycle enforcement / automation / management” concerns:

❌ Not a real scheduler / automation runner
	•	No cron, Celery, APScheduler, Django-Q, background workers, no periodic task.
	•	Nothing updates obligations over time (no “check if overdue and flip state” loop).

❌ No persistence layer
	•	It returns objects in memory only.
	•	It does not create ContractObligation rows.
	•	It does not connect to Django models at all.

❌ No lifecycle transition enforcement
	•	No rules like “only active → due → overdue → defaulted…”
	•	No “current_time” checks used here.
	•	No “contract state machine” logic.
	•	No permission logic (who can mark resolved / who can apply payment).

❌ No contract-level management
	•	Doesn’t tie schedule to Contract, ContractVersion, or negotiation status.
	•	Doesn’t know what “signed” means, doesn’t block generation before contract is signed, etc.

What this file indicates about the engine (signal)

✅ You do have a starting point for obligation generation logic (installment schedule + parallel service/payment cycles).
❌ You do not yet have “contract lifecycle enforcement” or “automation” just from this.

This file belongs in the engine as a pure generator utility.

⸻

Spec entry you can paste into your docs (single block, no breaks)

scheduler.py (engine lifecycle_core) provides obligation schedule generation as a pure utility: generate_obligation_schedule() creates an in-memory list of PaymentObligation and ServiceObligation instances for each installment cycle. It splits total_amount into equal Decimal installments using integer division and assigns any remainder to the first installment to preserve exact totals. It assigns due dates by start_date + (i * interval_days) and passes grace_days into each obligation type via payment_grace and service_grace. This module does not persist obligations to the database, does not integrate with Contract/ContractVersion models, does not enforce lifecycle state transitions, and does not implement automation/background scheduling (no periodic jobs or overdue/default evaluation loop). It is a generator utility only; orchestration, persistence into ContractObligation, and lifecycle enforcement must exist elsewhere.

⸻

If you want the next file to audit that actually answers your “do we already have lifecycle enforcement / transitions?” question, send one of these (whichever exists in your tree):
	•	backend/engine/lifecycle_core/__init__.py
	•	anything inside backend/engine/lifecycle_core/contracts/
	•	anything named like state_machine.py, transitions.py, enforcement.py, activation.py
	•	anything inside backend/engine/contracts/ (you showed that folder exists)