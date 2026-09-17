import os
import socket
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from prod_cycle_fixtures import DeterministicProductFake
from tools.agent_control.prod_contract import load_contract, validate_product_proposal
from tools.agent_control.prod_cycle import run_synthetic_product_cycle
from tools.agent_control.types import ValidationError


def synthetic_task():
    return {
        "agent_id": "PROD-01",
        "task_id": "ATS-0701",
        "task_class": "PRODUCT_REQUIREMENT",
        "objective": "Define the product requirements for displaying agent task history in the bonUP interface.",
        "input_references": [{
            "reference_type": "FOUNDER_DIRECTION",
            "reference_id": "FOUNDER-DIRECTION-0701",
            "digest": "7" * 64,
            "knowledge_state": "DIRECT_FOUNDER",
        }],
    }


class ProductCycleTests(unittest.TestCase):
    def test_success_is_deterministic_validated_and_documented(self):
        first = run_synthetic_product_cycle(synthetic_task(), DeterministicProductFake())
        second = run_synthetic_product_cycle(synthetic_task(), DeterministicProductFake())
        self.assertEqual(first.proposal_bytes, second.proposal_bytes)
        self.assertEqual(first.proposal_digest, second.proposal_digest)
        self.assertEqual(first.task_document_bytes, second.task_document_bytes)
        self.assertEqual(validate_product_proposal(first.proposal), first.proposal)
        for expected in (b"Agent:** PROD-01", b"SYNTHETIC_PROPOSAL_VALIDATED",
                         b"HUMAN-READABLE PROJECTION", b"NOT EXECUTION AUTHORITY",
                         b"Proposal Artifact", b"Evidence References", b"Result"):
            self.assertIn(expected, first.task_document_bytes)
        with tempfile.TemporaryDirectory(prefix="prod-cycle-", dir="/tmp") as directory:
            proposal_path = Path(directory) / "proposal.json"
            document_path = Path(directory) / "task-document.md"
            proposal_path.write_bytes(first.proposal_bytes)
            document_path.write_bytes(first.task_document_bytes)
            self.assertEqual(proposal_path.read_bytes(), first.proposal_bytes)
            self.assertEqual(document_path.read_bytes(), first.task_document_bytes)

    def test_authority_seeking_and_unknown_outputs_are_denied(self):
        changes = (
            {"proposal_type": "EXECUTION_GRANT"}, {"approved": True},
            {"execution_grant": "grant"}, {"deployment": True},
            {"assignment": "ARCH-01"}, {"command": "run"},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                run_synthetic_product_cycle(synthetic_task(), DeterministicProductFake(change))

    def test_knowledge_self_promotion_is_denied(self):
        for state in ("APPROVED_INTERNAL", "PUBLICATION_ELIGIBLE"):
            with self.subTest(state=state), self.assertRaises(ValidationError):
                run_synthetic_product_cycle(
                    synthetic_task(), DeterministicProductFake({"knowledge_state": state}))

    def test_secrets_claims_and_unbounded_output_are_denied(self):
        changes = (
            {"credentials": "secret"},
            {"proposed_requirement": "API_KEY=synthetic-secret"},
            {"proposed_requirement": "This requirement is approved."},
            {"proposed_requirement": "x" * 4097},
        )
        for change in changes:
            with self.subTest(change=list(change)), self.assertRaises(ValidationError):
                run_synthetic_product_cycle(synthetic_task(), DeterministicProductFake(change))

    def test_cycle_has_no_registry_authority_or_side_effect_adapter(self):
        invalid = DeterministicProductFake()
        invalid.adapter_kind = "REAL_MODEL"
        with self.assertRaises(ValidationError):
            run_synthetic_product_cycle(synthetic_task(), invalid)
        with (patch.object(subprocess, "Popen") as popen,
              patch.object(os, "system") as system,
              patch.object(socket, "socket") as network):
            task = synthetic_task()
            task_before = deepcopy(task)
            authoritative_state = {"agents": [], "grants": [], "reservations": [],
                                   "fencing_epoch": 1, "task_state": "PROPOSED"}
            authority_before = deepcopy(authoritative_state)
            run_synthetic_product_cycle(task, DeterministicProductFake())
            popen.assert_not_called(); system.assert_not_called(); network.assert_not_called()
            self.assertEqual(task, task_before)
            self.assertEqual(authoritative_state, authority_before)

    def test_prod_remains_non_active_and_proposal_only(self):
        contract = load_contract()
        self.assertEqual(contract["status"], "NON_ACTIVE")
        self.assertEqual(contract["authority_mode"], "PROPOSAL_ONLY")
        self.assertTrue(all(value is False for value in contract["permissions"].values()))


if __name__ == "__main__":
    unittest.main()
