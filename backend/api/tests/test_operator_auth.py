from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from backend.api.operator.authentication import BlackboardJWTAuthentication
from backend.operator.models import AdministratorAccount, OperatorAuditEvent, OperatorViewAsSession
from backend.operator.services import validate_administrator_user, validate_real_administrator_account

from .helpers import make_user

User = get_user_model()


def verified_user(username="admin-user", email="admin-user@example.com", password="userpass123"):
    user = make_user(username, email, password)
    profile = user.bon_profile
    profile.email_verified = True
    profile.save(update_fields=["email_verified"])
    return user


def make_administrator(email="admin@bonup.cloud", password="adminpass123", **kwargs):
    user = kwargs.pop("user", None) or verified_user(
        username=f"user-for-{email}",
        email=f"user-for-{email}",
    )
    administrator = AdministratorAccount(
        user=user,
        email=email,
        first_name=kwargs.pop("first_name", "Ada"),
        last_name=kwargs.pop("last_name", "Admin"),
        is_active=kwargs.pop("is_active", True),
        is_super_admin=kwargs.pop("is_super_admin", True),
        can_view_as_user=kwargs.pop("can_view_as_user", True),
        is_legacy_placeholder=kwargs.pop("is_legacy_placeholder", False),
        **kwargs,
    )
    administrator.set_password(password)
    administrator.save()
    return administrator


def make_legacy_placeholder(email="legacy-operator-user-1@invalid.bonup.local", password="adminpass123"):
    administrator = AdministratorAccount(
        user=None,
        email=email,
        first_name="Legacy",
        last_name="Operator",
        is_active=False,
        is_super_admin=False,
        can_view_as_user=False,
        is_legacy_placeholder=True,
    )
    administrator.set_password(password)
    administrator.save()
    return administrator


