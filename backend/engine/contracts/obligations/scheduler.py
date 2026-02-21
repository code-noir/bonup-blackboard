from datetime import timedelta
from decimal import Decimal
from typing import List
from backend.engine.contracts.obligations.primitives import PaymentObligation


def generate_obligation_schedule(
    obligor_id,
    obligee_id,
    total_amount,
    installments,
    start_date,
    interval_days,
) -> List[PaymentObligation]:

    total_amount = Decimal(str(total_amount))
    installments = int(installments)

    base_amount = total_amount // installments
    remainder = total_amount - (base_amount * installments)

    instances = []

    for i in range(installments):

        # First installment gets remainder
        if i == 0:
            amount_due = base_amount + remainder
        else:
            amount_due = base_amount

        due_date = start_date + timedelta(days=i * interval_days)

        instance = PaymentObligation(
            obligor_id=obligor_id,
            obligee_id=obligee_id,
            amount_due=amount_due,
            due_date=due_date,
        )

        instances.append(instance)

    return instances

