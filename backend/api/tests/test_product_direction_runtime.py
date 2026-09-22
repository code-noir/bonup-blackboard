import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID, uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_runtime import (
    ProductDirectionRuntimeRequest,
    ProductRuntimeUnavailable,
    TrustedProd01Runtime,
    agent_control_task_id_for,
)
from tools.agent_control.serialization import canonical_json

from backend.bonup.models import ProductDirectionTask

from .test_product_direction import make_administrator


class TrustedFakeTransport:
    credential_owned = True

    def __init__(self, *, fail=False, invalid=False):
        self.calls = []
        self.fail = fail
        self.invalid = invalid

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("synthetic transport failure")
        request = json.loads(kwargs["request"])
        task = request["context"]
        proposal = {
            "agent_id": "PROD-01",
            "task_id": task["task_id"],
            "proposal_id": "00000000-0000-4000-8000-000000000701",
            "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
            "title": "Product direction result",
            "problem_user_need": "A bounded product direction needs a validated result.",
            "objective": task["objective"],
            "proposed_requirement": "The system should display the validated product result.",
            "acceptance_intent": ["The result is available for Founder review."],
            "dependencies": [],
            "assumptions": [],
            "risks_open_questions": [],
            "priority_recommendation": "P2",
            "evidence_references": [],
            "knowledge_state": "WORKING",
            "predecessor_proposal_id": None,
        }
        if self.invalid:
            proposal["knowledge_state"] = "APPROVED_INTERNAL"
        envelope = {
            "id": "response_synthetic",
            "status": "completed",
            "output": [{
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": canonical_json(proposal),
                }],
            }],
        }
        self.assert_no_credential(kwargs)
        return canonical_json(envelope).encode("utf-8")

    @staticmethod
    def assert_no_credential(kwargs):
        assert kwargs["credential"] is None
        assert "credential" not in kwargs["request"].decode("utf-8").lower()


