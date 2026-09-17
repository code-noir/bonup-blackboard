import unittest

from fixtures import task_data
from tools.agent_control.records import Task
from tools.agent_control.task_document import render_task_document
from tools.agent_control.types import ValidationError


def summary():
    return {
        "background": "Provide a contractor-readable projection of trusted records.",
        "inputs": ["Founder-approved ATS"],
        "plan": ["Render bounded Markdown"],
        "work_performed": ["Added the projection contract"],
        "artifacts": ["tools/agent_control/task_document.py"],
        "validation": ["Focused unit tests passed"],
        "result": "Reusable task documentation is available.",
        "evidence_references": [{"kind": "TEST_EVIDENCE", "identifier": "evidence-1",
                                 "digest": "a" * 64, "path": "evidence/one.json"}],
        "started_at": "2026-09-11T00:00:00Z",
        "completed_at": None,
    }


class TaskDocumentTests(unittest.TestCase):
    def test_render_is_deterministic_and_binds_identity_agent_content_and_evidence(self):
        task = Task(task_data("IN_PROGRESS"))
        first = render_task_document(task, summary())
        self.assertEqual(first, render_task_document(task, summary()))
        for expected in (task["task_id"], task["task_uuid"], task["spec_digest"],
                         "FE-01", task["objective"], summary()["result"],
                         "evidence-1", "IN_PROGRESS"):
            self.assertIn(expected, first)

    def test_projection_cannot_supply_authority_or_change_task(self):
        task = Task(task_data("IN_PROGRESS"))
        before = task.canonical_json()
        for field in ("state", "grants", "can_write", "agent_id"):
            value = summary()
            value[field] = "CLOSED"
            with self.subTest(field=field), self.assertRaises(ValidationError):
                render_task_document(task, value)
        self.assertEqual(task.canonical_json(), before)
        with self.assertRaises(ValidationError):
            render_task_document(task.to_dict(), summary())

    def test_status_maps_existing_lifecycle_without_replacing_it(self):
        cases = {"PROPOSED": "CREATED", "BLOCKED": "BLOCKED",
                 "CLOSED": "COMPLETED", "ABANDONED": "FAILED"}
        for state, projected in cases.items():
            with self.subTest(state=state):
                rendered = render_task_document(Task(task_data(state)), summary())
                self.assertIn(f'"authoritative_state":"{state}"', rendered)
                self.assertIn(f'"document_status":"{projected}"', rendered)

    def test_secrets_and_raw_environment_are_rejected(self):
        values = ("API_KEY=not-safe-to-copy", "password: exposed-value",
                  "-----BEGIN PRIVATE KEY-----")
        for unsafe in values:
            value = summary()
            value["result"] = unsafe
            with self.subTest(unsafe=unsafe), self.assertRaises(ValidationError):
                render_task_document(Task(task_data()), value)

    def test_malformed_and_unbounded_fields_are_rejected(self):
        bad = []
        value = summary(); value["plan"] = ["x"] * 101; bad.append(value)
        value = summary(); value["result"] = "x" * 4097; bad.append(value)
        value = summary(); value["evidence_references"][0]["digest"] = "bad"; bad.append(value)
        value = summary(); value["evidence_references"][0]["extra"] = "bad"; bad.append(value)
        value = summary(); value["completed_at"] = "2026-09-10T00:00:00Z"; bad.append(value)
        for index, value in enumerate(bad):
            with self.subTest(index=index), self.assertRaises(ValidationError):
                render_task_document(Task(task_data()), value)


if __name__ == "__main__":
    unittest.main()
