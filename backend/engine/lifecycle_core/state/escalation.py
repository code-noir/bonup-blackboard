# backend/engine/lifecycle_core/state/escalation.py

from datetime import datetime


def evaluate_default_escalation(obligation, max_default_days=60, current_time=None):
    """
    Escalates prolonged default into breach-level condition.

    Rules:
    - If not defaulted → return current state
    - If defaulted for longer than max_default_days → breached
    """

    if current_time is None:
        current_time = datetime.utcnow()

    if obligation.state != "defaulted":
        return obligation.state

    # Calculate how long it's been past deadline
    overdue_days = (current_time - obligation.deadline()).days

    if overdue_days >= max_default_days:
        return "breached"

    return "defaulted"

