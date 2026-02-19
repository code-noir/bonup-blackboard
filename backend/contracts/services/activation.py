
from decimal import Decimal
from django.utils import timezone

from backend.engine.contracts.obligations.scheduler import generate_obligation_schedule
from backend.engine.contracts.obligations.primitives import ObligationInstance

from backend.contracts.models import ContractObligation


def activate_contract_with_schedule(
    *,
    contract,
    version,
    obligor,
    obligee,
    amount,
    installments,
    interval_days,
    ):
    """
    Bridge between Django and pure engine.

    Generates obligation schedule
    and persists each obligation.
    """

    schedule = generate_obligation_schedule(
        amount=Decimal(str(amount)),
        installments=installments,
        interval_days=interval_days,
        start_date=timezone.now(),
        obligor_id=obligor.id,
        obligee_id=obligee.id,
    )

    persisted = []

    for index, instance in enumerate(schedule, start=1):

        obj = ContractObligation.objects.create(
            contract=contract,
            version=version,
            obligor=obligor,
            obligee=obligee,
            installment_number=index,
            amount_due=instance.amount_due,
            due_date=instance.due_date,
            state="pending",
        )

        persisted.append(obj)




