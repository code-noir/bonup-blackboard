from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID, uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_runtime import agent_control_task_id_for

from backend.bonup.models import ProductDirectionTask

from .test_product_direction import make_administrator, make_verified_user


def working_proposal(task_id, *, evidence=True, proposal_id=None):
    references = [{
        "reference_type": "FOUNDER_DIRECTION",
        "reference_id": "FOUNDER-DIRECTION-M3-001",
        "digest": "a" * 64,
        "knowledge_state": "DIRECT_FOUNDER",
    }] if evidence else []
    return {
        "agent_id": "PROD-01",
        "task_id": task_id,
        "proposal_id": proposal_id or "00000000-0000-4000-8000-000000000703",
        "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
        "title": "Validated product direction",
        "problem_user_need": "The operator needs to review one exact product proposal.",
        "objective": "Define a bounded product direction.",
        "proposed_requirement": "The product should display one validated proposal.",
        "acceptance_intent": ["The Founder can inspect the exact proposal fields."],
        "dependencies": [],
        "assumptions": ["The immutable artifact is available to the trusted reader."],
        "risks_open_questions": ["Founder review remains a separate step."],
        "priority_recommendation": "P2",
        "evidence_references": references,
        "knowledge_state": "WORKING",
        "predecessor_proposal_id": None,
    }


class ProductDirectionProposalReadTests(TestCase):
    def setUp(self):
        self.administrator = make_administrator(email="proposal-read@bonup.cloud")
        self.client = self.operator_client()
        self.directory = TemporaryDirectory(prefix="bonup-prod-read-", dir="/tmp")
        self.store = ProposalArtifactStore(self.directory.name)
        self.task, self.artifact_path = self.make_working_task()

    def tearDown(self):
        self.directory.cleanup()

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

    def make_working_task(self, *, status=ProductDirectionTask.STATUS_WORKING_PROPOSAL):
        application_id = uuid4()
        agent_control_id = agent_control_task_id_for(application_id)
        proposal = working_proposal(agent_control_id, proposal_id=str(uuid4()))
        artifact = self.store.persist(proposal, source_checkpoint="a" * 40)
        task = ProductDirectionTask.objects.create(
            id=application_id,
            agent_control_task_id=agent_control_id,
            agent_id="PROD-01",
            objective=proposal["objective"],
            status=status,
            proposal_artifact_id=artifact.artifact_id,
            proposal_id=UUID(proposal["proposal_id"]),
            proposal_digest=artifact.value["proposal_digest"],
            created_by=self.administrator,
        )
        return task, Path(artifact.path)

    def read(self, task=None, **query):
        task = task or self.task
        suffix = "?" + "&".join(f"{key}={value}" for key, value in query.items()) if query else ""
        with patch(
            "backend.api.product_direction.proposal.get_proposal_artifact_store",
            return_value=self.store,
        ):
            return self.client.get(
                f"/api/product-direction/tasks/{task.id}/proposal/{suffix}")

    def test_authorized_read_returns_exact_safe_validated_projection(self):
        before = self.artifact_path.read_bytes()
        response = self.read(artifact_path="/tmp/caller-selected.json")
        after = self.artifact_path.read_bytes()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["application_task_id"], str(self.task.id))
        self.assertEqual(response.data["agent_control_task_id"], self.task.agent_control_task_id)
        self.assertEqual(response.data["agent_id"], "PROD-01")
        self.assertEqual(response.data["proposal_id"], str(self.task.proposal_id))
        self.assertEqual(response.data["proposal_digest"], self.task.proposal_digest)
        self.assertEqual(response.data["knowledge_state"], "WORKING")
        self.assertEqual(response.data["evidence_references"][0]["reference_id"],
                         "FOUNDER-DIRECTION-M3-001")
        self.assertNotIn("path", response.data)
        self.assertNotIn("provider", response.data)
        self.assertNotIn("credential", response.data)
        self.assertNotIn("reasoning", response.data)
        self.assertEqual(before, after)

    def test_unauthenticated_and_normal_user_reads_are_rejected(self):
        unauthenticated = APIClient().get(
            f"/api/product-direction/tasks/{self.task.id}/proposal/")
        self.assertEqual(unauthenticated.status_code, 401)

        normal_user = make_verified_user("proposal-reader", "proposal-reader@example.com")
        normal = APIClient().post(
            "/api/auth/token/",
            {"username": normal_user.email, "password": "userpass123"},
            format="json",
        )
        self.assertEqual(normal.status_code, 200)
        normal_client = APIClient()
        normal_client.credentials(HTTP_AUTHORIZATION=f"Bearer {normal.data['access']}")
        response = normal_client.get(
            f"/api/product-direction/tasks/{self.task.id}/proposal/")
        self.assertEqual(response.status_code, 403)

    def test_non_proposal_statuses_do_not_fabricate_output(self):
        for state in (
            ProductDirectionTask.STATUS_SUBMITTED,
            ProductDirectionTask.STATUS_RUNNING,
            ProductDirectionTask.STATUS_BLOCKED,
        ):
            with self.subTest(state=state):
                task, _ = self.make_working_task(status=state)
                response = self.read(task)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.data, {"reason": "PROPOSAL_NOT_AVAILABLE"})

    def test_later_review_states_can_read_same_working_artifact(self):
        for state in (
            ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW,
            ProductDirectionTask.STATUS_APPROVED_INTERNAL,
            ProductDirectionTask.STATUS_REJECTED,
            ProductDirectionTask.STATUS_CHANGES_REQUESTED,
        ):
            with self.subTest(state=state):
                task, _ = self.make_working_task(status=state)
                response = self.read(task)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["knowledge_state"], "WORKING")

    def test_binding_mismatches_fail_closed(self):
        original = {
            "agent_control_task_id": self.task.agent_control_task_id,
            "proposal_artifact_id": self.task.proposal_artifact_id,
            "proposal_id": self.task.proposal_id,
            "proposal_digest": self.task.proposal_digest,
        }
        cases = (
            ("agent_control_task_id", "ATS-9999", "TASK_BINDING_MISMATCH"),
            ("proposal_artifact_id", "PROD-01-00000000-0000-4000-8000-000000000704",
             "ARTIFACT_BINDING_MISMATCH"),
            ("proposal_id", UUID("00000000-0000-4000-8000-000000000704"),
             "ARTIFACT_BINDING_MISMATCH"),
            ("proposal_digest", "b" * 64, "PROPOSAL_DIGEST_MISMATCH"),
        )
        for field, value, reason in cases:
            with self.subTest(field=field):
                setattr(self.task, field, value)
                self.task.save(update_fields=[field])
                response = self.read()
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.data, {"reason": reason})
                setattr(self.task, field, original[field])
                self.task.save(update_fields=[field])

    def test_tampered_and_malformed_artifacts_fail_without_content(self):
        original = self.artifact_path.read_bytes()
        self.artifact_path.write_bytes(original[:-1] + b"x\n")
        tampered = self.read()
        self.assertEqual(tampered.status_code, 409)
        self.assertEqual(tampered.data, {"reason": "ARTIFACT_INVALID"})

        self.artifact_path.write_bytes(b"not-json\n")
        malformed = self.read()
        self.assertEqual(malformed.status_code, 409)
        self.assertEqual(malformed.data, {"reason": "ARTIFACT_INVALID"})

    def test_missing_artifact_is_bounded_and_read_has_no_side_effects(self):
        self.artifact_path.unlink()
        with patch("tools.agent_control.prod_first_live.run_first_live") as live:
            response = self.read()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data, {"reason": "ARTIFACT_MISSING"})
        live.assert_not_called()
