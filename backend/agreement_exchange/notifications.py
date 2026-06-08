from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from backend.notifications.models import Notification

User = get_user_model()

_TITLES = {
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
        result["error"] = str(exc)
    return result


def notify_exchange_recipient(*, user=None, email="", notification_type="contract_updated", message="", contract=None, metadata=None):
    title = _TITLES.get(notification_type, "bonUP notification")
    result = {"in_app_created": False, "email_sent": False, "email_attempted": False, "recipient_email": email or ""}

    if user is not None:
        recipient_email = getattr(user, "email", "") or email or ""
        result["recipient_email"] = recipient_email
        try:
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                related_contract=contract,
                metadata=metadata or {},
            )
            result["in_app_created"] = True
        except Exception as exc:
            result["in_app_error"] = str(exc)
        result.update(_send_email(recipient_email, subject=title, message=message))
        return result

    result.update(_send_email(email, subject=title, message=message))
    return result


def find_user_by_email(email):
    if not email:
        return None
    return User.objects.filter(email__iexact=email).first()
