# backend/engine/contracts/services/contract_coordinator.py
from django.utils import timezone
from backend.engine.contracts.obligations.lifecycle import process_obligation_lifecycle


class ContractCoordinator:
    """
    Application service responsible for coordinating
    contract lifecycle operations across obligations.
    """

    def __init__(self, obligation_repo, contract_repo):
        self.obligation_repo = obligation_repo
        self.contract_repo = contract_repo

    def refresh_contract_obligations(self, contract_id, now=None):

        if now is None:
            now = timezone.now()

        # load contract
        contract = self.contract_repo.get(contract_id)

        # load obligations
        obligations = self.obligation_repo.get_by_contract(contract_id)

        # attach obligations to contract
        contract.obligations = obligations

        for obligation in obligations:

            # Skip lifecycle if obligation already resolved
            if  getattr(obligation, "state", None) == "resolved":
                continue

            process_obligation_lifecycle(
                obligation,
                obligation_repo=self.obligation_repo,
                current_time=now,
            )



        # refresh contract aggregate state
        if hasattr(contract, "refresh"):
            contract.refresh(now)

        # persist contract
        self.contract_repo.save(contract)















