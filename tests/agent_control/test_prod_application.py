import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from tools.agent_control.founder_review_auth import ProductProposalReviewBinding
from tools.agent_control.prod_application import (
    ProductDirectionApplicationClient,
    ProductDirectionApplicationService,
)
from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_execution import ProdExecutionLedger
from tools.agent_control.prod_runtime import (
    ProductDirectionRuntimeRequest,
    TrustedProd01Runtime,
    agent_control_task_id_for,
)
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import AuthorityError, ValidationError


CHECKPOINT = "a" * 40


def proposal(task_id, proposal_id):
    return {
        "agent_id": "PROD-01",
        "task_id": task_id,
        "proposal_id": proposal_id,
        "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
        "title": "Bounded product direction",
        "problem_user_need": "A bounded product direction needs review.",
        "objective": "Review one bounded product direction.",
        "proposed_requirement": "The product should expose the validated direction.",
        "acceptance_intent": ["The exact direction is visible."],
        "dependencies": [],
        "assumptions": [],
        "risks_open_questions": [],
        "priority_recommendation": "P2",
        "evidence_references": [],
        "knowledge_state": "WORKING",
        "predecessor_proposal_id": None,
    }


class ModelTransport:
    credential_owned = True

    def __init__(self):
        self.calls = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        request = json.loads(kwargs["request"])
        task = request["context"]
        value = proposal(task["task_id"], "00000000-0000-4000-8000-000000000901")
        return canonical_json({
            "id": "synthetic-response",
            "status": "completed",
            "output": [{
                "type": "message", "status": "completed", "role": "assistant",
                "content": [{"type": "output_text", "text": canonical_json(value)}],
            }],
        }).encode()


class FounderBoundary:
    trusted_agent_control_boundary = True

    def __init__(self):
        self.bindings = []

    def request_product_review(self, binding, proposal_projection, *, operation_id):
        self.bindings.append((binding, operation_id))
        return {"status": "REQUESTED"}

    def observe_product_review(self, task_id):
        return None


class InProcessTransport:
    trusted_agent_control_transport = True

    def __init__(self, service):
        self.service = service
        self.calls = []

    def exchange(self, operation, payload):
        self.calls.append((operation, payload))
        return self.service.handle(operation, payload)


