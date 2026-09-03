import base64
from dataclasses import dataclass, field
from typing import Protocol

import requests
from django.conf import settings


class EmailServiceUnavailable(RuntimeError):
    code = "email_service_unavailable"


class EmailProviderDeliveryError(RuntimeError):
    code = "provider_delivery_failure"


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass(frozen=True)
class EmailMessage:
    to: list[str]
    subject: str
    text: str
    attachments: list[EmailAttachment] = field(default_factory=list)


@dataclass(frozen=True)
class EmailDeliveryResult:
    provider: str
    provider_message_id: str = ""


class EmailProvider(Protocol):
    provider_name: str

    def send(self, message: EmailMessage, *, idempotency_key: str = "") -> EmailDeliveryResult:
        ...


class ResendEmailProvider:
    provider_name = "resend"

    def send(self, message: EmailMessage, *, idempotency_key: str = "") -> EmailDeliveryResult:
        api_key = getattr(settings, "RESEND_API_KEY", "")
        from_email = getattr(settings, "BONUP_EMAIL_FROM", "")
        if not api_key or not from_email:
            raise EmailServiceUnavailable("Email delivery is not configured.")

        attachments = []
        for attachment in message.attachments:
            payload = {
                "filename": attachment.filename,
                "content": base64.b64encode(attachment.content).decode("ascii"),
            }
            if attachment.content_type:
                payload["content_type"] = attachment.content_type
            attachments.append(payload)

        payload = {
            "from": from_email,
            "to": message.to,
            "subject": message.subject,
            "text": message.text,
        }
        if attachments:
            payload["attachments"] = attachments

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = requests.post(
                getattr(settings, "RESEND_API_URL", "https://api.resend.com/emails"),
                headers=headers,
                json=payload,
                timeout=getattr(settings, "RESEND_TIMEOUT", 10),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise EmailProviderDeliveryError("Email provider delivery failed.") from exc

        try:
            data = response.json()
        except ValueError:
            data = {}
        return EmailDeliveryResult(
            provider=self.provider_name,
            provider_message_id=str(data.get("id") or ""),
        )


def get_email_provider() -> EmailProvider:
    provider = getattr(settings, "BONUP_EMAIL_PROVIDER", "resend").strip().lower()
    if provider == "resend":
        return ResendEmailProvider()
    raise EmailServiceUnavailable("Email provider is not configured.")


def send_email(message: EmailMessage, *, idempotency_key: str = "") -> EmailDeliveryResult:
    return get_email_provider().send(message, idempotency_key=idempotency_key)
