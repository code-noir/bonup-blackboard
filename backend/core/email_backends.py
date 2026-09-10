import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    """
    Django email backend that sends plain-text messages through Resend's HTTPS API.
    """

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                sent = self._send_message(message)
            except Exception:
                if not self.fail_silently:
                    raise
            else:
                if sent:
                    sent_count += 1

        return sent_count

    def _send_message(self, message):
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            raise RuntimeError("RESEND_API_KEY is not configured.")

        from_email = message.from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "")
        recipient_list = list(message.to or [])
        if not from_email:
            raise RuntimeError("DEFAULT_FROM_EMAIL is not configured.")
        if not recipient_list:
            return False

        payload = {
            "from": from_email,
            "to": recipient_list,
            "subject": message.subject,
            "text": message.body,
        }

        response = requests.post(
            getattr(settings, "RESEND_API_URL", "https://api.resend.com/emails"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=getattr(settings, "RESEND_TIMEOUT", 10),
        )
        response.raise_for_status()
        return True


class PrivacyConsoleEmailBackend(BaseEmailBackend):
    """Development placeholder: never writes email bodies or bearer links to stdout."""
    def send_messages(self, email_messages):
        from backend.core.privacy_logging import safe_event
        messages = list(email_messages or [])
        if messages:
            safe_event("development_email_suppressed")
        return 0
