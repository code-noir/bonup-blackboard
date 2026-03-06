from django.utils import timezone

# State constants (adjust import if yours live elsewhere)
ACTIVE = "active"
OVERDUE = "overdue"
RESOLVED = "resolved"


def evaluate_obligation_state(obligation, current_time=None):
    """
    Determines lifecycle state of a single obligation.

    Rules:
    - If fully paid  -> resolved
    - If past deadline -> overdue
    - Otherwise -> active
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

    # 2️⃣ Past due
    if obligation.is_past_due(current_time):
        return OVERDUE

    # 3️⃣ Default state
    return ACTIVE




