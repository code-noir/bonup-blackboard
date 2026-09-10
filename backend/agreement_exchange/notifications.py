from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from backend.notifications.models import Notification

User = get_user_model()

_TITLES = {
    "agreement_exchange": "Agreement Exchange update",
    "contract_updated": "Agreement Exchange update",
    "version_created": "Agreement Exchange update",
    "version_signed": "Agreement Exchange signed",
    "version_rejected": "Agreement Exchange rejected",
}


def _send_email(email, *, subject, message):
    result = {"email_sent": False, "email_attempted": False}
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")
    if not email or not from_email:
        result["email_unavailable"] = "Recipient email or DEFAULT_FROM_EMAIL is not configured."
        return result
    result["email_attempted"] = True
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[email],
            fail_silently=True,
        )
        result["email_sent"] = sent_count > 0
    except Exception as exc:
        result["error"] = "email_delivery_failed"
    return result


def _existing_unread_notification(user, notification_type, metadata):
    source_event = (metadata or {}).get("source_event")
    exchange_id = (metadata or {}).get("exchange_id")
    action_type = (metadata or {}).get("action_type")
    if not source_event or not exchange_id:
        return None
    queryset = Notification.objects.filter(
        user=user,
        notification_type=notification_type,
        is_read=False,
        metadata__source_event=source_event,
        metadata__exchange_id=exchange_id,
    )
    if action_type:
        queryset = queryset.filter(metadata__action_type=action_type)
    return queryset.order_by("-created_at").first()


def notify_exchange_recipient(*, user=None, email="", notification_type="agreement_exchange", title="", message="", contract=None, metadata=None):
    metadata = metadata or {}
    notification_type = notification_type or "agreement_exchange"
    title = title or _TITLES.get(notification_type, "bonUP notification")
    result = {"in_app_created": False, "email_sent": False, "email_attempted": False, "recipient_email": email or ""}

    recipient = user or find_user_by_email(email)
    if recipient is not None:
        recipient_email = getattr(recipient, "email", "") or email or ""
        result["recipient_email"] = recipient_email
        try:
            existing = _existing_unread_notification(recipient, notification_type, metadata)
            if existing is None:
                Notification.objects.create(
                    user=recipient,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    related_contract=contract,
                    metadata=metadata,
                )
                result["in_app_created"] = True
            else:
                result["in_app_created"] = True
                result["deduplicated"] = True
                result["notification_id"] = str(existing.id)
        except Exception as exc:
            result["in_app_error"] = "notification_failed"
        result.update(_send_email(recipient_email, subject=title, message=message))
        return result

    result.update(_send_email(email, subject=title, message=message))
    return result


def find_user_by_email(email):
    if not email:
        return None
    return User.objects.filter(email__iexact=email).first()
