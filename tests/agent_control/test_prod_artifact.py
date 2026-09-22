import json
import os
from pathlib import Path
import tempfile
import unittest

from prod_cycle_fixtures import DeterministicProductFake
from test_prod_cycle import synthetic_task
from tools.agent_control.prod_artifact import (
    ARTIFACT_MAX_BYTES, ProposalArtifactError, ProposalArtifactStore,
)
from tools.agent_control.prod_contract import load_contract
from tools.agent_control.prod_model_transport import ProductModelFailure, run_product_model_cycle
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import ValidationError


CHECKPOINT = "a" * 40


class _Transport:
    credential_owned = False

    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        return self.raw


class _Credentials:
    def credential(self):
        return "synthetic-not-a-credential"


def proposal(changes=None):
    value = DeterministicProductFake().propose(synthetic_task())
    value.update(changes or {})
    return value


def response_bytes(candidate=None):
    return canonical_json({
        "id": "resp_artifact_synthetic",
        "status": "completed",
        "output": [{
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": canonical_json(candidate or proposal()),
            }],
        }],
    }).encode()


class ProductArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ProposalArtifactStore(Path(self.temp.name) / "artifacts")

    def tearDown(self):
        self.temp.cleanup()

    def test_validated_proposal_persists_exact_bytes_and_digest(self):
        value = proposal()
        artifact = self.store.persist(value, source_checkpoint=CHECKPOINT)
        expected_bytes = (canonical_json(value) + "\n").encode()
        self.assertEqual(artifact.proposal_bytes, expected_bytes)
        self.assertEqual(artifact.value["proposal_digest"], digest(value))
        self.assertEqual(artifact.value["knowledge_state"], "WORKING")
        self.assertEqual(artifact.value["validation_result"], "PASS")
        self.assertEqual(os.stat(self.store.directory).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(artifact.path).st_mode & 0o777, 0o600)
        loaded = self.store.load(value["proposal_id"])
        self.assertEqual(loaded.value, artifact.value)
        self.assertEqual(loaded.proposal_bytes, expected_bytes)

    def test_malformed_changed_and_oversized_artifacts_fail_closed(self):
        value = proposal()
        artifact = self.store.persist(value, source_checkpoint=CHECKPOINT)
        path = Path(artifact.path)
        original = path.read_bytes()
        path.write_bytes(b"not-json\n")
        with self.assertRaises(ProposalArtifactError):
            self.store.load(value["proposal_id"])
        path.write_bytes(original)
        changed = json.loads(original.decode())
        changed["proposal_digest"] = "b" * 64
        path.write_bytes((canonical_json(changed) + "\n").encode())
        with self.assertRaises(ProposalArtifactError):
            self.store.load(value["proposal_id"])
        path.write_bytes(b"x" * (ARTIFACT_MAX_BYTES + 1))
        with self.assertRaises(ProposalArtifactError):
            self.store.load(value["proposal_id"])

    def test_exclusive_creation_and_symlink_rejection(self):
        value = proposal()
        self.store.persist(value, source_checkpoint=CHECKPOINT)
        with self.assertRaises(ProposalArtifactError):
            self.store.persist(value, source_checkpoint=CHECKPOINT)

        other = proposal({"proposal_id": "00000000-0000-4000-8000-000000000901"})
        filename = "proposal-" + other["proposal_id"] + ".json"
        target = Path(self.temp.name) / "outside"
        target.write_text("synthetic", encoding="utf-8")
        (Path(self.temp.name) / "artifacts").joinpath(filename).symlink_to(target)
        with self.assertRaises(ProposalArtifactError):
            self.store.persist(other, source_checkpoint=CHECKPOINT)

        symlinked_directory = Path(self.temp.name) / "linked"
        symlinked_directory.symlink_to(Path(self.temp.name), target_is_directory=True)
        with self.assertRaises(ProposalArtifactError):
            ProposalArtifactStore(symlinked_directory).persist(
                proposal({"proposal_id": "00000000-0000-4000-8000-000000000902"}),
                source_checkpoint=CHECKPOINT)

    def test_only_validated_working_proposals_persist(self):
        with self.assertRaises(ValidationError):
            self.store.persist(proposal({"title": ""}), source_checkpoint=CHECKPOINT)
        with self.assertRaises(ValidationError):
            self.store.persist(proposal({"knowledge_state": "APPROVED_INTERNAL"}),
                               source_checkpoint=CHECKPOINT)
        with self.assertRaises(ProposalArtifactError):
            self.store.persist(proposal(), source_checkpoint="not-a-checkpoint")

    def test_artifact_contains_no_provider_or_authority_material(self):
        artifact = self.store.persist(proposal(), source_checkpoint=CHECKPOINT)
        rendered = canonical_json(artifact.value)
        for forbidden in (
                "Authorization", "api_key", "provider_metadata", "reasoning",
                "execution_grant", "assignment", "activation"):
            self.assertNotIn(forbidden, rendered)
        self.assertEqual(load_contract()["status"], "NON_ACTIVE")
        self.assertEqual(load_contract()["authority_mode"], "PROPOSAL_ONLY")

    def test_loading_artifact_has_no_authority_and_persistence_failure_does_not_retry(self):
        authority = {"agents": [], "grants": [], "assignments": [], "fence": 1}
        before = dict(authority)
        value = proposal()
        artifact = self.store.persist(value, source_checkpoint=CHECKPOINT)
        loaded = self.store.load(value["proposal_id"])
        self.assertEqual(loaded.artifact_id, artifact.artifact_id)
        self.assertEqual(authority, before)

        class FailingStore:
            def persist(self, *args, **kwargs):
                raise ValidationError("synthetic persistence failure")

        transport = _Transport(response_bytes())
        with self.assertRaises(ProductModelFailure) as caught:
            run_product_model_cycle(
                synthetic_task(), transport, _Credentials(),
                proposal_artifact_store=FailingStore(), source_checkpoint=CHECKPOINT)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(
            caught.exception.audit_metadata["failure_reason"],
            "PROPOSAL_ARTIFACT_PERSISTENCE_FAILED",
        )

    def test_synthetic_founder_context_remains_non_production(self):
        from tools.agent_control.prod_review import SyntheticFounderReviewContext
        self.assertEqual(SyntheticFounderReviewContext().context_kind, "SYNTHETIC_TEST_ONLY")


if __name__ == "__main__":
    unittest.main()
