import json

from django.test import TestCase

from backend.api.contracts.serializers import ContractVersionSerializer
from backend.api.tests.helpers import make_contract, make_user, make_version
from backend.contracts.section_normalizer import normalize_contract_sections


class ContractSectionNormalizerTests(TestCase):
    def test_standard_sections_normalize_consistently(self):
        sections = normalize_contract_sections({
            "sections": [
                {"id": "payment", "number": 1, "name": "Payment Terms", "content_html": "<p>Due monthly.</p>"},
            ]
        })

        self.assertEqual(sections[0]["id"], "payment")
        self.assertEqual(sections[0]["title"], "Payment Terms")
        self.assertEqual(sections[0]["order"], 1)
        self.assertEqual(sections[0]["anchor_id"], "contract-section-payment")
        self.assertEqual(sections[0]["content_html"], "<p>Due monthly.</p>")

    def test_heading_name_label_fields_normalize(self):
        sections = normalize_contract_sections({
            "sections": [
                {"section_id": "scope", "heading": "Scope of Work", "body": "Do the work."},
                {"key": "term", "label": "Term", "text": "One year."},
            ]
        })

        self.assertEqual(sections[0]["id"], "scope")
        self.assertEqual(sections[0]["name"], "Scope of Work")
        self.assertEqual(sections[1]["id"], "term")
        self.assertEqual(sections[1]["name"], "Term")

    def test_missing_ids_get_deterministic_ids(self):
        snapshot = {"sections": [{"title": "Payment Terms"}, {"title": "Payment Terms"}]}

        first = normalize_contract_sections(snapshot)
        second = normalize_contract_sections(snapshot)

        self.assertEqual(first, second)
        self.assertEqual(first[0]["id"], "1-payment-terms")
        self.assertEqual(first[1]["id"], "2-payment-terms")

    def test_dict_based_sections_normalize(self):
        sections = normalize_contract_sections({
            "sections": {
                "confidentiality": {"title": "Confidentiality", "html": "<p>Keep private.</p>"},
                "termination": "Either party may terminate.",
            }
        })

        self.assertEqual(sections[0]["id"], "confidentiality")
        self.assertEqual(sections[0]["content_html"], "<p>Keep private.</p>")
        self.assertEqual(sections[1]["id"], "termination")
        self.assertEqual(sections[1]["name"], "Section 2")
        self.assertEqual(sections[1]["content_html"], "Either party may terminate.")

    def test_contract_version_serializer_returns_normalized_sections(self):
        user = make_user("section_owner", "section-owner@example.com")
        contract = make_contract(user, "counterparty@example.com")
        version = make_version(
            contract,
            user,
            content_snapshot=json.dumps({"sections": [{"heading": "Services", "content": "Monthly service."}]}),
        )

        data = ContractVersionSerializer(version).data

        self.assertEqual(data["sections"][0]["id"], "1-services")
        self.assertEqual(data["sections"][0]["anchor_id"], "contract-section-1-services")
        self.assertEqual(data["sections"][0]["name"], "Services")
