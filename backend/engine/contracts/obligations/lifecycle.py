from django.db import transaction

from backend.engine.lifecycle_core.state.evaluator import (
    evaluate_obligation_state,
)

from backend.engine.lifecycle_core.state.escalation import (
    evaluate_default_escalation,
)


@transaction.atomic
def process_obligation_lifecycle(
    instance,
    obligation_repo,
    current_time=None,
):
    """
    Processes lifecycle state transitions and persists changes.
    """

    original_state = instance.state

    # 1️⃣ Evaluate base lifecycle state
    new_state = evaluate_obligation_state(
        instance,
        current_time=current_time,
    )

    # 2️⃣ Persist base state change
    if new_state != original_state:
        instance.state = new_state
        obligation_repo.save(instance)

    # 3️⃣ Optional escalation (only for defaulted)
    if instance.state == "defaulted":
        escalated_state = evaluate_default_escalation(
            instance,
            current_time=current_time,
        )

        if escalated_state != instance.state:
            instance.state = escalated_state
            obligation_repo.save(instance)

    return instance.state















