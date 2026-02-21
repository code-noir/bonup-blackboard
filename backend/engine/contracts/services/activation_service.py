
# backend/engine/contracts/services/activation_service.py

from datetime import datetime

from backend.infrastructure.repositories.contract_repository import (
    ContractRepository,
)
from backend.infrastructure.repositories.contract_version_repository import (
    ContractVersionRepository,
)
from backend.infrastructure.repositories.contract_obligation_repository import (
    ContractObligationRepository,
)

from backend.engine.contracts.obligations.scheduler import (
    generate_obligation_schedule,
)




class ContractActivationService:
    """
    Handles full contract activation.
    Bridge between engine logic and persistence layer.
    """

    def __init__(
        self,
        contract_repo: ContractRepository,
        version_repo: ContractVersionRepository,
        obligation_repo: ContractObligationRepository,
    ):
        self.contract_repo = contract_repo
        self.version_repo = version_repo
        self.obligation_repo = obligation_repo

    def activate_contract(
        self,
        contract_id,
        obligor_id,
        obligee_id,
        amount,
        installments,
        interval_days,
        start_date=None,
    ):
        """
        Activates a signed contract.
        Generates obligation schedule.
        Persists obligations.
        """

        contract = self.contract_repo.get(contract_id)
        version = self.version_repo.get_latest(contract)

        if version.status != "signed":
            raise Exception("Only signed contracts can be activated.")

        if not start_date:
            start_date = datetime.utcnow()

      

        instances = generate_obligation_schedule(
            obligor_id=obligor_id,
            obligee_id=obligee_id,
            total_amount=amount,
            installments=installments,
            start_date=start_date,
            interval_days=interval_days,
        )



        # 3️⃣ Persist
        for index, instance in enumerate(instances, start=1):
            self.obligation_repo.create(
                contract=contract,
                version=version,
                obligor_id=instance.obligor_id,
                obligee_id=instance.obligee_id,
                installment_number=index,
                amount_due=instance.amount_due,
                due_date=instance.due_date,
                state=instance.state,
            )

        return instances

