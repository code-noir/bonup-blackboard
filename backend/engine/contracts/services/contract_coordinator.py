from datetime import datetime

from backend.engine.contracts.domain.contract import Contract


class ContractCoordinator:
    """
    Coordinates contract lifecycle using the Contract aggregate.
    Orchestrates persistence only.
    """

    def __init__(self, obligation_repo, contract_repo):
        self.obligation_repo = obligation_repo
        self.contract_repo = contract_repo

    def refresh_contract_obligations(self, contract_id, now=None):

        if not now:
            now = datetime.utcnow()

        # Load persisted data
        obligations = self.obligation_repo.get_by_contract(contract_id)
        contract_record = self.contract_repo.get(contract_id)

        # Instantiate aggregate
        contract = Contract(
            contract_id=contract_id,
            obligations=obligations
        )

        # Refresh lifecycle via aggregate
        contract.refresh(now)

        # Persist obligation state changes
        for obligation in contract.obligations:
            self.obligation_repo.save(obligation)

        # Persist contract state change
        if contract_record.state != contract.state:
            contract_record.state = contract.state
            self.contract_repo.save(contract_record)

        return contract.obligations





