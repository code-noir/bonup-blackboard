# backend/engine/contracts/services/contract_coordinator.py

from datetime import datetime

from backend.engine.contracts.services.recurrence_service import RecurrenceService
from backend.engine.contracts.obligations.lifecycle import process_obligation_lifecycle


class ContractCoordinator:
    """
    Orchestrates persistence and cross-service coordination.

    Enforcement rules:
    - Lifecycle state MUST be derived via lifecycle engine (process_obligation_lifecycle)
    - Contract state MUST be aggregated from obligation states (domain contract.refresh_state)
    - Coordinator persists the results
    """

    def __init__(self, obligation_repo, contract_repo):
        self.obligation_repo = obligation_repo
        self.contract_repo = contract_repo
        self.recurrence_service = RecurrenceService(obligation_repo)

    def refresh_contract_obligations(self, contract_id, now=None):
        if now is None:
            now = datetime.utcnow()

        # 1️⃣ Load contract and obligations
        contract = self.contract_repo.get(contract_id)
        obligations = self.obligation_repo.get_by_contract(contract_id)

        # 2️⃣ Attach obligations to domain aggregate
        contract.obligations = obligations

        # 3️⃣ Enforce lifecycle on each obligation (single source of truth)
        for obligation in contract.obligations:
          
            process_obligation_lifecycle(
            obligation,
            obligation_repo=self.obligation_repo,
            current_time=now,
        )

        # 4️⃣ Aggregate contract state from obligations (domain responsibility)
        if hasattr(contract, "refresh_state"):
            contract.refresh_state()
        else:
            raise Exception("Contract domain missing refresh_state(); cannot aggregate contract state.")

        # 5️⃣ Persist obligation state changes
        for obligation in contract.obligations:
            self.obligation_repo.save(obligation)

        # 6️⃣ Persist contract state change
        self.contract_repo.save(contract)

        # 7️⃣ Maintain recurrence projection (if supported)
        if hasattr(contract, "interval_days"):
            self.recurrence_service.maintain_projection(
                contract=contract,
                obligations=contract.obligations,
                interval_days=contract.interval_days,
                buffer_cycles=1,
            )

        return contract.obligations










