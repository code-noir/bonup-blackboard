# backend/api/contracts/services/contract_lifecycle_service.py
from backend.contracts.models import Contract
from backend.engine.lifecycle_core.obligations.primitives import (
    PaymentObligation,
    ServiceObligation,
)
from backend.infrastructure.repositories.contract_obligation_repository import (
    ContractObligationRepository,
)
from backend.infrastructure.repositories.contract_version_repository import (
    ContractVersionRepository,
)


class ContractLifecycleService:
    """
    Contract ↔ Engine orchestration layer

    Contract:
        - owns DB
    Engine:
        - owns logic
    This layer:
        - builds engine objects
        - persists results
    """

    def __init__(self):
        self.obligation_repo = ContractObligationRepository()
        self.version_repo = ContractVersionRepository()

    def create_obligation(self, contract_id, input_data):

        # -----------------------------
        # 1. LOAD CONTRACT
        # -----------------------------
        contract = Contract.objects.get(id=contract_id)

        # -----------------------------
        # 2. LOAD LATEST CONTRACT VERSION
        # -----------------------------
        version = self.version_repo.get_latest(contract)

        if not version:
            raise Exception("Cannot create obligation: no contract version exists")

        obligor_id = input_data.get("obligor_id")
        obligee_id = input_data.get("obligee_id")
        amount_due = input_data.get("amount_due")
        due_date = input_data.get("due_date")
        obligation_type = input_data.get("type")

        # -----------------------------
        # 3. BUILD ENGINE OBJECT
        # -----------------------------
        if obligation_type == "payment":

            if not amount_due:
                raise Exception("amount_due is required")

            obligation = PaymentObligation(
                obligor_id=obligor_id,
                obligee_id=obligee_id,
                amount_due=amount_due,
                due_date=due_date
            )

        elif obligation_type == "service":

            description = input_data.get("description")

            if not description:
                raise Exception("description is required")

            obligation = ServiceObligation(
                obligor_id=obligor_id,
                obligee_id=obligee_id,
                description=description,
                due_date=due_date
            )

        else:
            raise Exception("Invalid obligation type")

        # -----------------------------
        # 4. SAVE TO DATABASE
        # -----------------------------
        self.obligation_repo.create_from_engine_obligation(
            contract_id=contract.id,
            version=version,
            obligation=obligation,
            obligation_type=obligation_type,
        )

        return obligation



