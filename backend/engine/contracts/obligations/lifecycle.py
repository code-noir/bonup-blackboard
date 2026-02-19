from datetime import datetime
from .state import (
    evaluate_obligation_state,
    evaluate_default_escalation,
)


# ============================================================
# MASTER LIFECYCLE ENGINE
# ============================================================

def process_obligation_lifecycle(instance):
    """
    Full lifecycle state mutation.
    """

    # Step 1 — base state evaluation
    base_state = evaluate_obligation_state(instance)

    instance.state = base_state

    # Step 2 — escalate to default if needed
    escalated_state = evaluate_default_escalation(instance)

    instance.state = escalated_state

    return instance.state



