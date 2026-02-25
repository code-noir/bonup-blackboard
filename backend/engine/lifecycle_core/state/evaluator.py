# backend/engine/lifecycle_core/state/evaluator.py

from datetime import datetime


def evaluate_obligation_state(obligation, current_time=None):
    """
    Determines lifecycle state of a single obligation.

    Rules:
    - If resolved → remain resolved
    - If past deadline → overdue
    - Otherwise → active
    """

    if current_time is None:
        current_time = datetime.utcnow()

    if obligation.state == "resolved":
        return "resolved"

    if obligation.is_past_due(current_time):
        return "overdue"

    return "active"



