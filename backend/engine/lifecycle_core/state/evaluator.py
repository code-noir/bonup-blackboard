# backend/engine/lifecycle_core/state/evaluator.py
from django.utils import timezone

# State constants (adjust import if yours live elsewhere)
ACTIVE = "active"
OVERDUE = "overdue"
DEFAULTED = "defaulted"
RESOLVED = "resolved"

DEFAULT_THRESHOLD_DAYS = 30


def evaluate_obligation_state(obligation, current_time=None):
    """
    Determines lifecycle state of a single obligation.

    Rules:
    - If fully paid              -> resolved
    - If overdue >= 30 days      -> defaulted
    - If past due                -> overdue
    - Otherwise                  -> active
    """

    # Always use Django timezone-aware datetime
    if current_time is None:
        current_time = timezone.now()

    # 1️⃣ Fully paid
    # Prefer explicit method if present
    if hasattr(obligation, "is_fully_paid") and obligation.is_fully_paid():
        return RESOLVED

    # Fallback logic (optional safety)
    if hasattr(obligation, "amount_paid") and hasattr(obligation, "amount_due"):
        if obligation.amount_paid >= obligation.amount_due:
            return RESOLVED

    # 2️⃣ Past due — check how long
    if obligation.is_past_due(current_time):
        due_date = obligation.due_date

        # Normalise tzinfo so subtraction doesn't blow up on naive/aware mismatch
        if current_time.tzinfo and not due_date.tzinfo:
            due_date = due_date.replace(tzinfo=current_time.tzinfo)
        elif due_date.tzinfo and not current_time.tzinfo:
            current_time = current_time.replace(tzinfo=due_date.tzinfo)

        overdue_days = (current_time - due_date).days

        if overdue_days >= DEFAULT_THRESHOLD_DAYS:
            return DEFAULTED

        return OVERDUE

    # 3️⃣ Default state
    return ACTIVE




