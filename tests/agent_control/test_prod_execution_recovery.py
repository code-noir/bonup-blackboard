import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import unittest
from uuid import uuid4

from tools.agent_control.prod_artifact import ProposalArtifactError, ProposalArtifactStore
from tools.agent_control.prod_application import ProductDirectionApplicationService
from tools.agent_control.prod_execution import (
    ARTIFACT_COMMITTED,
    ProdExecutionBinding,
    ProdExecutionLedger,
    ProductExecutionFailure,
    RECONCILIATION_REQUIRED,
    RESPONSE_CAPTURED,
    SEND_FENCE_COMMITTED,
)
from tools.agent_control.prod_model_transport import (
    TRUSTED_ENDPOINT,
    TRUSTED_MODEL,
    build_product_model_request,
)
from tools.agent_control.prod_runtime import (
    ProductDirectionRuntimeRequest,
    ProductRuntimeFailure,
    TrustedProd01Runtime,
    _policy_digest,
    agent_control_task_id_for,
)
from tools.agent_control.serialization import canonical_json, digest


CHECKPOINT = "a" * 40


def proposal(task_id):
    return {
        "agent_id": "PROD-01",
        "task_id": task_id,
        "proposal_id": "00000000-0000-4000-8000-000000000991",
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


class CountingTransport:
    credential_owned = True

    def __init__(self, *, delay=0):
        self.calls = []
        self.delay = delay
        self.lock = threading.Lock()

    def response(self, request_bytes):
        request = json.loads(request_bytes)
        value = proposal(request["context"]["task_id"])
        return canonical_json({
            "id": "synthetic-response",
            "status": "completed",
            "output": [{
                "type": "message", "status": "completed", "role": "assistant",
                "content": [{"type": "output_text", "text": canonical_json(value)}],
            }],
        }).encode()

    def send(self, **kwargs):
        with self.lock:
            self.calls.append(kwargs)
        if self.delay:
            time.sleep(self.delay)
        return self.response(kwargs["request"])


def request():
    application_task_id = str(uuid4())
    return ProductDirectionRuntimeRequest(
        application_task_id=application_task_id,
        agent_control_task_id=agent_control_task_id_for(application_task_id),
        agent_id="PROD-01",
        objective="Review one bounded product direction.",
    )


def binding_for(value):
    task = value.to_product_task()
    model_request, _ = build_product_model_request(task)
    return ProdExecutionBinding(
        agent_id=task["agent_id"],
        agent_control_task_id=task["task_id"],
        application_task_id=value.application_task_id,
        request_digest=digest(model_request),
        policy_digest=_policy_digest(model_request),
        source_checkpoint=CHECKPOINT,
    )


class CrashCaptureLedger(ProdExecutionLedger):
    def capture_response(self, binding, response, response_metadata=None):
        raise ProductExecutionFailure("INJECTED_AFTER_PROVIDER_RESPONSE")


class CrashAfterCaptureLedger(ProdExecutionLedger):
    def capture_response(self, binding, response, response_metadata=None):
        super().capture_response(binding, response, response_metadata)
        raise ProductExecutionFailure("INJECTED_AFTER_RESPONSE_CAPTURE")


class CrashAfterArtifactLedger(ProdExecutionLedger):
    def __init__(self, path):
        super().__init__(path)
        self.crashed = False

    def mark_artifact(self, binding, artifact_id, artifact_digest):
        if not self.crashed:
            self.crashed = True
            super().mark_artifact(binding, artifact_id, artifact_digest)
            raise ProductExecutionFailure("INJECTED_AFTER_ARTIFACT_COMMIT")
        return super().mark_artifact(binding, artifact_id, artifact_digest)


class FailOnceArtifactStore(ProposalArtifactStore):
    def __init__(self, directory):
        super().__init__(directory)
        self.failed = False

    def persist(self, proposal_value, *, source_checkpoint, logical_model=None):
        if not self.failed:
            self.failed = True
            raise ProposalArtifactError("INJECTED_BEFORE_ARTIFACT_PERSISTENCE")
        kwargs = {"source_checkpoint": source_checkpoint}
        if logical_model is not None:
            kwargs["logical_model"] = logical_model
        return super().persist(proposal_value, **kwargs)


class ProdExecutionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bonup-prod-execution-", dir="/dev/shm")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def runtime(self, transport, ledger=None, store=None):
        return TrustedProd01Runtime(
            transport,
            source_checkpoint=CHECKPOINT,
            artifact_store=store or ProposalArtifactStore(self.root / "artifacts"),
            execution_ledger=ledger or ProdExecutionLedger(self.root / "execution.sqlite3"),
        )

    def test_ready_state_can_be_recovered_without_duplicate_send(self):
        value = request()
        ledger = ProdExecutionLedger(self.root / "execution.sqlite3")
        ledger.prepare(binding_for(value))
        ledger.close()
        transport = CountingTransport()
        result = self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3")).submit(value)
        self.assertEqual(result.agent_control_task_id, value.agent_control_task_id)
        self.assertEqual(len(transport.calls), 1)

    def test_send_fence_without_response_fails_closed_without_provider_call(self):
        value = request()
        binding = binding_for(value)
        ledger = ProdExecutionLedger(self.root / "execution.sqlite3")
        ledger.prepare(binding)
        claimed, record = ledger.claim_send_fence(binding)
        self.assertTrue(claimed)
        self.assertEqual(record.state, SEND_FENCE_COMMITTED)
        transport = CountingTransport()
        with self.assertRaises(ProductRuntimeFailure) as error:
            self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3")).submit(value)
        self.assertEqual(error.exception.reason, "PROVIDER_OUTCOME_UNKNOWN")
        self.assertEqual(transport.calls, [])
        self.assertEqual(
            ProdExecutionLedger(self.root / "execution.sqlite3").get(binding).state,
            RECONCILIATION_REQUIRED,
        )

    def test_captured_response_resumes_locally_after_restart(self):
        value = request()
        binding = binding_for(value)
        transport = CountingTransport()
        ledger = ProdExecutionLedger(self.root / "execution.sqlite3")
        ledger.prepare(binding)
        ledger.claim_send_fence(binding)
        task = value.to_product_task()
        model_request, _ = build_product_model_request(task)
        ledger.capture_response(binding, transport.response(canonical_json(model_request).encode()))
        ledger.close()
        result = self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3")).submit(value)
        self.assertEqual(result.agent_control_task_id, value.agent_control_task_id)
        self.assertEqual(transport.calls, [])
        self.assertEqual(
            ProdExecutionLedger(self.root / "execution.sqlite3").get(binding).state,
            ARTIFACT_COMMITTED,
        )

    def test_crash_after_provider_response_enters_reconciliation_without_retry(self):
        value = request()
        transport = CountingTransport()
        first = self.runtime(
            transport, CrashCaptureLedger(self.root / "execution.sqlite3"))
        with self.assertRaises(ProductRuntimeFailure) as error:
            first.submit(value)
        self.assertEqual(error.exception.reason, "PROVIDER_OUTCOME_UNKNOWN")
        second = self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3"))
        with self.assertRaises(ProductRuntimeFailure) as error:
            second.submit(value)
        self.assertEqual(error.exception.reason, "PROVIDER_OUTCOME_UNKNOWN")
        self.assertEqual(len(transport.calls), 1)

    def test_crash_after_capture_resumes_without_second_provider_call(self):
        value = request()
        transport = CountingTransport()
        first = self.runtime(
            transport, CrashAfterCaptureLedger(self.root / "execution.sqlite3"))
        with self.assertRaises(ProductRuntimeFailure):
            first.submit(value)
        result = self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3")).submit(value)
        self.assertEqual(result.agent_control_task_id, value.agent_control_task_id)
        self.assertEqual(len(transport.calls), 1)

    def test_crash_before_artifact_persistence_resumes_locally(self):
        value = request()
        transport = CountingTransport()
        store = FailOnceArtifactStore(self.root / "artifacts")
        first = self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3"), store)
        with self.assertRaises(ProductRuntimeFailure) as error:
            first.submit(value)
        self.assertEqual(error.exception.reason, "PROPOSAL_ARTIFACT_PERSISTENCE_FAILED")
        result = self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3"), store).submit(value)
        self.assertEqual(result.agent_control_task_id, value.agent_control_task_id)
        self.assertEqual(len(transport.calls), 1)

    def test_crash_after_artifact_creation_finalizes_without_retry(self):
        value = request()
        transport = CountingTransport()
        first = self.runtime(
            transport, CrashAfterArtifactLedger(self.root / "execution.sqlite3"))
        with self.assertRaises(ProductRuntimeFailure):
            first.submit(value)
        result = self.runtime(transport, ProdExecutionLedger(self.root / "execution.sqlite3")).submit(value)
        self.assertEqual(result.agent_control_task_id, value.agent_control_task_id)
        self.assertEqual(len(transport.calls), 1)

    def test_concurrent_submissions_have_one_send_fence_and_one_provider_call(self):
        value = request()
        transport = CountingTransport(delay=0.05)
        ledger_path = self.root / "execution.sqlite3"
        store = ProposalArtifactStore(self.root / "artifacts")
        runtime = self.runtime(transport, ProdExecutionLedger(ledger_path), store)
        service = ProductDirectionApplicationService(runtime, artifact_store=store)
        payload = {
            "application_task_id": value.application_task_id,
            "agent_control_task_id": value.agent_control_task_id,
            "agent_id": value.agent_id,
            "objective": value.objective,
        }
        results = []

        def submit():
            try:
                results.append(service.handle("SUBMIT_PRODUCT_DIRECTION", payload))
            except Exception as error:
                results.append(error)

        threads = [threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])

    def test_binding_conflict_is_rejected(self):
        value = request()
        binding = binding_for(value)
        ledger = ProdExecutionLedger(self.root / "execution.sqlite3")
        ledger.prepare(binding)
        conflict = ProdExecutionBinding(
            agent_id=binding.agent_id,
            agent_control_task_id=binding.agent_control_task_id,
            application_task_id=binding.application_task_id,
            request_digest="b" * 64,
            policy_digest=binding.policy_digest,
            source_checkpoint=binding.source_checkpoint,
        )
        with self.assertRaises(ProductExecutionFailure) as error:
            ledger.prepare(conflict)
        self.assertEqual(error.exception.reason, "EXECUTION_BINDING_CONFLICT")

    def test_tampered_response_capture_is_rejected(self):
        value = request()
        binding = binding_for(value)
        ledger = ProdExecutionLedger(self.root / "execution.sqlite3")
        ledger.prepare(binding)
        ledger.claim_send_fence(binding)
        ledger.capture_response(binding, b"captured-response")
        ledger.db.execute(
            "UPDATE prod01_executions SET response_bytes=? WHERE execution_key=?",
            (b"tampered-response", binding.execution_key),
        )
        ledger.db.commit()
        with self.assertRaises(ProductExecutionFailure) as error:
            ledger.get(binding)
        self.assertEqual(error.exception.reason, "RESPONSE_CAPTURE_TAMPERED")

    def test_response_capture_rejects_authorization_metadata_and_persists_no_secret(self):
        value = request()
        binding = binding_for(value)
        ledger = ProdExecutionLedger(self.root / "execution.sqlite3")
        ledger.prepare(binding)
        ledger.claim_send_fence(binding)
        with self.assertRaises(ProductExecutionFailure) as error:
            ledger.capture_response(
                binding, b"provider-response", {"Authorization": "Bearer secret"})
        self.assertEqual(error.exception.reason, "RESPONSE_METADATA_INVALID")
        rows = ledger.db.execute(
            "SELECT binding_json,response_bytes,response_metadata FROM prod01_executions").fetchall()
        self.assertNotIn(b"secret", repr(rows).encode())
        self.assertEqual(stat.S_IMODE(os.stat(self.root / "execution.sqlite3").st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
