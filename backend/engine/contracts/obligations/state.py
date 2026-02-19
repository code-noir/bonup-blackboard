from datetime import datetime, timedelta


# ============================================================
# OBLIGATION STATES (ENGINE LEVEL)
# ============================================================

class ObligationState:
    ACTIVE= "active"        # Not yet due
    DUE = "due"              # Due today
    GRACE = "grace"          # Inside grace window
    OVERDUE = "overdue"      # After grace window
    DEFAULTED = "defaulted"  # Exceeded max overdue days
    RESOLVED = "resolved"    # Fully paid


# ============================================================
# BASIC STATE EVALUATION
# ============================================================

def evaluate_obligation_state(
    instance,
    grace_period_days: int = 3,
    current_time: datetime = None,
):
    """
    Pure evaluation.
    Returns state WITHOUT mutating instance.
    """

    if current_time is None:
        current_time = datetime.utcnow()

    if instance.state == ObligationState.RESOLVED:
        return ObligationState.RESOLVED

    today = current_time.date()
    due_date = instance.due_date.date()

    # Before due
    if today < due_date:
        return ObligationState.ACTIVE

    # Due today
    if today == due_date:
        return ObligationState.DUE

    # Grace period
    grace_deadline = due_date + timedelta(days=grace_period_days)

    if today <= grace_deadline:
        return ObligationState.GRACE

    # After grace
    return ObligationState.OVERDUE


# ============================================================
# DEFAULT ESCALATION LOGIC
# ============================================================

def evaluate_default_escalation(
    instance,
    max_default_days: int = 60,
    current_time: datetime = None,
):
    """
    Escalates overdue obligations into default.
    """

    if current_time is None:
        current_time = datetime.utcnow()

    if instance.state != ObligationState.OVERDUE:
        return instance.state

    overdue_days = (current_time.date() - instance.due_date.date()).days

    if overdue_days >= max_default_days:
        return ObligationState.DEFAULTED

    return ObligationState.OVERDUE


















