# backend/engine/contracts/services/contract_service.py

from backend.engine.contracts.exceptions import (
    NegotiationLimitReached,
)

from backend.engine.contracts.domain.contract import Contract
from backend.engine.lifecycle_core.scheduler.scheduler import (
    generate_obligation_schedule,
)


class ContractService:
    """
    Handles:
    - Contract version lifecycle logic
    - Contract aggregate creation
    """

    def __init__(self, contract_repo=None, version_repo=None):
        self.contract_repo = contract_repo
        self.version_repo = version_repo

    # ------------------------------------------------------------
    # VERSIONING LOGIC
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # CONTRACT CREATION (ENGINE LEVEL)
    # ------------------------------------------------------------

    def create_contract(
        self,
        name,
        start_date,
        recurrence,
        cycles,
        payment_amount,
        payment_grace=0,
        service_grace=0,
    ):
        """
        Creates a Contract aggregate and generates
        parallel Payment and Service obligations.
        """

        # Create empty aggregate
        contract = Contract(
            contract_id=None,
            obligations=[]
        )

        # Compute total amount for scheduler
        total_amount = payment_amount * cycles

        # Generate obligations from lifecycle scheduler
        obligations = generate_obligation_schedule(
            obligor_id=1,
            obligee_id=2,
            total_amount=total_amount,
            installments=cycles,
            start_date=start_date,
            interval_days=self._resolve_interval(recurrence),
            payment_grace=payment_grace,
            service_grace=service_grace,
        )

        # Attach obligations to aggregate
        contract.obligations.extend(obligations)

        return contract

    # ------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------

    def _resolve_interval(self, recurrence):
        if recurrence == "monthly":
            return 30
        if recurrence == "weekly":
            return 7
        if recurrence == "daily":
            return 1

        raise ValueError("Unsupported recurrence type.")


