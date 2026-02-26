# backend/engine/contracts/obligations/lifecycle.py

from backend.engine.lifecycle_core.state.evaluator import (
    evaluate_obligation_state,
)

from backend.engine.lifecycle_core.state.escalation import (
    evaluate_default_escalation,
)


# ==============================================================
# MASTER LIFECYCLE ENGINE
# ==============================================================


def process_obligation_lifecycle(instance, current_time):
    """
    Full lifecycle state mutation.

    Rules:
    - current_time MUST be provided.
    - No state regression allowed.
    - Escalation only applies to defaulted obligations.
    """

    if current_time is None:
        raise ValueError("current_time must be provided to lifecycle engine")

    # --- PROTECT TERMINAL STATES ---
    if instance.state in ("resolved", "breached"):
        return instance.state

    # --- STEP 1: BASE STATE ---
    base_state = evaluate_obligation_state(instance)

    # Prevent regression from defaulted/breached back to overdue
    if instance.state == "defaulted" and base_state == "overdue":
        base_state = "defaulted"

    instance.state = base_state

    # --- STEP 2: ESCALATION ---
    if instance.state == "defaulted":
        escalated_state = evaluate_default_escalation(
            instance,
            current_time=current_time,
        )

        # Escalation may upgrade to breached
        instance.state = escalated_state

    return instance.state






