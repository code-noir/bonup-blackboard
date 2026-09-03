import base64
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from backend.emailing.services import (
    EmailAttachment,
    EmailMessage,
    EmailProviderDeliveryError,
    EmailServiceUnavailable,
    ResendEmailProvider,
)


class ResendEmailProviderTests(SimpleTestCase):

    def message(self):
        return EmailMessage(
            to=["recipient@example.com"],
            subject="Subject",
            text="Body",
            attachments=[
                EmailAttachment(
                    filename="contract.pdf",
                    content=b"pdf bytes",
                    content_type="application/pdf",
                )
            ],
        )

    @override_settings(RESEND_API_KEY="", BONUP_EMAIL_FROM="")
    def test_provider_requires_configuration(self):
        with self.assertRaises(EmailServiceUnavailable):
            ResendEmailProvider().send(self.message())

    @override_settings(
        RESEND_API_KEY="re_test",
        BONUP_EMAIL_FROM="bonUP <vault@example.com>",
        RESEND_API_URL="https://api.resend.com/emails",
        RESEND_TIMEOUT=7,
    )
    @patch("backend.emailing.services.requests.post")
    def test_provider_sends_base64_attachment_with_idempotency_key(self, mock_post):
        mock_post.return_value.json.return_value = {"id": "em_123"}
        mock_post.return_value.raise_for_status.return_value = None

        result = ResendEmailProvider().send(self.message(), idempotency_key="once")

        self.assertEqual(result.provider, "resend")
        self.assertEqual(result.provider_message_id, "em_123")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "once")
        self.assertEqual(kwargs["timeout"], 7)
        self.assertEqual(kwargs["json"]["from"], "bonUP <vault@example.com>")
        self.assertEqual(kwargs["json"]["to"], ["recipient@example.com"])
        attachment = kwargs["json"]["attachments"][0]
        self.assertEqual(attachment["filename"], "contract.pdf")
        self.assertEqual(attachment["content"], base64.b64encode(b"pdf bytes").decode("ascii"))
        self.assertEqual(attachment["content_type"], "application/pdf")

    @override_settings(RESEND_API_KEY="re_test", BONUP_EMAIL_FROM="bonUP <vault@example.com>")
    @patch("backend.emailing.services.requests.post")
    def test_provider_failure_is_sanitized(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("provider secret details")

        with self.assertRaises(EmailProviderDeliveryError):
            ResendEmailProvider().send(self.message())
