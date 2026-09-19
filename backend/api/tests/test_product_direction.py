from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from backend.bonup.models import ProductDirectionTask
from backend.operator.models import AdministratorAccount

from .helpers import make_user


User = get_user_model()


def make_verified_user(username, email, password="userpass123"):
    user = make_user(username, email, password)
    profile = user.bon_profile
    profile.email_verified = True
    profile.save(update_fields=["email_verified"])
    return user


def make_administrator(email="product-admin@bonup.cloud", password="adminpass123"):
    user = make_verified_user(
        username=f"user-for-{email}",
        email=f"user-for-{email}",
    )
    administrator = AdministratorAccount(
        user=user,
        email=email,
        first_name="Product",
        last_name="Admin",
        is_active=True,
        is_super_admin=True,
        can_view_as_user=True,
    )
    administrator.set_password(password)
    administrator.save()
    return administrator


class ProductDirectionTaskAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.administrator = make_administrator()

    def operator_client(self):
        response = self.client.post(
            "/api/operator/auth/token/",
            {"email": self.administrator.email, "password": "adminpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return client

    def test_authorized_operator_creates_bounded_submitted_task(self):
        client = self.operator_client()

        response = client.post(
            "/api/product-direction/tasks/",
            {"objective": "Define the first product-direction workflow."},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["agent_id"], "PROD-01")
        self.assertEqual(response.data["status"], "SUBMITTED")
        self.assertIsNone(response.data["agent_control_task_id"])
        self.assertEqual(response.data["objective"], "Define the first product-direction workflow.")
        self.assertEqual(response.data["created_by"]["email"], self.administrator.email)
        self.assertEqual(ProductDirectionTask.objects.count(), 1)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.post(
            "/api/product-direction/tasks/",
            {"objective": "Should not be accepted."},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_normal_user_is_rejected(self):
        user = make_verified_user("normal-product-user", "normal-product-user@example.com")
        response = APIClient().post(
            "/api/auth/token/",
            {"username": user.email, "password": "userpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

        result = client.post(
            "/api/product-direction/tasks/",
            {"objective": "Normal users cannot submit operator tasks."},
            format="json",
        )

        self.assertEqual(result.status_code, 403)

    def test_objective_is_required_and_bounded(self):
        client = self.operator_client()

        missing = client.post("/api/product-direction/tasks/", {}, format="json")
        oversized = client.post(
            "/api/product-direction/tasks/",
            {"objective": "x" * 4097},
            format="json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(oversized.status_code, 400)
        self.assertEqual(ProductDirectionTask.objects.count(), 0)

    def test_forbidden_control_fields_are_rejected(self):
        client = self.operator_client()
        forbidden = {
            "agent_id": "ARCH-01",
            "model": "untrusted-model",
            "endpoint": "https://example.invalid",
            "credential": "synthetic-secret-sentinel",
            "tools": [],
            "knowledge_state": "APPROVED_INTERNAL",
            "decision": "ACCEPT",
            "arch_destination": "ARCH-01",
        }

        for field, value in forbidden.items():
            with self.subTest(field=field):
                response = client.post(
                    "/api/product-direction/tasks/",
                    {"objective": "A bounded objective.", field: value},
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(ProductDirectionTask.objects.count(), 0)

    def test_objective_rejects_secret_material_without_echoing_it(self):
        client = self.operator_client()
        sentinel = "synthetic-secret-sentinel"

        response = client.post(
            "/api/product-direction/tasks/",
            {"objective": f"api_key: {sentinel}"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(sentinel, response.content.decode())

    def test_list_and_detail_return_safe_exact_task(self):
        client = self.operator_client()
        create = client.post(
            "/api/product-direction/tasks/",
            {"objective": "Display validated product direction."},
            format="json",
        )
        task_id = create.data["task_id"]

        listed = client.get("/api/product-direction/tasks/")
        detail = client.get(f"/api/product-direction/tasks/{task_id}/")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["results"][0], detail.data)
        self.assertEqual(
            set(detail.data),
            {
                "task_id",
                "agent_control_task_id",
                "agent_id",
                "objective",
                "status",
                "created_by",
                "created_at",
                "updated_at",
            },
        )
        self.assertNotIn("password", detail.data)
        self.assertNotIn("credential", detail.data)
        self.assertNotIn("knowledge_state", detail.data)
        self.assertNotIn("decision", detail.data)

    def test_creation_does_not_invoke_live_prod_or_create_authority(self):
        client = self.operator_client()

        with patch("tools.agent_control.prod_first_live.run_first_live") as live:
            response = client.post(
                "/api/product-direction/tasks/",
                {"objective": "Create only application input."},
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        live.assert_not_called()
        task = ProductDirectionTask.objects.get(pk=response.data["task_id"])
        self.assertEqual(task.status, ProductDirectionTask.STATUS_SUBMITTED)
        self.assertIsNone(task.agent_control_task_id)
