Purpose
	•	Orchestrates contract refresh by loading contract + obligations, delegating lifecycle decisions to the contract aggregate, then persisting changes.

What exists (confirmed)
	•	Loads contract: contract_repo.get(contract_id)
	•	Loads obligations: obligation_repo.get_by_contract(contract_id)
	•	Attaches obligations to aggregate: contract.obligations = obligations
	•	Runs lifecycle evaluation via aggregate: contract.refresh(now)
	•	Persists obligation changes: loop obligation_repo.save(obligation)
	•	Persists contract changes: contract_repo.save(contract)
	•	Recurrence projection hook exists:
	•	If hasattr(contract, "interval_days") → RecurrenceService.maintain_projection(...)

Lifecycle enforcement status
	•	This file does not contain lifecycle rules.
	•	It depends on lifecycle enforcement inside:
	•	the Contract aggregate (contract.refresh())
	•	and any contract state machine logic used by the aggregate.

What’s missing / not present here (by design)
	•	No transition validation here (expected to live in domain/state machine)
	•	No guardrails like “only signed contracts refresh” (must be in domain or service layer)
	•	No task scheduler/automation runner (no celery/cron here)
	•	No transaction wrapper / atomic block (partial save risk if exception mid-loop)

Conclusion
	•	✅ Coordinator layer exists.
	•	✅ Lifecycle refresh plumbing exists.
	•	⚠️ Actual lifecycle rules/transition enforcement are not provable from this file alone — must confirm inside the Contract domain (backend/engine/contracts/domain/contract.py) and state machine module.