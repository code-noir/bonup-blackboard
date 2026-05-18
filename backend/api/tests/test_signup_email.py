from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from backend.users.models import PendingSignup


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@bonup.cloud",
    FRONTEND_URL="https://app.bonup.cloud",
)
class SignupEmailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        mail.outbox = []

    def test_register_creates_pending_signup_and_sends_verification_email(self):
        response = self.client.post(
            "/api/users/register/",
            {
                "email": "signup-email-test@example.com",
                "password": "StrongSignupPass123!",
                "first_name": "Signup",
                "last_name": "Tester",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        pending = PendingSignup.objects.get(email="signup-email-test@example.com")

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Verify your bonUP email address")
        self.assertEqual(message.from_email, "noreply@bonup.cloud")
        self.assertEqual(message.to, ["signup-email-test@example.com"])
        self.assertIn(
            f"https://app.bonup.cloud/verify-email?token={pending.token}",
            message.body,
        )
