from contextlib import redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures import task_data
from tools.agent_control.records import Task, task_spec_digest
from tools.agent_control.task_document_project import main, project_task_document
from tools.agent_control.types import ValidationError


class FakeRegistry:
    def __init__(self, task, evidence=None):
        self.task = task
        self.evidence = evidence or {}
        self.loads = []
        self.grants = []

    def get_task(self, task_id):
        if task_id != self.task["task_id"]:
            raise ValidationError("Unknown task.")
        return self.task

    def load(self, kind, record_id):
        self.loads.append((kind, record_id))
        if kind != "TestEvidence" or record_id not in self.evidence:
            raise ValidationError("Unknown control record.")
        return self.evidence[record_id]


class EvidenceStub:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        return self.data[key]

    def to_dict(self):
        return dict(self.data)


def synthetic_task(state="PROPOSED", **changes):
    data = task_data(state)
    data.update(changes)
    data["spec_digest"] = task_spec_digest(data)
    return Task(data)


class TaskDocumentProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bonup-task-doc-", dir="/tmp")
        self.root = Path(self.temp.name)
        self.documents = self.root / "docs" / "agent-tasks"

    def tearDown(self):
        self.temp.cleanup()

    def test_successful_authoritative_projection_is_deterministic_and_read_only(self):
        task = synthetic_task(objective="Trusted objective", acceptance_criteria=["Render safely"])
        registry = FakeRegistry(task)
        before = task.canonical_json()
        first = project_task_document(registry, task["task_id"], document_root=self.documents)
        content = (self.documents / f"{task['task_id']}.md").read_bytes()
        second = project_task_document(registry, task["task_id"], document_root=self.documents)
        self.assertEqual(first["status"], "WRITTEN")
        self.assertEqual(second["status"], "UNCHANGED")
        self.assertEqual(content, (self.documents / f"{task['task_id']}.md").read_bytes())
        self.assertIn(b"HUMAN-READABLE PROJECTION", content)
        self.assertIn(b"NOT EXECUTION AUTHORITY", content)
        self.assertEqual(registry.get_task(task["task_id"]).canonical_json(), before)
        self.assertEqual(registry.grants, [])

    def test_unknown_and_traversal_task_ids_are_rejected_without_output(self):
        registry = FakeRegistry(synthetic_task())
        with self.assertRaises(ValidationError):
            project_task_document(registry, "ATS-9999", document_root=self.documents)
        for unsafe in ("../ATS-0001", "/ATS-0001", "ATS-0001/other", "ATS-1"):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValidationError):
                project_task_document(registry, unsafe, document_root=self.documents)
        self.assertFalse(self.documents.exists())

    def test_caller_cannot_override_agent_status_authority_or_result(self):
        for option in ("--agent", "--status", "--grant", "--result", "--spec-digest"):
            with self.subTest(option=option), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--state", "/synthetic/state", "--task-id", "ATS-0001", option, "forged"])

    def test_invalid_evidence_and_secret_content_fail_without_partial_document(self):
        missing = "00000000-0000-4000-8000-000000000077"
        task = synthetic_task(validation_results=[missing])
        with self.assertRaises(ValidationError):
            project_task_document(FakeRegistry(task), task["task_id"], document_root=self.documents)
        self.assertFalse((self.documents / f"{task['task_id']}.md").exists())

        wrong = EvidenceStub({"task_id": "ATS-9999", "spec_digest": task["spec_digest"]})
        with self.assertRaises(ValidationError):
            project_task_document(FakeRegistry(task, {missing: wrong}), task["task_id"],
                                  document_root=self.documents)
        self.assertFalse((self.documents / f"{task['task_id']}.md").exists())

        secret = synthetic_task(objective="API_KEY=synthetic-secret-value")
        with self.assertRaises(ValidationError):
            project_task_document(FakeRegistry(secret), secret["task_id"], document_root=self.documents)
        self.assertFalse((self.documents / f"{secret['task_id']}.md").exists())

    def test_safe_path_symlink_and_stale_overwrite_protection(self):
        task = synthetic_task(record_revision=2)
        registry = FakeRegistry(task)
        project_task_document(registry, task["task_id"], document_root=self.documents)
        destination = self.documents / f"{task['task_id']}.md"
        newer = destination.read_bytes()

        stale = synthetic_task(record_revision=1)
        with self.assertRaises(ValidationError):
            project_task_document(FakeRegistry(stale), stale["task_id"], document_root=self.documents)
        self.assertEqual(destination.read_bytes(), newer)

        other_root = self.root / "linked"
        other_root.symlink_to(self.documents, target_is_directory=True)
        with self.assertRaises(ValidationError):
            project_task_document(registry, task["task_id"], document_root=other_root)

    def test_atomic_write_failure_leaves_no_partial_document(self):
        task = synthetic_task()
        with patch("tools.agent_control.task_document_project.os.replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                project_task_document(FakeRegistry(task), task["task_id"], document_root=self.documents)
        self.assertFalse((self.documents / f"{task['task_id']}.md").exists())
        self.assertEqual(list(self.documents.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
