from django.utils import timezone

from backend.contracts.models import LifecycleItemUserState
from backend.notifications.models import Notification


def _iso(value):
    return value.isoformat() if value else None


def _item_due_date(item):
    due_date = getattr(item, "due_date", None)
    return due_date.isoformat() if due_date else None


def _notification_message(state):
    item = state.lifecycle_item
    agreement = item.lifecycle_agreement
    contract_title = agreement.contract.title or "Untitled contract"
    parts = [
        f"Reminder for: {item.title}",
        f"Agreement: {contract_title}",
    ]
    if item.due_date:
        parts.append(f"Due date: {item.due_date.isoformat()}")
    if state.reminder_at:
        parts.append(f"Reminder time: {state.reminder_at.isoformat()}")
    return "\n".join(parts)


def _notification_metadata(state, reminder_key):
    item = state.lifecycle_item
    agreement = item.lifecycle_agreement
    contract = agreement.contract
    return {
        "source": "agreement_performance_reminder",
        "lifecycle_item_id": str(item.id),
        "lifecycle_agreement_id": str(agreement.id),
        "contract_id": str(contract.id),
        "reminder_at": reminder_key,
        "due_date": _item_due_date(item),
        "redirect_url": "/agreement-performance",
        "target_url": "/agreement-performance",
    }


def due_reminder_states(now=None):
    now = now or timezone.now()
    return (
        LifecycleItemUserState.objects
        .filter(reminder_at__isnull=False, reminder_at__lte=now)
        .select_related(
            "user",
            "lifecycle_item",
            "lifecycle_item__lifecycle_agreement",
            "lifecycle_item__lifecycle_agreement__contract",
        )
        .order_by("reminder_at", "created_at")
    )


def send_due_timeline_reminders(now=None):
    sent = []
    for state in due_reminder_states(now=now):
        reminder_key = _iso(state.reminder_at)
        metadata = dict(state.metadata or {})
        reminder_delivery = dict(metadata.get("reminder_delivery") or {})
        if reminder_delivery.get("sent_for") == reminder_key:
            continue

        item = state.lifecycle_item
        notification = Notification.objects.create(
            user=state.user,
            notification_type="agreement_timeline",
            title=f"Reminder: {item.title}",
            message=_notification_message(state),
            related_contract=item.lifecycle_agreement.contract,
            metadata=_notification_metadata(state, reminder_key),
        )

        reminder_delivery.update({
            "sent_for": reminder_key,
            "sent_at": timezone.now().isoformat(),
            "notification_id": str(notification.id),
        })
        metadata["reminder_delivery"] = reminder_delivery
        state.metadata = metadata
        state.save(update_fields=["metadata", "updated_at"])
        sent.append(notification)
    return sent
