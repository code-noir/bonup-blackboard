# backend/activity/log.py
#
# Thin write-through helper.  Import and call log_activity() from any view
# mutation point to append a record to ContractActivity and notify the
# other contract party.
#
# Deliberately NOT wrapped in transaction.atomic() here — callers that want
# atomic consistency should wrap their own mutation + this call together.

from backend.activity.models import ContractActivity


_BACKGROUND_NOTIFICATION_TYPES = {
    "draft_autosaved",
}


def _metadata_marks_background_save(metadata):
    metadata = metadata or {}
    source = str(metadata.get("source") or metadata.get("source_event") or "").lower()
    return source in {"editor_autosave", "draft_autosave", "autosave", "draft_autosaved"}


def _should_create_visible_notification(activity_type, metadata):
    if activity_type in _BACKGROUND_NOTIFICATION_TYPES:
        return False
    return not _metadata_marks_background_save(metadata)


def _get_other_party(contract, actor_user):
    """
    Return the User who is the OTHER party on the contract (i.e. not the actor).
    Returns None if the other party is unregistered or if actor_user is None.
    """
    if actor_user is None:
        return None

    from django.contrib.auth import get_user_model
    User = get_user_model()

    if contract.initiator_id == actor_user.pk:
        # Actor is the initiator — notify counterparty if they have an account.
        try:
            return User.objects.get(email=contract.counterparty_email)
        except User.DoesNotExist:
            return None
    else:
        # Actor is the counterparty — notify initiator.
        return contract.initiator


def log_activity(contract, user, activity_type, description, metadata=None):
    """
    Append a ContractActivity record and notify the other contract party.

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

    # Notify the other party.  Wrapped in try/except so a broken mail backend
    # or missing notification type never bubbles up and corrupts the caller's
    # transaction.
    if not _should_create_visible_notification(activity_type, metadata):
        return

    try:
        recipient = _get_other_party(contract, user)
        if recipient is not None:
            from backend.notifications.notify import notify
            notify(
                user=recipient,
                notification_type=activity_type,
                message=description,
                related_contract=contract,
                metadata=metadata,
            )
    except Exception:
        pass