class ProductDirectionRuntimeTests(TestCase):
    def setUp(self):
        self.administrator = make_administrator(email="runtime-admin@bonup.cloud")

    def operator_client(self):
        client = APIClient()
        response = client.post(
            "/api/operator/auth/token/",
            {"email": self.administrator.email, "password": "adminpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return client

    def create_task(self, client):
        response = client.post(
            "/api/product-direction/tasks/",
            {"objective": "Define a bounded product direction."},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data["task_id"]

    def test_runtime_maps_product_task_and_persists_validated_result(self):
        application_id = str(uuid4())
        agent_control_id = agent_control_task_id_for(application_id)
        transport = TrustedFakeTransport()
        with TemporaryDirectory(prefix="bonup-prod-runtime-", dir="/tmp") as directory:
            runtime = TrustedProd01Runtime(
                transport,
                source_checkpoint="a" * 40,
                artifact_store=ProposalArtifactStore(directory),
            )
            result = runtime.submit(ProductDirectionRuntimeRequest(
                application_task_id=application_id,
                agent_control_task_id=agent_control_id,
                agent_id="PROD-01",
                objective="Define a bounded product direction.",
            ))

            self.assertEqual(result.agent_control_task_id, agent_control_id)
            self.assertEqual(result.proposal_id, "00000000-0000-4000-8000-000000000701")
            self.assertEqual(result.proposal_artifact_id, "PROD-01-" + result.proposal_id)
            self.assertEqual(len(transport.calls), 1)
            self.assertTrue((Path(directory) / (
                "proposal-" + result.proposal_id + ".json")).exists())

    def test_api_success_transitions_once_and_binds_safe_result(self):
        client = self.operator_client()
        task_id = self.create_task(client)
        transport = TrustedFakeTransport()
        with TemporaryDirectory(prefix="bonup-prod-runtime-", dir="/tmp") as directory:
            runtime = TrustedProd01Runtime(
                transport,
                source_checkpoint="a" * 40,
                artifact_store=ProposalArtifactStore(directory),
            )
            with patch(
                "backend.api.product_direction.views.submit_product_direction_task",
                runtime.submit,
            ):
                first = client.post(f"/api/product-direction/tasks/{task_id}/submit/", {}, format="json")
                second = client.post(f"/api/product-direction/tasks/{task_id}/submit/", {}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["status"], "WORKING_PROPOSAL")
        self.assertEqual(first.data["agent_id"], "PROD-01")
        self.assertEqual(first.data["proposal_artifact_id"], "PROD-01-00000000-0000-4000-8000-000000000701")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(len(transport.calls), 1)
        task = ProductDirectionTask.objects.get(pk=UUID(task_id))
        self.assertEqual(task.status, ProductDirectionTask.STATUS_WORKING_PROPOSAL)
        self.assertNotIn("credential", first.content.decode().lower())
        self.assertNotIn("provider", first.content.decode().lower())

    def test_failed_runtime_blocks_without_retry(self):
        client = self.operator_client()
        task_id = self.create_task(client)
        transport = TrustedFakeTransport(fail=True)
        with TemporaryDirectory(prefix="bonup-prod-runtime-", dir="/tmp") as directory:
            runtime = TrustedProd01Runtime(
                transport,
                source_checkpoint="a" * 40,
                artifact_store=ProposalArtifactStore(directory),
            )
            with patch("backend.api.product_direction.views.submit_product_direction_task", runtime.submit):
                response = client.post(f"/api/product-direction/tasks/{task_id}/submit/", {}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["reason"], "PROVIDER_ERROR")
        self.assertEqual(response.data["task"]["status"], "BLOCKED")
        self.assertEqual(len(transport.calls), 1)
        self.assertNotIn("synthetic transport failure", response.content.decode())

    def test_unavailable_runtime_keeps_submission_retryable(self):
        client = self.operator_client()
        task_id = self.create_task(client)
        transport = TrustedFakeTransport()
        with TemporaryDirectory(prefix="bonup-prod-recovery-", dir="/tmp") as directory:
            runtime = TrustedProd01Runtime(
                transport,
                source_checkpoint="a" * 40,
                artifact_store=ProposalArtifactStore(directory),
            )
            attempts = iter(("unavailable", "recover"))

            def submit(request):
                if next(attempts) == "unavailable":
                    raise ProductRuntimeUnavailable()
                return runtime.submit(request)

            with patch(
                "backend.api.product_direction.views.submit_product_direction_task",
                side_effect=submit,
            ) as submit_mock:
                unavailable = client.post(
                    f"/api/product-direction/tasks/{task_id}/submit/", {}, format="json")
                recovered = client.post(
                    f"/api/product-direction/tasks/{task_id}/submit/", {}, format="json")

        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.data["task"]["status"], ProductDirectionTask.STATUS_RUNNING)
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.data["status"], ProductDirectionTask.STATUS_WORKING_PROPOSAL)
        self.assertEqual(submit_mock.call_count, 2)
        self.assertEqual(len(transport.calls), 1)

    def test_submit_rejects_runtime_controls_and_unauthenticated_request(self):
        client = self.operator_client()
        task_id = self.create_task(client)
        response = client.post(
            f"/api/product-direction/tasks/{task_id}/submit/",
            {"model": "caller-selected", "tools": [], "credential": "secret"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        unauthenticated = APIClient().post(
            f"/api/product-direction/tasks/{task_id}/submit/", {}, format="json")
        self.assertEqual(unauthenticated.status_code, 401)

    def test_strict_invalid_proposal_blocks_and_does_not_persist_artifact(self):
        client = self.operator_client()
        task_id = self.create_task(client)
        transport = TrustedFakeTransport(invalid=True)
        with TemporaryDirectory(prefix="bonup-prod-runtime-", dir="/tmp") as directory:
            runtime = TrustedProd01Runtime(
                transport,
                source_checkpoint="a" * 40,
                artifact_store=ProposalArtifactStore(directory),
            )
            with patch("backend.api.product_direction.views.submit_product_direction_task", runtime.submit):
                response = client.post(f"/api/product-direction/tasks/{task_id}/submit/", {}, format="json")
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["reason"], "KNOWLEDGE_STATE_INVALID")
