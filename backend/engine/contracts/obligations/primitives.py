from datetime import datetime
from decimal import Decimal


class ObligationInstance:

    def __init__(
        self,
        obligor_id,
        obligee_id,
        amount_due,
        due_date,
    ):
        self.obligor_id = obligor_id
        self.obligee_id = obligee_id
        self.amount_due = Decimal(str(amount_due))
        self.amount_paid = Decimal("0.00")
        self.due_date = due_date
        self.state = "active"
        self.created_at = datetime.utcnow()

    # ------------------------------------------------------------
    # PAYMENT LOGIC
    # ------------------------------------------------------------

    def apply_payment(self, amount):
        """
        Applies a payment toward this obligation.
        Supports partial and full payments.
        """

        amount = Decimal(str(amount))

        if amount <= 0:
            raise ValueError("Payment must be greater than zero.")

        if self.state == "resolved":
            raise ValueError("Obligation already resolved.")

        self.amount_paid += amount

        # Prevent overpayment beyond amount_due
        if self.amount_paid > self.amount_due:
            self.amount_paid = self.amount_due

        # Auto-resolve if fully paid
        if self.amount_paid == self.amount_due:
            self.state = "resolved"

    # ------------------------------------------------------------
    # STATUS HELPERS
    # ------------------------------------------------------------

    def remaining_balance(self):
        return self.amount_due - self.amount_paid

    def is_fully_paid(self):
        return self.amount_paid >= self.amount_due
