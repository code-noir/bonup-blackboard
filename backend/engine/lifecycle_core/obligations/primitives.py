
# backend/engine/lifecycle_core/obligations/primitives.py

from datetime import datetime, timedelta
from decimal import Decimal


# ------------------------------------------------------------
# BASE OBLIGATION
# ------------------------------------------------------------

class BaseObligation:
    """
    Represents a single lifecycle unit (one cycle / one installment).

    This class is engine-level.
    It knows nothing about contracts.
    """

    def __init__(
        self,
        obligor_id,
        obligee_id,
        due_date,
        grace_days=0,
    ):
        self.obligor_id = obligor_id
        self.obligee_id = obligee_id
        self.due_date = due_date
        self.grace_days = grace_days

        self.state = "active"
        self.created_at = datetime.utcnow()

    # ------------------------------------------------------------
    # LIFECYCLE HELPERS
    # ------------------------------------------------------------

    def deadline(self):
        """
        Returns the effective deadline including grace period.
        """
        if not self.grace_days:
            return self.due_date

        return self.due_date + timedelta(days=self.grace_days)

    def is_past_due(self, current_time=None):
        """
        Determines whether obligation has passed its deadline.
        """
        if current_time is None:
            current_time = datetime.utcnow()

        return current_time > self.deadline()


# ------------------------------------------------------------
# PAYMENT OBLIGATION
# ------------------------------------------------------------

class PaymentObligation(BaseObligation):
    """
    Monetary obligation.
    Handles amount tracking and payment application.
    """

    def __init__(
        self,
        obligor_id,
        obligee_id,
        amount_due,
        due_date,
        grace_days=0,
    ):
        super().__init__(obligor_id, obligee_id, due_date, grace_days)

        self.amount_due = Decimal(str(amount_due))
        self.amount_paid = Decimal("0.00")

    # ------------------------------------------------------------
    # PAYMENT LOGIC
    # ------------------------------------------------------------

    def apply_payment(self, amount):
        """
        Applies payment toward the obligation.
        """

        amount = Decimal(str(amount))

        if amount <= 0:
            raise ValueError("Payment must be greater than zero.")

        if self.state == "resolved":
            raise ValueError("Obligation already resolved.")

        self.amount_paid += amount

        # Prevent overpayment
        if self.amount_paid > self.amount_due:
            self.amount_paid = self.amount_due

        # Auto-resolve if fully paid
        if self.amount_paid >= self.amount_due:
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
    Performance-based obligation.
    Tracks completion instead of monetary payment.
    """

    def __init__(
        self,
        obligor_id,
        obligee_id,
        description,
        due_date,
        grace_days=0,
    ):
        super().__init__(obligor_id, obligee_id, due_date, grace_days)

        self.description = description
        self.completed_at = None

    def mark_completed(self):
        """
        Marks service as completed.
        """
        if self.state == "resolved":
            raise ValueError("Service already completed.")

        self.state = "resolved"
        self.completed_at = datetime.utcnow()

