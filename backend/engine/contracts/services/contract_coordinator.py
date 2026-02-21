# backend/engine/contracts/services/contract_coordinator.py

from datetime import datetime

from backend.engine.contracts.obligations.state import evaluate_obligation_state


class ContractCoordinator:
    """
    Coordinates obligations inside a contract.
    Does NOT mutate primitives directly.
    Only updates persisted contract obligations.
    """
    def __init__(self, obligation_repo, contract_repo):
        self.obligation_repo = obligation_repo
        self.contract_repo = contract_repo

    def refresh_contract_obligations(self, contract_id, now=None):

        if not now:
            now = datetime.utcnow()

        obligations = self.obligation_repo.get_by_contract(contract_id)

        # Refresh each obligation state
        for obligation in obligations:

            new_state = evaluate_obligation_state(
                obligation,
                current_time=now
            )

            if new_state != obligation.state:
                obligation.state = new_state
                self.obligation_repo.save(obligation)

        # Evaluate overall contract state AFTER updating obligations
        contract_state = self._evaluate_contract_state(obligations)
         
        contract = self.contract_repo.get(contract_id)

        if contract.state != contract_state:
            contract.state = contract_state
            self.contract_repo.save(contract)


        # NOTE:
        # We are not persisting contract_state yet.
        # That will be wired in next step.

        return obligations

    def _evaluate_contract_state(self, obligations):

        if not obligations:
            return "active"

        states = [o.state for o in obligations]

        if "defaulted" in states:
            return "breached"

        if all(state == "resolved" for state in states):
            return "fulfilled"

        return "active"



