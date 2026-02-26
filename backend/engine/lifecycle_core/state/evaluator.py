from datetime import datetime
from backend.engine.lifecycle_core.state.constants import (
    ACTIVE,
    OVERDUE,
    RESOLVED,
)


def evaluate_obligation_state(obligation, current_time=None):
    """
    Determines lifecycle state of a single obligation.

    Rules:
    - If fully paid -> resolved
    - If past deadline -> overdue
    - Otherwise -> active
    """

    if current_time is None:
        current_time = datetime.utcnow()

    # Derive from facts, not stored state
    if hasattr(obligation, "is_fully_paid") and obligation.is_fully_paid():
        return RESOLVED

    if obligation.is_past_due(current_time):
        return OVERDUE

    return ACTIVE