class AdministratorAccountModelTests(TestCase):
    def test_password_hashes_and_correct_password_authenticates(self):
        administrator = make_administrator(password="secure-admin-pass")

        self.assertNotEqual(administrator.password, "secure-admin-pass")
        self.assertTrue(administrator.check_password("secure-admin-pass"))

    def test_wrong_password_rejected(self):
        administrator = make_administrator(password="secure-admin-pass")

        self.assertFalse(administrator.check_password("wrong"))

    def test_inactive_administrator_rejected_by_operator_login(self):
        make_administrator(is_active=False)

        response = APIClient().post(
            "/api/operator/auth/token/",
            {"email": "admin@bonup.cloud", "password": "adminpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_duplicate_email_rejected(self):
        make_administrator(email="admin@bonup.cloud")

        duplicate = AdministratorAccount(email="admin@bonup.cloud")
        duplicate.set_password("otherpass123")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                duplicate.save()

    def test_only_one_real_administrator_per_user(self):
        user = verified_user("one-admin-user", "one-admin-user@example.com")
        make_administrator(email="admin-one@bonup.cloud", user=user)
        duplicate = AdministratorAccount(user=user, email="admin-two@bonup.cloud")
        duplicate.set_password("otherpass123")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                duplicate.save()

    def test_real_administrator_requires_linked_verified_bonup_user(self):
        active_verified = verified_user("eligible", "eligible@example.com")
        self.assertEqual(validate_administrator_user(active_verified).bon_id, active_verified.bon_profile.bon_id)

        inactive = verified_user("inactive", "inactive@example.com")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            validate_administrator_user(inactive)

        unverified = make_user("unverified", "unverified@example.com", "userpass123")
        with self.assertRaises(ValidationError):
            validate_administrator_user(unverified)

        no_bon_id = verified_user("no-bonid", "no-bonid@example.com")
        no_bon_id.bon_profile.bon_id = ""
        no_bon_id.bon_profile.save(update_fields=["bon_id"])
        with self.assertRaises(ValidationError):
            validate_administrator_user(no_bon_id)

    def test_legacy_placeholder_is_exempt_from_user_link_but_cannot_authenticate(self):
        placeholder = make_legacy_placeholder(password="legacy-pass-123")

        with self.assertRaises(ValidationError):
            validate_real_administrator_account(placeholder)
        response = APIClient().post(
            "/api/operator/auth/token/",
            {"email": placeholder.email, "password": "legacy-pass-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_administrator_uses_linked_user_bonid_without_generating_second_bonid(self):
        user = verified_user("bonid-admin-user", "bonid-admin-user@example.com")
        bon_id = user.bon_profile.bon_id
        administrator = make_administrator(email="bonid-admin@bonup.cloud", user=user)

        self.assertEqual(administrator.user.bon_profile.bon_id, bon_id)
        self.assertNotEqual(str(administrator.pk), bon_id)
        self.assertEqual(user.bon_profile.bon_id, bon_id)


class OperatorAuthenticationTests(TestCase):
    user_password = "testpass123"
    admin_password = "adminpass123"

    def setUp(self):
        self.client = APIClient()
        self.administrator = make_administrator(
            email="owner@bonup.cloud",
            password=self.admin_password,
            first_name="Opal",
            last_name="Operator",
            is_super_admin=True,
            can_view_as_user=True,
        )
        self.staff_user = make_user("staff-user@example.com", "staff-user@example.com", self.user_password)
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=["is_staff"])
        self.superuser = User.objects.create_superuser(
            username="superuser@example.com",
            email="superuser@example.com",
            password=self.user_password,
        )
        self.target = make_user("target@example.com", "target@example.com", self.user_password)
        self.normal = make_user("normal@example.com", "normal@example.com", self.user_password)
        self.same_email_user = make_user("owner-user", "owner@bonup.cloud", self.user_password)
        for user in [self.staff_user, self.superuser, self.target, self.normal, self.same_email_user]:
            profile = user.bon_profile
            profile.email_verified = True
            profile.save(update_fields=["email_verified"])

    def post_normal_login(self, user):
        return self.client.post(
            "/api/auth/token/",
            {"username": user.email, "password": self.user_password},
            format="json",
        )

    def post_operator_login(self, email=None, password=None):
        return self.client.post(
            "/api/operator/auth/token/",
            {"email": email or self.administrator.email, "password": password or self.admin_password},
            format="json",
        )

    def bearer(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def operator_access(self):
        response = self.post_operator_login()
        self.assertEqual(response.status_code, 200)
        return response.data["access"], response.data["refresh"]

    def normal_access(self, user=None):
        response = self.post_normal_login(user or self.normal)
        self.assertEqual(response.status_code, 200)
        return response.data["access"], response.data["refresh"]

    def start_view_as(self):
        access, _ = self.operator_access()
        response = self.bearer(access).post(f"/api/operator/view-as/{self.target.id}/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        return data_with_operator_access(response.data, access)

    def test_dedicated_administrator_can_get_admin_token(self):
        response = self.post_operator_login()

        self.assertEqual(response.status_code, 200)
        token = AccessToken(response.data["access"])
        self.assertEqual(token["auth_context"], "operator")
        self.assertEqual(token["administrator_id"], self.administrator.id)
        self.assertNotIn("user_id", token)
        self.assertEqual(response.data["operator"]["email"], self.administrator.email)
        self.assertEqual(response.data["operator"]["user_id"], self.administrator.user_id)
        self.assertEqual(response.data["operator"]["bon_id"], self.administrator.user.bon_profile.bon_id)
        self.assertEqual(OperatorAuditEvent.objects.filter(action="operator_login", administrator=self.administrator).count(), 1)

    def test_normal_user_with_same_email_cannot_authenticate_operator_endpoint(self):
        response = self.post_operator_login(email=self.same_email_user.email, password=self.user_password)

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)

    def test_admin_password_cannot_authenticate_normal_user_endpoint(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": self.administrator.email, "password": self.admin_password},
            format="json",
        )

        self.assertNotEqual(response.status_code, 200)

    def test_normal_staff_user_cannot_authenticate_operator_endpoint(self):
        response = self.post_operator_login(email=self.staff_user.email, password=self.user_password)

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)

    def test_normal_superuser_cannot_authenticate_operator_endpoint(self):
        response = self.post_operator_login(email=self.superuser.email, password=self.user_password)

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)

    def test_admin_token_resolves_administrator_identity(self):
        access, _ = self.operator_access()
        request = APIRequestFactory().get("/api/operator/me/", HTTP_AUTHORIZATION=f"Bearer {access}")

        user, _ = BlackboardJWTAuthentication().authenticate(request)

        self.assertFalse(user.is_authenticated)
        self.assertEqual(request.administrator, self.administrator)
        self.assertIsNone(request.operator_user)

    def test_admin_token_does_not_act_as_normal_user_token(self):
        access, _ = self.operator_access()

        response = self.bearer(access).get("/api/users/me/")

        self.assertEqual(response.status_code, 403)

    def test_normal_login_for_staff_does_not_create_operator_context_or_admin_access(self):
        access, refresh = self.normal_access(self.staff_user)

        self.assertIsNone(AccessToken(access).get("auth_context"))
        self.assertEqual(self.bearer(access).get("/api/admin/summary/").status_code, 403)
        self.assertEqual(self.bearer(access).get("/api/operator/me/").status_code, 403)

        refresh_response = self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIsNone(AccessToken(refresh_response.data["access"]).get("auth_context"))

    def test_admin_login_and_refresh_use_operator_context(self):
        response = self.post_operator_login()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AccessToken(response.data["access"])["auth_context"], "operator")
        self.assertEqual(self.bearer(response.data["access"]).get("/api/admin/summary/").status_code, 200)

        refresh_response = self.client.post(
            "/api/operator/auth/token/refresh/",
            {"refresh": response.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 200)
        refreshed = AccessToken(refresh_response.data["access"])
        self.assertEqual(refreshed["auth_context"], "operator")
        self.assertEqual(refreshed["administrator_id"], self.administrator.id)

        normal_refresh_response = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": response.data["refresh"]},
            format="json",
        )
        self.assertNotEqual(normal_refresh_response.status_code, 200)

    def test_normal_refresh_cannot_use_operator_refresh_endpoint(self):
        _, refresh = self.normal_access()

        response = self.client.post("/api/operator/auth/token/refresh/", {"refresh": refresh}, format="json")

        self.assertNotEqual(response.status_code, 200)

    def test_impersonation_token_cannot_access_admin_apis(self):
        data = self.start_view_as()
        client = self.bearer(data["access"])

        self.assertEqual(client.get("/api/admin/summary/").status_code, 403)
        self.assertEqual(client.get("/api/operator/me/").status_code, 403)

    def test_administrator_starts_view_as_without_target_password(self):
        data = self.start_view_as()
        token = AccessToken(data["access"])
        session = OperatorViewAsSession.objects.get(pk=data["view_as_session_id"])

        self.assertEqual(token["auth_context"], "impersonation")
        self.assertEqual(int(token["administrator_id"]), self.administrator.id)
        self.assertEqual(int(token["effective_user_id"]), self.target.id)
        self.assertEqual(session.administrator, self.administrator)
        self.assertEqual(session.target_user, self.target)
        self.assertTrue(session.is_active)
        self.assertEqual(OperatorAuditEvent.objects.filter(action="view_as_started", view_as_session=session, administrator=self.administrator).count(), 1)
        self.assertEqual(OperatorAuditEvent.objects.get(action="view_as_started", view_as_session=session).administrator, self.administrator)

    def test_impersonation_sets_effective_user_and_administrator_on_request(self):
        data = self.start_view_as()
        request = APIRequestFactory().get("/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {data['access']}")

        user, _ = BlackboardJWTAuthentication().authenticate(request)

        self.assertEqual(user, self.target)
        self.assertEqual(request.administrator, self.administrator)
        self.assertEqual(request.impersonation_session.administrator, self.administrator)
        self.assertFalse(hasattr(user, "is_super_admin"))

    def test_impersonation_is_read_only_for_write_methods(self):
        data = self.start_view_as()
        client = self.bearer(data["access"])

        self.assertEqual(client.get("/api/users/me/").status_code, 200)
        self.assertEqual(client.post("/api/users/me/change-password/", {}, format="json").status_code, 403)
        self.assertEqual(client.put("/api/users/me/", {}, format="json").status_code, 403)
        self.assertEqual(client.patch("/api/users/me/", {"first_name": "Changed"}, format="json").status_code, 403)
        self.assertEqual(client.delete("/api/users/me/").status_code, 403)

    def test_view_as_exit_ends_session_audits_and_preserves_admin_session(self):
        data = self.start_view_as()
        session_id = data["view_as_session_id"]
        impersonation_client = self.bearer(data["access"])

        response = impersonation_client.post("/api/operator/view-as/exit/", {"view_as_session_id": session_id}, format="json")

        self.assertEqual(response.status_code, 200)
        session = OperatorViewAsSession.objects.get(pk=session_id)
        self.assertIsNotNone(session.ended_at)
        self.assertEqual(OperatorAuditEvent.objects.filter(action="view_as_ended", view_as_session=session, administrator=self.administrator).count(), 1)
        self.assertEqual(self.bearer(data["operator_access"]).get("/api/operator/me/").status_code, 200)

    def test_impersonation_token_has_no_refresh_path(self):
        data = self.start_view_as()

        response = self.client.post("/api/auth/token/refresh/", {"refresh": data["access"]}, format="json")

        self.assertNotEqual(response.status_code, 200)

    def test_expired_view_as_session_invalidates_impersonation_token(self):
        data = self.start_view_as()
        session = OperatorViewAsSession.objects.get(pk=data["view_as_session_id"])
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=["expires_at"])

        response = self.bearer(data["access"]).get("/api/users/me/")

        self.assertEqual(response.status_code, 401)

    def test_ended_view_as_session_invalidates_impersonation_token(self):
        data = self.start_view_as()
        session = OperatorViewAsSession.objects.get(pk=data["view_as_session_id"])
        session.end(reason="test")

        response = self.bearer(data["access"]).get("/api/users/me/")

        self.assertEqual(response.status_code, 401)

    def test_direct_normal_user_login_continues_working(self):
        access, _ = self.normal_access(self.target)

        response = self.bearer(access).get("/api/users/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.target.email)

    def test_normal_user_does_not_administer_operator_console(self):
        access, _ = self.normal_access(self.normal)

        self.assertEqual(self.bearer(access).get("/api/admin/users/").status_code, 403)


def data_with_operator_access(data, operator_access):
    copied = dict(data)
    copied["operator_access"] = operator_access
    return copied
