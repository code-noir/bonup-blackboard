import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from tools.agent_control.founder_session import FounderSessions
from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_review_adapter import ProductionProductReviewAdapter
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.prod_review import ProductReviewRecord as SyntheticReviewRecord

from backend.bonup.models import ProductDirectionTask
from .test_product_direction import make_administrator, make_verified_user


BOOT = "00000000-0000-4000-8000-000000000001"

try:
    from tools.agent_control.founder_crypto import FounderRoot
    FounderRoot(
        "synthetic-only",
        bytes.fromhex("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"),
        1,
    )
    FOUNDER_FIXTURE_AVAILABLE = True
except Exception:
    FOUNDER_FIXTURE_AVAILABLE = False


def working_proposal(task_id, proposal_id):
    return {
        "agent_id": "PROD-01",
        "task_id": task_id,
        "proposal_id": proposal_id,
        "predecessor_proposal_id": None,
        "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
        "title": "Validated product direction",
        "problem_user_need": "The operator needs to review one exact proposal.",
        "objective": "Review one bounded product direction.",
        "proposed_requirement": "The product should support Founder review.",
        "acceptance_intent": ["The exact proposal is reviewed."],
        "dependencies": [],
        "assumptions": ["Founder runtime is trusted."],
        "risks_open_questions": ["Provisioning remains separate."],
        "priority_recommendation": "P2",
        "evidence_references": [],
        "knowledge_state": "WORKING",
    }


def make_signature(message):
    # Test-only RFC 8032 public vector signer; never used by production code.
    seed = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    from tools.agent_control.founder_crypto import sealed
    import os
    import subprocess

    key = sealed(bytes.fromhex("302e020100300506032b657004220420") + seed)
    data = sealed(message)
    try:
        result = subprocess.run(
            ("/usr/bin/openssl", "pkeyutl", "-sign", "-rawin", "-keyform", "DER",
             "-inkey", f"/proc/self/fd/{key}", "-in", f"/proc/self/fd/{data}"),
            pass_fds=(key, data), close_fds=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2,
            env={"LANG": "C", "OPENSSL_CONF": "/dev/null"}, check=True,
        )
        return result.stdout
    finally:
        os.close(data)
        os.close(key)


class TrustedFounderFixture:
    """Test-only bridge using the existing FounderSessions and adapter."""

    available = True

    def __init__(self, store):
        self.store = store
        self.registry = None
        self.binding = None
        self.challenge = None
        self.sessions = FounderSessions(
            FounderRoot(
                "synthetic-only",
                bytes.fromhex("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"),
                1,
            ),
            observe=lambda: (
                PeerIdentity(1000, 1000, 1234),
                ProcessIdentity(BOOT, 1234, 42),
            ),
            audit=lambda *args: None,
        )

    def attach_registry(self, registry):
        self.registry = registry

    def request_challenge(self, binding):
        self.binding = binding
        self.challenge = self.sessions.issue_product_review(binding)

    def submit_signature(self, *, task_id, signature):
        session = self.sessions.submit({
            "challenge_id": digest(self.challenge),
            "signature": signature,
        })
        return ProductionProductReviewAdapter(
            self.store, self.sessions, self.registry,
        ).review(self.binding, session=session, operation_id=str(uuid4()))


