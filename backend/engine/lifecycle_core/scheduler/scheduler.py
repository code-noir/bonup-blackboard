# backend/engine/lifecycle_core/scheduler/scheduler.py
from datetime import timedelta
from decimal import Decimal

from backend.engine.lifecycle_core.obligations.primitives import (
    PaymentObligation,
    ServiceObligation,
)


def generate_obligation_schedule(
    obligor_id,
    obligee_id,
    total_amount,
    installments,
    start_date,
    interval_days,
    payment_grace=0,
    service_grace=0,
):
    """
    Generates parallel Payment and Service obligations
    per installment cycle.
    """

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

        # ------------------------------
        # Payment Obligation
        # ------------------------------
        payment_ob = PaymentObligation(
            obligor_id=obligor_id,
            obligee_id=obligee_id,
            amount_due=amount_due,
            due_date=due_date,
            grace_days=payment_grace,
        )

        instances.append(payment_ob)

        # ------------------------------
        # Service Obligation
        # ------------------------------
        service_ob = ServiceObligation(
            obligor_id=obligor_id,
            obligee_id=obligee_id,
            description=f"Service cycle {i + 1}",
            due_date=due_date,
            grace_days=service_grace,
        )

        instances.append(service_ob)

    return instances


