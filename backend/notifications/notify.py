# backend/notifications/notify.py
#
# notify() creates an in-app Notification record and sends an email
# synchronously via Django's send_mail.
#
# fail_silently=True on the email call means a broken mail backend will
# never roll back an enclosing database transaction.

from django.conf import settings
from django.core.mail import send_mail

from backend.notifications.models import Notification


# Human-readable titles keyed by activity/notification type.
_TITLES = {
    "contract_created": "New contract created",
    "contract_updated": "Contract updated",
    "version_created": "New contract version proposed",
    "version_signed": "Contract version signed",
    "version_rejected": "Contract version rejected",
    "role_switch_requested": "Role switch requested",
    "role_switch_confirmed": "Role switch confirmed",
    "obligation_resolved": "Obligation resolved",
    "payment_obligation_resolved": "Payment obligation resolved",
    "payment_created": "New payment recorded",
    "payment_confirmed": "Payment confirmed",
    "payment_failed": "Payment failed",
    "payment_cancelled": "Payment cancelled",
    "payment_refunded": "Payment refunded",
    "payment_reversed": "Payment reversed",
    "approval_requested": "Approval requested",
    "approval_granted": "Approval granted",
    "approval_rejected": "Approval rejected",
    "session_held": "Live session update",
}


def notify(user, notification_type, message, related_contract=None, metadata=None):
    """
    Create an in-app Notification record for *user* and send an email.

    Args:
        user:                User instance to notify.
        notification_type:   One of Notification.NOTIFICATION_TYPE_CHOICES keys.
        message:             Human-readable body text (reused as email body).
        related_contract:    Optional Contract the notification is about.
        metadata:            Optional supplementary dict.

    Returns:
        The created Notification instance.
    """
    title = _TITLES.get(notification_type, "bonUP notification")

    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        related_contract=related_contract,
        metadata=metadata or {},
    )

    if user.email:
        send_mail(
            subject=title,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bonup.cloud"),
            recipient_list=[user.email],
            fail_silently=True,
        )

    return notification