class ProductDirectionReviewAPITests(TestCase):
    def setUp(self):
        self.administrator = make_administrator(email="review-admin@bonup.cloud")
        self.client = APIClient()
        response = self.client.post(
            "/api/operator/auth/token/",
            {"email": self.administrator.email, "password": "adminpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.directory = TemporaryDirectory(prefix="bonup-review-", dir="/tmp")
        self.store = ProposalArtifactStore(self.directory.name)
        # The test runner may provide a /tmp/.git marker. Production registry
        # storage keeps its normal repository-exclusion check; this fixture's
        # explicit temporary paths are the controlled test boundary.
        with patch("tools.agent_control.registry.external_path", lambda value: Path(value).absolute()), patch(
            "tools.agent_control.storage.external_path", lambda value: Path(value).absolute()
        ), patch(
            "tools.agent_control.publication.external_path", lambda value: Path(value).absolute()
        ):
            self.registry = Registry.initialize(
                Path(self.directory.name) / "state.sqlite3",
                Path(self.directory.name) / "history.git",
                operation_id=str(uuid4()),
            )
        migrate_v2(self.registry)
        self.runtime = None
        self.addCleanup(self.registry.close)
        self.addCleanup(self.directory.cleanup)

    def make_task(self, status=ProductDirectionTask.STATUS_WORKING_PROPOSAL):
        application_id = uuid4()
        agent_task_id = f"ATS-{application_id.int}"
        proposal = working_proposal(agent_task_id, str(uuid4()))
        artifact = self.store.persist(proposal, source_checkpoint="a" * 40)
        task = ProductDirectionTask.objects.create(
            id=application_id,
            agent_control_task_id=agent_task_id,
            objective=proposal["objective"],
            status=status,
            proposal_artifact_id=artifact.artifact_id,
            proposal_id=UUID(proposal["proposal_id"]),
            proposal_digest=artifact.value["proposal_digest"],
            created_by=self.administrator,
        )
        return task

    def patch_runtime(self):
        if self.runtime is None:
            self.runtime = TrustedFounderFixture(self.store)
            self.runtime.attach_registry(self.registry)
        return patch(
            "backend.api.product_direction.review.get_founder_review_runtime",
            return_value=self.runtime,
        )

    def test_default_runtime_fails_closed_and_operator_cannot_override_bindings(self):
        task = self.make_task()
        availability = self.client.get(
            f"/api/product-direction/tasks/{task.id}/review/availability/"
        )
        self.assertEqual(availability.status_code, 200)
        self.assertEqual(availability.data, {
            "available": False,
            "reason": "FOUNDER_RUNTIME_UNAVAILABLE",
        })
        response = self.client.post(
            f"/api/product-direction/tasks/{task.id}/review/challenge/",
            {
                "decision": "ACCEPT",
                "reason": "Approve exact proposal.",
                "artifact_id": "caller-selected",
                "proposal_id": str(uuid4()),
                "proposal_digest": "b" * 64,
                "task_id": "ATS-9999",
                "purpose": "FOUNDER_INSTALLATION_APPROVAL",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        task.refresh_from_db()
        self.assertEqual(task.status, ProductDirectionTask.STATUS_WORKING_PROPOSAL)

    def test_unauthenticated_and_normal_user_are_rejected(self):
        task = self.make_task()
        unauthenticated = APIClient().post(
            f"/api/product-direction/tasks/{task.id}/review/challenge/",
            {"decision": "ACCEPT", "reason": "Approve."},
            format="json",
        )
        self.assertEqual(unauthenticated.status_code, 401)
        user = make_verified_user("review-normal", "review-normal@example.com")
        token = APIClient().post(
            "/api/auth/token/", {"username": user.email, "password": "userpass123"}, format="json"
        )
        normal = APIClient()
        normal.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        response = normal.post(
            f"/api/product-direction/tasks/{task.id}/review/challenge/",
            {"decision": "ACCEPT", "reason": "Approve."},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    @unittest.skipUnless(FOUNDER_FIXTURE_AVAILABLE, "trusted Founder fixture unavailable in this environment")
    def test_authenticated_accept_binds_review_and_updates_after_durable_record(self):
        task = self.make_task()
        with self.patch_runtime(), patch(
            "backend.api.product_direction.proposal.get_proposal_artifact_store",
            return_value=self.store,
        ):
            challenge = self.client.post(
                f"/api/product-direction/tasks/{task.id}/review/challenge/",
                {"decision": "ACCEPT", "reason": "Approve exact proposal."},
                format="json",
            )
            self.assertEqual(challenge.status_code, 202)
            self.assertEqual(challenge.data["proposal_id"], str(task.proposal_id))
            self.assertNotIn("challenge", challenge.data)
            result = self.client.post(
                f"/api/product-direction/tasks/{task.id}/review/submit/",
                {"signature": base64.b64encode(make_signature(canonical_json(self.runtime.challenge).encode())).decode()},
                format="json",
            )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["decision"], "ACCEPT")
        self.assertEqual(result.data["resulting_knowledge_state"], "APPROVED_INTERNAL")
        self.assertNotIn("signature", result.data)
        self.assertNotIn("authentication", result.data)
        task.refresh_from_db()
        self.assertEqual(task.status, ProductDirectionTask.STATUS_APPROVED_INTERNAL)
        self.assertEqual(task.review_id, UUID(result.data["review_id"]))
        self.assertEqual(task.review_digest, result.data["review_digest"])
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 1)

    @unittest.skipUnless(FOUNDER_FIXTURE_AVAILABLE, "trusted Founder fixture unavailable in this environment")
    def test_duplicate_signature_is_rejected_without_second_record(self):
        task = self.make_task()
        with self.patch_runtime(), patch(
            "backend.api.product_direction.proposal.get_proposal_artifact_store",
            return_value=self.store,
        ):
            self.client.post(
                f"/api/product-direction/tasks/{task.id}/review/challenge/",
                {"decision": "REJECT", "reason": "Reject exact proposal."}, format="json"
            )
            signature = base64.b64encode(make_signature(canonical_json(self.runtime.challenge).encode())).decode()
            first = self.client.post(
                f"/api/product-direction/tasks/{task.id}/review/submit/", {"signature": signature}, format="json"
            )
            second = self.client.post(
                f"/api/product-direction/tasks/{task.id}/review/submit/", {"signature": signature}, format="json"
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data, {"reason": "REVIEW_ALREADY_RECORDED"})
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 1)

    def test_synthetic_review_record_cannot_cross_runtime_boundary(self):
        task = self.make_task()
        runtime = type("SyntheticRuntime", (), {
            "available": True,
            "request_challenge": lambda self, binding: None,
            "submit_signature": lambda self, **kwargs: SyntheticReviewRecord("{}"),
        })()
        with patch(
            "backend.api.product_direction.review.get_founder_review_runtime",
            return_value=runtime,
        ), patch(
            "backend.api.product_direction.proposal.get_proposal_artifact_store",
            return_value=self.store,
        ):
            self.client.post(
                f"/api/product-direction/tasks/{task.id}/review/challenge/",
                {"decision": "ACCEPT", "reason": "Approve."}, format="json"
            )
            response = self.client.post(
                f"/api/product-direction/tasks/{task.id}/review/submit/",
                {"signature": base64.b64encode(b"x" * 64).decode()}, format="json"
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data, {"reason": "REVIEW_RECORD_INVALID"})
        task.refresh_from_db()
        self.assertEqual(task.status, ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW)


if __name__ == "__main__":
    import unittest
    unittest.main()
