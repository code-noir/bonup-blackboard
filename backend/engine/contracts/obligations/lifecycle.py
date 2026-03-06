# backend/engine/contracts/obligations/lifecycle.py


from django.db import transaction
from django.utils import timezone

from backend.engine.lifecycle_core.state.evaluator import evaluate_obligation_state
from backend.engine.lifecycle_core.state.escalation import evaluate_default_escalation


@transaction.atomic
def process_obligation_lifecycle(instance, obligation_repo=None, current_time=None):
    """
    Processes lifecycle state transitions and (optionally) persists changes.

    Defensive behavior:
    - If current_time is None => uses timezone.now()
    - If obligation_repo is None => does NOT attempt to persist
    """

    if current_time is None:
        current_time = timezone.now()

    original_state = getattr(instance, "state", None)

    # 1) Evaluate base lifecycle state
    new_state = evaluate_obligation_state(instance, current_time=current_time)

    # 2) Persist base state change (optional)
    if new_state != original_state:
        instance.state = new_state
        if obligation_repo is not None:
            obligation_repo.save(instance)

    # 3) Optional escalation (only when defaulted)
    if getattr(instance, "state", None) == "defaulted":
        escalated_state = evaluate_default_escalation(instance, current_time=current_time)
        if escalated_state != instance.state:
            instance.state = escalated_state
            if obligation_repo is not None:
                obligation_repo.save(instance)

    return instance.state




















