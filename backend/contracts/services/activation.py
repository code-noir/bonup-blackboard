# backend/contracts/services/activation.py
#
# NOT ON THE LIVE API PATH — DO NOT BUILD ON THIS WITHOUT REVIEW.
#
# activate_contract_with_schedule() is not imported by any view, factory,
# or other live code. It is a dead schedule-based bulk-activation function
# that has never been wired to an API endpoint.
#
# The live activation path is:
#   backend/api/contracts/obligations_views.py (POST)
#   → backend/api/contracts/services/contract_lifecycle_service.py
#     ContractLifecycleService.create_obligation()
#
# This creates obligations individually per request (not via schedule).

from decimal import Decimal
from django.utils import timezone

from backend.engine.lifecycle_core.scheduler.obligation_scheduler import ObligationScheduler
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

    schedule = ObligationScheduler.generate_parallel_schedule(
        total_amount=Decimal(str(amount)),
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




