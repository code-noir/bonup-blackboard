from datetime import datetime, timedelta
from decimal import Decimal


# ------------------------------------------------------------
# BASE OBLIGATION
# ------------------------------------------------------------

class BaseObligation:
    """
    Core bilateral obligation structure.
    Contains identity and lifecycle state only.
    """

    def __init__(
        self,
        obligor_id,
        obligee_id,
        due_date,
        grace_days=0,  # NEW
    ):
        self.obligor_id = obligor_id
        self.obligee_id = obligee_id
        self.due_date = due_date
        self.grace_days = grace_days  # NEW
        self.state = "active"
        self.created_at = datetime.utcnow()

        
       


# ------------------------------------------------------------
# PAYMENT OBLIGATION
# ------------------------------------------------------------

class PaymentObligation(BaseObligation):
    """
    Monetary obligation.
    Handles amount tracking and resolution logic.
    """

    
    def __init__(
        self,
        obligor_id,
        obligee_id,
        amount_due,
        due_date,
        grace_days=0,  # NEW
    ):
        super().__init__(obligor_id, obligee_id, due_date, grace_days)

        self.amount_due = Decimal(str(amount_due))
        self.amount_paid = Decimal("0.00")

    # ------------------------------------------------------------
    # PAYMENT LOGIC
    # ------------------------------------------------------------

    def apply_payment(self, amount):

        amount = Decimal(str(amount))

        if amount <= 0:
            raise ValueError("Payment must be greater than zero.")

        if self.state == "resolved":
            raise ValueError("Obligation already resolved.")

        self.amount_paid += amount

        # Prevent overpayment
        if self.amount_paid > self.amount_due:
            self.amount_paid = self.amount_due

        if self.amount_paid == self.amount_due:
            self.state = "resolved"

    # ------------------------------------------------------------
    # STATUS HELPERS
    # ------------------------------------------------------------

    def remaining_balance(self):
        return self.amount_due - self.amount_paid

    def is_fully_paid(self):
        return self.amount_paid >= self.amount_due


# ------------------------------------------------------------
# SERVICE OBLIGATION
# ------------------------------------------------------------

class ServiceObligation(BaseObligation):
    """
    Non-monetary obligation.
    Tracks performance completion only.
    """

    def __init__(
    self,
    obligor_id,
    obligee_id,
    description,
    due_date,
    grace_days=0,  # NEW
):
      super().__init__(obligor_id, obligee_id, due_date, grace_days)

    def mark_completed(self):
        self.state = "resolved"
        self.completed_at = datetime.utcnow()

