
# backend/engine/contracts/services/contract_coordinator.py

from datetime import datetime
from backend.engine.contracts.services.recurrence_service import RecurrenceService


class ContractCoordinator:
    """
    Orchestrates persistence and cross-service coordination.

    Does NOT contain lifecycle rules.
    Contract aggregate owns lifecycle truth.
    """

    def __init__(self, obligation_repo, contract_repo):
        self.obligation_repo = obligation_repo
        self.contract_repo = contract_repo
        self.recurrence_service = RecurrenceService(obligation_repo)

    def refresh_contract_obligations(self, contract_id, now=None):

        if not now:
            now = datetime.utcnow()

        # 1️⃣ Load contract and obligations
        contract = self.contract_repo.get(contract_id)
        obligations = self.obligation_repo.get_by_contract(contract_id)

        # 2️⃣ Attach obligations to domain aggregate
        contract.obligations = obligations

        # 3️⃣ Let contract decide lifecycle
        contract.refresh(now)

        # 4️⃣ Persist obligation state changes
        for obligation in contract.obligations:
            self.obligation_repo.save(obligation)

        # 5️⃣ Persist contract state change
        self.contract_repo.save(contract)

        # 6️⃣ Maintain recurrence projection (if supported)
        if hasattr(contract, "interval_days"):
            self.recurrence_service.maintain_projection(
                contract=contract,
                obligations=contract.obligations,
                interval_days=contract.interval_days,
                buffer_cycles=1,
            )

        return contract.obligations









