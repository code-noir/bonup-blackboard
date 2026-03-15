# backend/engine/lifecycle_core/obligations/primitives.py
from datetime import datetime
from decimal import Decimal


# ============================================================
# PAYMENT OBLIGATION
# ============================================================

class PaymentObligation:

    def __init__(
        self,
        obligee_id,
        obligor_id,
        amount_due,
        due_date,
        state="pending",
        amount_paid=0,
    ):
        self.obligee_id = obligee_id
        self.obligor_id = obligor_id

        self.amount_due = Decimal(amount_due)
        self.amount_paid = Decimal(amount_paid)

        self.due_date = due_date
        self.state = state

    # -------------------------
    # PAYMENT LOGIC
    # -------------------------

    def apply_payment(self, amount):

        amount = Decimal(amount)

        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        self.amount_paid += amount

        # CAP PAYMENT
        if self.amount_paid > self.amount_due:
            self.amount_paid = self.amount_due

        # RESOLVE IF FULLY PAID
        if self.amount_paid == self.amount_due:
            self.state = "resolved"

    def remaining_balance(self):
        return self.amount_due - self.amount_paid

    # -------------------------
    # LIFECYCLE SUPPORT
    # -------------------------

    def is_past_due(self, current_time: datetime):

        due = self.due_date

        if current_time.tzinfo and not due.tzinfo:
            due = due.replace(tzinfo=current_time.tzinfo)

        elif due.tzinfo and not current_time.tzinfo:
            current_time = current_time.replace(tzinfo=due.tzinfo)

        return current_time > due


# ============================================================
# SERVICE OBLIGATION
# ============================================================

class ServiceObligation:

    def __init__(
        self,
        obligor_id,
        obligee_id,
        description,
        due_date,
        state="pending",
    ):

        self.obligor_id = obligor_id
        self.obligee_id = obligee_id

        self.description = description

        self.due_date = due_date
        self.state = state

        self.completed_at = None

    # -------------------------
    # SERVICE EXECUTION
    # -------------------------

    def mark_completed(self, completion_time=None):

        if completion_time is None:
            completion_time = datetime.utcnow()

        self.completed_at = completion_time
        self.state = "resolved"

    # -------------------------
    # LIFECYCLE SUPPORT
    # -------------------------

    def is_past_due(self, current_time: datetime):

        due = self.due_date

        if current_time.tzinfo and not due.tzinfo:
            due = due.replace(tzinfo=current_time.tzinfo)

        elif due.tzinfo and not current_time.tzinfo:
            current_time = current_time.replace(tzinfo=due.tzinfo)

        return current_time > due and self.state != "resolved"
















