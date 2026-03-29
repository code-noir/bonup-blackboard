# backend/engine/lifecycle_core/state/escalation.py


from datetime import datetime


def evaluate_default_escalation(
    obligation,
    max_default_days=60,
    current_time=None,
):
    """
    Escalates prolonged default into breach-level condition.

    Rules:
    - Only applies to defaulted obligations
    - If defaulted longer than max_default_days → breached
    """

    if current_time is None:
        raise ValueError("current_time must be provided for escalation")

    if obligation.state != "defaulted":
        return obligation.state

    if obligation.due_date is None:
        return obligation.state

    overdue_days = (current_time - obligation.due_date).days

    if overdue_days >= max_default_days:
        return "breached"

    return "defaulted"