class ProductApplicationTests(unittest.TestCase):
    def _service(self, directory, model):
        root = Path(directory)
        store = ProposalArtifactStore(root / "artifacts")
        return ProductDirectionApplicationService(
            TrustedProd01Runtime(
                model, source_checkpoint=CHECKPOINT, artifact_store=store,
                execution_ledger=ProdExecutionLedger(root / "execution.sqlite3"),
            ),
            artifact_store=store,
            founder_boundary=FounderBoundary(),
        )

    def test_composed_application_client_uses_fixed_agent_control_contract(self):
        application_id = str(uuid4())
        task_id = agent_control_task_id_for(application_id)
        model = ModelTransport()
        founder = FounderBoundary()
        app_transport = None
        with TemporaryDirectory(prefix="bonup-prod-application-", dir="/dev/shm") as directory:
            root = Path(directory)
            store = ProposalArtifactStore(root / "artifacts")
            service = ProductDirectionApplicationService(
                TrustedProd01Runtime(
                    model, source_checkpoint=CHECKPOINT, artifact_store=store,
                    execution_ledger=ProdExecutionLedger(root / "execution.sqlite3"),
                ),
                artifact_store=store,
                founder_boundary=founder,
            )
            app_transport = InProcessTransport(service)
            client = ProductDirectionApplicationClient(app_transport)
            result = client.submit(ProductDirectionRuntimeRequest(
                application_task_id=application_id,
                agent_control_task_id=task_id,
                agent_id="PROD-01",
                objective="Review one bounded product direction.",
            ))
            projection = client.read_proposal(
                application_task_id=application_id,
                agent_control_task_id=task_id,
                proposal_artifact_id=result.proposal_artifact_id,
                proposal_id=result.proposal_id,
                proposal_digest=result.proposal_digest,
            )
            binding = ProductProposalReviewBinding.from_dict({
                "binding_version": 1,
                "purpose": "PROD_PROPOSAL_REVIEW",
                "artifact_id": projection["artifact_id"],
                "artifact_digest": projection["artifact_digest"],
                "task_id": projection["agent_control_task_id"],
                "proposal_id": projection["proposal_id"],
                "proposal_digest": projection["proposal_digest"],
                "decision": "ACCEPT",
                "reason": "Approve the exact bounded proposal.",
            })
            review = client.request_founder_review(binding)

        self.assertEqual(review["status"], "REQUESTED")
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(founder.bindings), 1)
        request = model.calls[0]
        self.assertIsNone(request["credential"])
        self.assertNotIn("credential", request["request"].decode().lower())
        application_payload = app_transport.calls[0][1]
        self.assertNotIn("model", application_payload)
        self.assertNotIn("endpoint", application_payload)
        self.assertNotIn("credential", application_payload)
        self.assertNotIn("tools", application_payload)
        self.assertNotIn("retries", application_payload)
        self.assertNotIn("path", projection)
        self.assertNotIn("source_checkpoint", projection)

    def test_application_service_rejects_runtime_controls_and_wrong_task_binding(self):
        model = ModelTransport()
        with TemporaryDirectory(prefix="bonup-prod-application-", dir="/dev/shm") as directory:
            root = Path(directory)
            store = ProposalArtifactStore(root / "artifacts")
            service = ProductDirectionApplicationService(
                TrustedProd01Runtime(
                    model, source_checkpoint=CHECKPOINT, artifact_store=store,
                    execution_ledger=ProdExecutionLedger(root / "execution.sqlite3"),
                ),
                artifact_store=store,
                founder_boundary=FounderBoundary(),
            )
            with self.assertRaises((AuthorityError, ValidationError)):
                service.handle("SUBMIT_PRODUCT_DIRECTION", {
                    "application_task_id": str(uuid4()),
                    "agent_control_task_id": "ATS-1234",
                    "agent_id": "PROD-01",
                    "objective": "Bounded objective.",
                    "model": "caller-selected",
                })
            with self.assertRaises((AuthorityError, ValidationError)):
                service.handle("READ_PROPOSAL", {
                    "application_task_id": str(uuid4()),
                    "agent_control_task_id": "ATS-1234",
                    "proposal_artifact_id": "PROD-01-00000000-0000-4000-8000-000000000901",
                    "proposal_id": "00000000-0000-4000-8000-000000000901",
                    "proposal_digest": "a" * 64,
                })

    def test_duplicate_and_restart_submit_recover_one_committed_artifact(self):
        application_id = str(uuid4())
        task_id = agent_control_task_id_for(application_id)
        request = {
            "application_task_id": application_id,
            "agent_control_task_id": task_id,
            "agent_id": "PROD-01",
            "objective": "Bounded objective.",
        }
        with TemporaryDirectory(prefix="bonup-prod-recovery-", dir="/dev/shm") as directory:
            first_model = ModelTransport()
            first = self._service(directory, first_model)
            first_result = first.handle("SUBMIT_PRODUCT_DIRECTION", request)
            duplicate_result = first.handle("SUBMIT_PRODUCT_DIRECTION", request)

            restarted_model = ModelTransport()
            restarted = self._service(directory, restarted_model)
            recovered_result = restarted.handle("SUBMIT_PRODUCT_DIRECTION", request)

        self.assertEqual(first_result, duplicate_result)
        self.assertEqual(first_result, recovered_result)
        self.assertEqual(len(first_model.calls), 1)
        self.assertEqual(len(restarted_model.calls), 0)

    def test_founder_status_is_unavailable_without_founder_composition(self):
        model = ModelTransport()
        with TemporaryDirectory(prefix="bonup-prod-founder-status-", dir="/dev/shm") as directory:
            root = Path(directory)
            store = ProposalArtifactStore(root / "artifacts")
            service = ProductDirectionApplicationService(
                TrustedProd01Runtime(
                    model, source_checkpoint=CHECKPOINT, artifact_store=store,
                    execution_ledger=ProdExecutionLedger(root / "execution.sqlite3"),
                ),
                artifact_store=store,
            )
            self.assertEqual(
                service.handle("FOUNDER_REVIEW_STATUS", {}), {"available": False})
if __name__ == "__main__":
    unittest.main()
