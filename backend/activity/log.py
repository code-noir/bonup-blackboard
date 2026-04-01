# backend/activity/log.py
#
# Thin write-through helper.  Import and call log_activity() from any view
# mutation point to append a record to ContractActivity.
#
# Deliberately NOT wrapped in transaction.atomic() here — callers that want
# atomic consistency should wrap their own mutation + this call together.

from backend.activity.models import ContractActivity


def log_activity(contract, user, activity_type, description, metadata=None):
    """
    Append a ContractActivity record.

    Args:
        contract:       Contract instance the event belongs to.
        user:           The User who triggered the action (may be None for
                        automated events).
        activity_type:  One of ContractActivity.ACTIVITY_TYPE_CHOICES keys.
        description:    Human-readable summary of what happened.
        metadata:       Optional dict of supplementary data.
    """
    ContractActivity.objects.create(
        contract=contract,
        user=user,
        activity_type=activity_type,
        description=description,
        metadata=metadata or {},
    )
