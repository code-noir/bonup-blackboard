# backend/engine/lifecycle_core/instances/obligation_instance.py

from datetime import datetime
from decimal import Decimal


class ObligationInstance:
    """
    A lifecycle instance of an obligation.

    This represents one occurrence of a payment
    or service obligation in time.
    """

    STATE_PENDING = "pending"
    STATE_ACTIVE = "active"
    STATE_COMPLETED = "completed"
    STATE_OVERDUE = "overdue"

    def __init__(
        self,
        obligation_type,
        obligor_id,
        obligee_id,
        due_date,
        amount_due=None,
        description=None,
        installment_number=None,
    ):

        self.obligation_type = obligation_type

        self.obligor_id = obligor_id
        self.obligee_id = obligee_id

        self.amount_due = Decimal(amount_due) if amount_due else None
        self.amount_paid = Decimal("0")

        self.description = description

        self.installment_number = installment_number

        self.due_date = due_date
        self.state = self.STATE_PENDING

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    # -------------------------
    # PAYMENT SUPPORT
    # -------------------------

    def apply_payment(self, amount):

        if self.amount_due is None:
            raise ValueError("This obligation is not a payment obligation")

        amount = Decimal(amount)

        if amount <= 0:
            raise ValueError("Payment must be positive")

        self.amount_paid += amount

        if self.amount_paid >= self.amount_due:
            self.state = self.STATE_COMPLETED

        self.updated_at = datetime.utcnow()

    # -------------------------
    # SERVICE SUPPORT
    # -------------------------

    def mark_completed(self):

        self.state = self.STATE_COMPLETED
        self.updated_at = datetime.utcnow()

    # -------------------------
    # LIFECYCLE
    # -------------------------

    def is_past_due(self, current_time):

        return current_time > self.due_date and self.state != self.STATE_COMPLETED
