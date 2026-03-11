# backend/engine/lifecycle_core/scheduler/obligation_scheduler.py

from datetime import timedelta
from decimal import Decimal

from backend.engine.lifecycle_core.obligations.primitives import (
    PaymentObligation,
    ServiceObligation,
)


class ObligationScheduler:

    """
    Generates lifecycle obligations from a contract structure.
    """

    @staticmethod
    def generate_parallel_schedule(
        obligor_id,
        obligee_id,
        total_amount,
        installments,
        start_date,
        interval_days,
        service_description="Service cycle",
    ):
        """
        Generates matching service and payment obligations.
        """

        total_amount = Decimal(str(total_amount))
        installments = int(installments)

        base_amount = total_amount // installments
        remainder = total_amount - (base_amount * installments)

        obligations = []

        for i in range(installments):

            if i == 0:
                amount_due = base_amount + remainder
            else:
                amount_due = base_amount

            due_date = start_date + timedelta(days=i * interval_days)

            # -------------------------
            # SERVICE OBLIGATION
            # -------------------------

            service_ob = ServiceObligation(
                obligor_id=obligor_id,
                obligee_id=obligee_id,
                description=f"{service_description} {i + 1}",
                due_date=due_date,
            )

            obligations.append(service_ob)

            # -------------------------
            # PAYMENT OBLIGATION
            # -------------------------

            payment_ob = PaymentObligation(
                obligor_id=obligor_id,
                obligee_id=obligee_id,
                amount_due=amount_due,
                due_date=due_date,
            )

            obligations.append(payment_ob)

        return obligations


