# backend/engine/contracts/services/activation_service.py

from datetime import datetime

from backend.infrastructure.repositories.contract_repository import ContractRepository
from backend.infrastructure.repositories.contract_version_repository import VersionRepository
from backend.infrastructure.repositories.contract_obligation_repository import ContractObligationRepository

from backend.engine.contracts.obligations.scheduler import generate_obligation_schedule
from backend.engine.contracts.obligations.primitives import ObligationBlueprint


class ActivationService:
    """
    Responsible for activating a signed contract.
    Generates obligation instances and persists them.
    """

    def __init__(
        self,
        contract_repository: ContractRepository,
        version_repository: VersionRepository,
        obligation_repository: ContractObligationRepository,
    ):
        self.contract_repository = contract_repository
        self.version_repository = version_repository
        self.obligation_repository = obligation_repository

    def activate_contract(self, contract_id: str):
        """
        Activates a contract AFTER lender confirms funds sent.
        """

        # 1️⃣ Fetch contract
        contract = self.contract_repository.get(contract_id)

        if not contract:
            raise Exception("Contract not found.")

        # 2️⃣ Fetch signed version
        version = self.version_repository.get_signed_version(contract)

        if not version:
            raise Exception("No signed version found.")

        # 3️⃣ Extract structured obligation data from snapshot
        snapshot = version.content_snapshot

        blueprint = ObligationBlueprint(
            obligor_id=snapshot["obligor_id"],
            obligee_id=snapshot["obligee_id"],
            amount=snapshot["amount"],
            start_date=snapshot["start_date"],
            installments=snapshot["installments"],
            interval_days=snapshot["interval_days"],
        )

        # 4️⃣ Generate obligation instances
        obligation_instances = generate_obligation_schedule(blueprint)

        # 5️⃣ Persist obligations
        for index, instance in enumerate(obligation_instances, start=1):
            self.obligation_repository.create(
                contract=contract,
                version=version,
                obligor_id=instance.obligor_id,
                obligee_id=instance.obligee_id,
                installment_number=index,
                amount_due=instance.amount_due,
                due_date=instance.due_date,
                state="active",
            )

        # 6️⃣ Mark contract active
        contract.is_active = True
        self.contract_repository.save(contract)

        return True


