import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from backend.contracts.schema import SCHEMA_VERSION
from backend.contracts.snapshot_adapter import normalize_content_snapshot


class SnapshotAdapterTests(SimpleTestCase):
    def test_none_snapshot_returns_empty_canonical_schema(self):
        schema = normalize_content_snapshot(None)

        self.assertEqual(schema["schema_version"], SCHEMA_VERSION)
        self.assertEqual(schema["clauses"], [])
        self.assertIn("content_snapshot is empty.", schema["extraction_report"]["warnings"])

    def test_raw_plain_text_becomes_schema_with_clause(self):
        schema = normalize_content_snapshot("This agreement requires payment within 30 days.")

        self.assertEqual(len(schema["clauses"]), 1)
        self.assertEqual(schema["clauses"][0]["clause_type"], "payment")
        self.assertIn("payment", schema["clauses"][0]["body"].lower())

    def test_editor_html_snapshot_preserves_render_cache(self):
        snapshot = {
            "editor_html": "<h2>1. Payment</h2><p>Client shall pay $500.</p>",
        }

        schema = normalize_content_snapshot(json.dumps(snapshot))

        self.assertEqual(schema["render_cache"]["editor_html"], snapshot["editor_html"])
        self.assertEqual(len(schema["clauses"]), 1)
        self.assertIn("editor_html", schema["extraction_report"]["source_types"])

    def test_final_editor_html_is_preserved_but_not_clause_source(self):
        snapshot = {
            "final_editor_html": "<p>Clean ready to send final version.</p>",
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertEqual(schema["render_cache"]["final_editor_html"], snapshot["final_editor_html"])
        self.assertEqual(schema["clauses"], [])
        self.assertIn("final_editor_html", schema["extraction_report"]["source_types"])

    def test_sections_snapshot_becomes_navigation_and_body_clauses_where_possible(self):
        snapshot = {
            "sections": [
                {"id": "s1", "number": 1, "name": "Introduction"},
                {"id": "s2", "number": 2, "name": "Scope", "body": "Provider shall deliver the work."},
            ]
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertEqual(len(schema["render_cache"]["sections"]), 2)
        self.assertEqual(len(schema["clauses"]), 1)
        self.assertEqual(schema["clauses"][0]["id"], "s2")
        self.assertEqual(schema["clauses"][0]["title"], "Scope")

    def test_template_clauses_become_schema_clauses(self):
        snapshot = {
            "clauses": [
                {"clause_type": "scope", "title": "Services", "body": "Provider performs services.", "order": 1},
                {"clause_type": "payment", "title": "Fees", "body": "Client pays $100.", "order": 2},
            ]
        }

        schema = normalize_content_snapshot(json.dumps(snapshot))

        self.assertEqual(len(schema["clauses"]), 2)
        self.assertEqual(schema["clauses"][0]["title"], "Services")
        self.assertEqual(schema["clauses"][1]["clause_type"], "payment")

    def test_prepared_terms_are_preserved_and_mapped(self):
        snapshot = {
            "prepared_terms": {
                "parties": {
                    "initiator": {"name": "Alice", "email": "alice@example.com"},
                    "counterparty": {"name": "Bob", "email": "bob@example.com"},
                },
                "payment_terms": [
                    {"description": "Deposit", "amount": "250.00", "due_date": "2026-06-30"},
                ],
                "service_obligations": [
                    {"description": "Deliver draft", "deadline": "2026-07-15"},
                ],
            }
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertEqual(schema["render_cache"]["prepared_terms"], snapshot["prepared_terms"])
        self.assertEqual(len(schema["participants"]), 2)
        self.assertEqual(len(schema["payment_obligations"]), 1)
        self.assertEqual(len(schema["service_obligations"]), 1)

    def test_malformed_json_returns_canonical_schema_with_warning(self):
        schema = normalize_content_snapshot('{"editor_html": "<p>Broken"')

        self.assertEqual(schema["schema_version"], SCHEMA_VERSION)
        self.assertTrue(schema["extraction_report"]["warnings"])
        self.assertEqual(len(schema["clauses"]), 1)

    def test_contract_metadata_fills_identity_and_participants(self):
        initiator = SimpleNamespace(
            pk=123,
            email="schema-owner@example.com",
            username="schema_owner",
            get_full_name=lambda: "Schema Owner",
        )
        contract = SimpleNamespace(
            initiator=initiator,
            counterparty_name="Client Co",
            counterparty_email="client@example.com",
            title="Service Agreement",
            contract_type="Service Contract",
            description="Design services.",
            structure_type="ONE_TIME",
            currency="USD",
            jurisdiction="Florida",
            governing_law="Florida",
        )

        schema = normalize_content_snapshot("Payment is due on completion.", contract=contract)

        self.assertEqual(schema["contract_identity"]["title"], "Service Agreement")
        self.assertEqual(schema["contract_identity"]["contract_type"], "Service Contract")
        self.assertEqual(len(schema["participants"]), 2)
        self.assertEqual(schema["participants"][0]["role"], "initiator")
        self.assertEqual(schema["participants"][1]["email"], "client@example.com")


    def test_lawn_contract_clause_splitting_avoids_address_and_empty_headings(self):
        snapshot = {
            "editor_html": """
                <h1>Lawn Care Service Agreement</h1>
                <h2>1. Parties</h2><p>Provider and Client agree to this contract.</p>
                <h2>2. Service Property</h2><p>123 Oak Street, Miami, Florida 33130 (Property).</p>
                <h2>3. Scope of Services</h2><p>Provider shall mow, edge, and trim the lawn weekly.</p>
                <h2>4. Payment Terms</h2><p>Client shall pay Provider $150 monthly, due within 10 days of invoice.</p>
                <h2>Signatures</h2><p>Provider: ____________________ Client: ____________________</p>
            """,
        }

        schema = normalize_content_snapshot(snapshot)
        titles = [clause["title"] for clause in schema["clauses"]]
        types = [clause["clause_type"] for clause in schema["clauses"]]

        self.assertNotIn("", titles)
        self.assertNotIn("123 Oak Street, Miami, Florida 33130 (Property).", titles)
        self.assertIn("Parties", titles)
        self.assertIn("Scope of Services", titles)
        self.assertIn("signatures", types)

    def test_placeholder_detection_records_unresolved_fields(self):
        snapshot = {
            "editor_html": "<h2>1. Payment Terms</h2><p>Client shall pay {{total_fee}} by [DATE] to [COMPANY NAME]. Provider: ____</p>",
        }

        schema = normalize_content_snapshot(snapshot)
        reasons = [item["reason"] for item in schema["missing_unresolved_fields"]]

        self.assertTrue(any("{{total_fee}}" in reason for reason in reasons))
        self.assertTrue(any("[DATE]" in reason for reason in reasons))
        self.assertTrue(any("[COMPANY NAME]" in reason for reason in reasons))
        self.assertTrue(any("___" in reason for reason in reasons))

    def test_payment_obligation_extraction_from_clause_text(self):
        snapshot = {
            "editor_html": "<h2>1. Payment Terms</h2><p>Client shall pay Provider $500 monthly. Invoices are due within 14 days of invoice by ACH.</p>",
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertEqual(len(schema["payment_obligations"]), 1)
        payment = schema["payment_obligations"][0]
        self.assertEqual(payment["amount"], "500")
        self.assertEqual(payment["currency"], "USD")
        self.assertEqual(payment["frequency"], "monthly")
        self.assertIn("within 14 days", payment["due_date_rule"])
        self.assertEqual(payment["payment_method"], "ACH")

    def test_service_obligation_extraction_from_scope_and_schedule(self):
        snapshot = {
            "editor_html": "<h2>1. Scope of Services</h2><p>Provider shall mow and edge the lawn weekly on Monday at 123 Oak Street, Miami, Florida 33130 from 9am to 11am.</p>",
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertEqual(len(schema["service_obligations"]), 1)
        service = schema["service_obligations"][0]
        self.assertEqual(service["frequency"], "weekly")
        self.assertIn("monday", service["service_days"])
        self.assertEqual(service["service_hours"].lower(), "9am to 11am")
        self.assertIn("123 Oak Street", service["location"])

    def test_termination_term_promotion(self):
        snapshot = {
            "editor_html": "<h2>8. Termination</h2><p>Either party may terminate this agreement upon fourteen days written notice. Immediate termination for cause is available after material breach.</p>",
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertIsNotNone(schema["termination_terms"])
        self.assertEqual(schema["termination_terms"]["source_clause_id"], schema["clauses"][0]["id"])
        self.assertTrue(schema["termination_terms"]["termination_for_cause"])

    def test_dispute_resolution_term_promotion(self):
        snapshot = {
            "editor_html": "<h2>9. Dispute Resolution</h2><p>Any dispute shall first proceed to mediation, then arbitration. Venue shall be in Miami-Dade County.</p>",
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertIsNotNone(schema["dispute_terms"])
        self.assertEqual(schema["dispute_terms"], schema["resolution_terms"])
        self.assertEqual(schema["dispute_terms"]["method"], "arbitration")
        self.assertIn("Miami-Dade", schema["dispute_terms"]["venue"])

    def test_notices_and_governing_law_promotion(self):
        snapshot = {
            "editor_html": """
                <h2>10. Notices</h2><p>All notices must be provided by email or certified mail within 5 business days.</p>
                <h2>11. Governing Law</h2><p>This agreement is governed by the laws of Florida.</p>
            """,
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertIsNotNone(schema["notices"])
        self.assertIn("email", schema["notices"]["methods"])
        self.assertEqual(schema["notices"]["notice_period"], "within 5 business days")
        self.assertIsNotNone(schema["governing_law"])
        self.assertEqual(schema["governing_law"]["jurisdiction"], "Florida")

    def test_signature_block_classification(self):
        snapshot = {
            "editor_html": "<h2>SIGNATURES</h2><p>Provider: ____________________</p><p>Client: ____________________</p>",
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertEqual(len(schema["clauses"]), 1)
        self.assertEqual(schema["clauses"][0]["clause_type"], "signatures")

    def test_final_editor_html_still_not_used_as_clause_source_after_parser_improvements(self):
        snapshot = {
            "final_editor_html": "<h2>1. Payment Terms</h2><p>Client shall pay $999.</p>",
        }

        schema = normalize_content_snapshot(snapshot)

        self.assertEqual(schema["render_cache"]["final_editor_html"], snapshot["final_editor_html"])
        self.assertEqual(schema["clauses"], [])
        self.assertEqual(schema["payment_obligations"], [])
