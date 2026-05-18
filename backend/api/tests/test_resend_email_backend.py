from unittest.mock import Mock, patch

from django.core.mail import send_mail
from django.test import SimpleTestCase, override_settings
from requests import Timeout


@override_settings(
    EMAIL_BACKEND="backend.core.email_backends.ResendEmailBackend",
    DEFAULT_FROM_EMAIL="noreply@bonup.cloud",
    RESEND_API_KEY="test-resend-api-key",
    RESEND_API_URL="https://api.resend.com/emails",
    RESEND_TIMEOUT=10,
)
class ResendEmailBackendTests(SimpleTestCase):
    @patch("backend.core.email_backends.requests.post")
    def test_send_mail_posts_plain_text_payload_to_resend(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        sent_count = send_mail(
            subject="Verify your bonUP email address",
            message="Click the verification link.",
            from_email="noreply@bonup.cloud",
            recipient_list=["new-user@example.com"],
            fail_silently=False,
        )

        self.assertEqual(sent_count, 1)
        mock_post.assert_called_once_with(
            "https://api.resend.com/emails",
            headers={
                "Authorization": "Bearer test-resend-api-key",
                "Content-Type": "application/json",
            },
            json={
                "from": "noreply@bonup.cloud",
                "to": ["new-user@example.com"],
                "subject": "Verify your bonUP email address",
                "text": "Click the verification link.",
            },
            timeout=10,
        )

    @patch("backend.core.email_backends.requests.post")
    def test_returns_zero_when_fail_silently_and_resend_times_out(self, mock_post):
        mock_post.side_effect = Timeout("timed out")

        sent_count = send_mail(
            subject="Reset your bonUP password",
            message="Click the reset link.",
            from_email="noreply@bonup.cloud",
            recipient_list=["user@example.com"],
            fail_silently=True,
        )

        self.assertEqual(sent_count, 0)

    @patch("backend.core.email_backends.requests.post")
    def test_raises_when_resend_fails_and_fail_silently_false(self, mock_post):
        mock_post.side_effect = Timeout("timed out")

        with self.assertRaises(Timeout):
            send_mail(
                subject="Reset your bonUP password",
                message="Click the reset link.",
                from_email="noreply@bonup.cloud",
                recipient_list=["user@example.com"],
                fail_silently=False,
            )

    @override_settings(RESEND_API_KEY="")
    def test_missing_api_key_respects_fail_silently(self):
        sent_count = send_mail(
            subject="Verify your bonUP email address",
            message="Click the verification link.",
            from_email="noreply@bonup.cloud",
            recipient_list=["new-user@example.com"],
            fail_silently=True,
        )

        self.assertEqual(sent_count, 0)
