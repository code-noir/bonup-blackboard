# backend/engine/contracts/services/contract_service.py

from backend.engine.contracts.exceptions import (
    NegotiationLimitReached,
)


class ContractService:
    """
    Handles contract version lifecycle logic.
    Pure engine orchestration.
    """

    def __init__(self, contract_repo, version_repo):
        self.contract_repo = contract_repo
        self.version_repo = version_repo

    def create_initial_version(self, contract_id, content, user=None):

        contract = self.contract_repo.get(contract_id)

        existing_count = self.version_repo.count(contract)
        if existing_count > 0:
            raise Exception("Initial version already exists.")

        return self.version_repo.create(
            contract=contract,
            version_number=1,
            content_snapshot=content,
            created_by=user,
            status="draft"
        )

    def create_new_version(self, contract_id, content, user=None):

        contract = self.contract_repo.get(contract_id)

        current_count = self.version_repo.count(contract)

        if current_count >= contract.max_versions:
            raise NegotiationLimitReached("Negotiation limit reached.")

        latest = self.version_repo.get_latest(contract)

        next_number = 1 if not latest else latest.version_number + 1

        return self.version_repo.create(
            contract=contract,
            version_number=next_number,
            content_snapshot=content,
            created_by=user,
            previous_version=latest,
            status="draft"
        )

