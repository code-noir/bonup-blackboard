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

        if self.amount_paid > self.amount_due:
            self.amount_paid = self.amount_due

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

    def was_completed_late(self):
        """
        True if the service was completed after its due date.
        """

        if self.completed_at is None:
            return False

        completion_time = self.completed_at
        due = self.due_date

        if completion_time.tzinfo and not due.tzinfo:
            due = due.replace(tzinfo=completion_time.tzinfo)

        elif due.tzinfo and not completion_time.tzinfo:
            completion_time = completion_time.replace(tzinfo=due.tzinfo)

        return completion_time > due

    def calculate_lateness_adjustment(
        self,
        *,
        base_amount,
        adjustment_enabled,
        adjustment_mode=None,
        adjustment_value=None,
    ):
        """
        Calculate a one-time lateness adjustment for a completed service obligation.

        Rules:
        - applies only if enabled
        - applies only if the obligation was completed late
        - supports fixed_amount and percentage
        - never exceeds the base_amount
        """

        base_amount = Decimal(base_amount)

        if base_amount < 0:
            raise ValueError("base_amount cannot be negative")

        if not adjustment_enabled:
            return Decimal("0.00")

        if not self.was_completed_late():
            return Decimal("0.00")

        if adjustment_mode not in ["fixed_amount", "percentage"]:
            raise ValueError("Invalid lateness adjustment mode")

        if adjustment_value is None:
            raise ValueError("adjustment_value is required when lateness adjustment is enabled")

        adjustment_value = Decimal(adjustment_value)

        if adjustment_value < 0:
            raise ValueError("adjustment_value cannot be negative")

        if adjustment_mode == "fixed_amount":
            adjustment = adjustment_value
        else:
            adjustment = (base_amount * adjustment_value) / Decimal("100")

        if adjustment > base_amount:
            adjustment = base_amount

        return adjustment.quantize(Decimal("0.01"))

    def calculate_adjusted_service_amount(
        self,
        *,
        base_amount,
        adjustment_enabled,
        adjustment_mode=None,
        adjustment_value=None,
    ):
        """
        Returns the adjusted payable amount after lateness discount/penalty.
        """

        base_amount = Decimal(base_amount)
        adjustment = self.calculate_lateness_adjustment(
            base_amount=base_amount,
            adjustment_enabled=adjustment_enabled,
            adjustment_mode=adjustment_mode,
            adjustment_value=adjustment_value,
        )

        adjusted_amount = base_amount - adjustment

        if adjusted_amount < 0:
            adjusted_amount = Decimal("0.00")

        return adjusted_amount.quantize(Decimal("0.01"))






















