# backend/engine/contracts/services/contract_coordinator.py

from datetime import datetime

from backend.engine.contracts.obligations.state import evaluate_obligation_state


class ContractCoordinator:
    """
    Coordinates obligations inside a contract.
    Does NOT mutate primitives directly.
    Only updates persisted contract obligations.
    """

    def __init__(self, obligation_repo):
        self.obligation_repo = obligation_repo

    def refresh_contract_obligations(self, contract_id, now=None):

        if not now:
            now = datetime.utcnow()

        obligations = self.obligation_repo.get_by_contract(contract_id)

        for obligation in obligations:

            new_state = evaluate_obligation_state(
                obligation,
                current_time=now
            )

            if new_state != obligation.state:
                obligation.state = new_state
                self.obligation_repo.save(obligation)

        return obligations

