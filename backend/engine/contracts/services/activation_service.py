from datetime import datetime
from decimal import Decimal

from backend.engine.contracts.obligations.scheduler import generate_obligation_schedule
from backend.engine.contracts.obligations.primitives import ObligationBlueprint
from backend.contracts.models import ContractObligation


class ActivationService:

    def __init__(
        self,
        contract_repo,
        version_repo,
        obligation_repo,
    ):
        self.contract_repo = contract_repo
        self.version_repo = version_repo
        self.obligation_repo = obligation_repo

    def activate_contract(self, contract_id):

        contract = self.contract_repo.get(contract_id)

        latest_version = self.version_repo.get_latest(contract)

        if not latest_version or latest_version.status != "signed":
            raise Exception("Contract must be signed before activation.")

        # ------------------------------------------------------------------
        # TEMPORARY: extract obligation data from snapshot
        # (Later this becomes structured JSON parsing)
        # ------------------------------------------------------------------

        snapshot_data = latest_version.content_snapshot

        amount = Decimal(snapshot_data.get("amount"))
        installments = snapshot_data.get("installments")
        interval_days = snapshot_data.get("interval_days")
        start_date = snapshot_data.get("start_date")

        blueprint = ObligationBlueprint(
            obligor_id=snapshot_data.get("obligor_id"),
            obligee_id=snapshot_data.get("obligee_id"),
            amount=amount,
            installments=installments,
            interval_days=interval_days,
            start_date=start_date,
        )

        instances = generate_obligation_schedule(blueprint)

        db_objects = []

        for index, instance in enumerate(instances, start=1):

            db_objects.append(
                ContractObligation(
                    contract=contract,
                    version=latest_version,
                    obligor_id=instance.obligor_id,
                    obligee_id=instance.obligee_id,
                    installment_number=index,
                    amount_due=instance.amount_due,
                    amount_paid=Decimal("0.00"),
                    due_date=instance.due_date,
                    state="active",
                )
            )

        self.obligation_repo.bulk_create(db_objects)

        return True

