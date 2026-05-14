from django.test import TestCase
from rest_framework.test import APIClient

from .helpers import make_user


class LoginEmailVerificationTests(TestCase):
    password = "testpass123"

    def setUp(self):
        self.client = APIClient()

    def _make_user(self, email, verified):
        user = make_user(email, email, password=self.password)
        profile = user.bon_profile
        profile.email_verified = verified
        profile.save(update_fields=["email_verified"])
        return user

    def _post_login(self, url, email):
        return self.client.post(
            url,
            {"username": email, "password": self.password},
            format="json",
        )

    def assert_login_blocked(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def assert_login_allowed(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_users_login_rejects_unverified_user(self):
        user = self._make_user("users-login-unverified@example.com", verified=False)

        response = self._post_login("/api/users/login/", user.email)

        self.assert_login_blocked(response)

    def test_users_login_allows_verified_user(self):
        user = self._make_user("users-login-verified@example.com", verified=True)

        response = self._post_login("/api/users/login/", user.email)

        self.assert_login_allowed(response)

    def test_auth_token_rejects_unverified_user(self):
        user = self._make_user("auth-token-unverified@example.com", verified=False)

        response = self._post_login("/api/auth/token/", user.email)

        self.assert_login_blocked(response)

    def test_auth_token_allows_verified_user(self):
        user = self._make_user("auth-token-verified@example.com", verified=True)

        response = self._post_login("/api/auth/token/", user.email)

        self.assert_login_allowed(response)
