# backend/api/tests/test_ai_contract_tools.py
#
# Tests for:
#   POST /api/ai/analyze-contract/
#   POST /api/ai/counter-contract/
#   POST /api/ai/import-contract/

import io
import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from backend.ai.models import AIConversation
from backend.billing.models import SubscriptionPlan, UserSubscription
from backend.contracts.models import Contract, ContractObligation, ContractServiceObligation

from .helpers import authed_client, make_user

ANALYZE_URL = "/api/ai/analyze-contract/"
COUNTER_URL = "/api/ai/counter-contract/"
IMPORT_URL = "/api/ai/import-contract/"

_SAMPLE_PDF_TEXT = """\
SERVICE AGREEMENT

This Agreement is entered into between Acme Corp ("Provider") and Client Co ("Client").

1. SERVICES: Provider will deliver software development services.
2. PAYMENT: Client will pay $5,000 per month due on the 1st of each month.
3. TERM: This Agreement begins on 2024-01-01 and ends on 2024-12-31.
4. NON-COMPETE: Client may not hire Provider's employees for 2 years after termination.
"""

_ANALYZE_JSON = {
    "summary": "A service agreement between Acme Corp and Client Co for software services.",
    "key_terms": {
        "parties": ["Acme Corp (Provider)", "Client Co (Client)"],
        "dates": ["Start: 2024-01-01", "End: 2024-12-31"],
        "amounts": ["$5,000/month"],
        "duration": "12 months",
    },
    "red_flags": ["Non-compete clause is broadly worded."],
    "questions": ["What counts as a similar service for the non-compete?"],
}

_COUNTER_JSON = {
    "summary": "Contract has a broad non-compete and payment clause.",
    "concerning_clauses": [
        {
            "clause_reference": "Section 4",
            "concern": "2-year non-compete is excessive.",
            "counter_language": "Limit non-compete to 6 months and same industry.",
        }
    ],
    "negotiation_strategy": {
        "push_on": ["Non-compete duration"],
        "concede": ["Payment schedule"],
    },
    "revised_contract": "SERVICE AGREEMENT (REVISED)\n...",
}

_IMPORT_JSON = {
    "title": "Software Services Agreement",
    "counterparty_email": None,
    "structure_type": "ONGOING",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "summary": "Monthly software development services for 12 months.",
    "payment_obligations": [
        {
            "description": "Monthly retainer",
            "amount": 5000.00,
            "due_date": "2024-02-01",
            "recurrence_interval_days": 30,
        }
    ],
    "service_obligations": [
        {
            "description": "Deliver monthly development sprint",
            "due_date": "2024-01-31",
        }
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(slug, ai_tier="none", has_sol=False):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug=slug,
        defaults={
            "display_name": f"Test {slug}",
            "price_monthly": Decimal("0.00"),
            "max_active_contracts": None,
            "max_live_sessions_per_month": None,
            "has_lifecycle": True,
            "has_notifications": False,
            "has_negotiation_prep": False,
            "all_templates": True,
            "excluded_categories": [],
            "has_sol": has_sol,
            "ai_tier": ai_tier,
        },
    )
    return plan


def _make_subscription(user, ai_tier="none", has_sol=False):
    slug = f"_test_tool_{ai_tier}_sol{int(has_sol)}"
    plan = _make_plan(slug, ai_tier=ai_tier, has_sol=has_sol)
    return UserSubscription.objects.create(
        user=user,
        plan=plan,
        status="active",
        billing_period="monthly",
        current_period_start=timezone.now(),
    )


def _mock_anthropic_response(response_json: dict):
    """Return patch kwargs that make anthropic.Anthropic().messages.create() return JSON."""
    json_block = f"```json\n{json.dumps(response_json, indent=2)}\n```"
    mock_content = MagicMock()
    mock_content.text = json_block
    mock_msg = MagicMock()
    mock_msg.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return MagicMock(return_value=mock_client)


def _fake_pdf():
    """Return a minimal in-memory file object that passes file upload."""
    return io.BytesIO(b"%PDF-1.4 fake pdf content for testing")


# ---------------------------------------------------------------------------
# Analyze Contract — tier gate
# ---------------------------------------------------------------------------

class AnalyzeContractTierTests(TestCase):

    def setUp(self):
        self.user = make_user("analyze_gate", "analyze_gate@example.com")

    def test_no_subscription_returns_403(self):
        r = authed_client(self.user).post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)
        self.assertIn("subscription", r.data["error"].lower())

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 401)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_starter_tier_returns_200(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_ANALYZE_JSON).return_value
        _make_subscription(self.user, ai_tier="basic")
        r = authed_client(self.user).post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_advanced_tier_returns_200(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_ANALYZE_JSON).return_value
        _make_subscription(self.user, ai_tier="advanced")
        r = authed_client(self.user).post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_full_tier_returns_200(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_ANALYZE_JSON).return_value
        _make_subscription(self.user, ai_tier="full", has_sol=True)
        r = authed_client(self.user).post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# Analyze Contract — functional
# ---------------------------------------------------------------------------

class AnalyzeContractTests(TestCase):

    def setUp(self):
        self.user = make_user("analyze_user", "analyze_user@example.com")
        _make_subscription(self.user, ai_tier="advanced")
        self.client = authed_client(self.user)

    def test_no_file_no_upload_id_returns_400(self):
        r = self.client.post(ANALYZE_URL, {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_returns_structured_fields(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_ANALYZE_JSON).return_value
        r = self.client.post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertIn("conversation_id", r.data)
        self.assertIn("summary", r.data)
        self.assertIn("key_terms", r.data)
        self.assertIn("red_flags", r.data)
        self.assertIn("questions", r.data)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_response_values_match_ai_output(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_ANALYZE_JSON).return_value
        r = self.client.post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.data["summary"], _ANALYZE_JSON["summary"])
        self.assertEqual(r.data["red_flags"], _ANALYZE_JSON["red_flags"])
        self.assertEqual(r.data["questions"], _ANALYZE_JSON["questions"])

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_saves_conversation(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_ANALYZE_JSON).return_value
        r = self.client.post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        conv_id = r.data["conversation_id"]
        conv = AIConversation.objects.get(pk=conv_id)
        self.assertEqual(conv.user, self.user)
        self.assertEqual(conv.conversation_type, "contract_help")
        self.assertEqual(len(conv.messages), 2)
        self.assertEqual(conv.messages[0]["role"], "user")
        self.assertEqual(conv.messages[1]["role"], "assistant")

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_ai_receives_pdf_text_in_message(self, MockClient, _mock_pdf):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = f"```json\n{json.dumps(_ANALYZE_JSON)}\n```"
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        self.client.post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        call_kwargs = mock_instance.messages.create.call_args[1]
        sent_messages = call_kwargs["messages"]
        self.assertIn(_SAMPLE_PDF_TEXT, sent_messages[0]["content"])

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_graceful_when_ai_returns_no_json(self, MockClient, _mock_pdf):
        """If AI returns plain text without JSON block, return empty fields rather than crash."""
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "I was unable to analyze this document."
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(ANALYZE_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["summary"], "")
        self.assertEqual(r.data["red_flags"], [])
        self.assertEqual(r.data["questions"], [])


# ---------------------------------------------------------------------------
# Counter Contract — tier gate
# ---------------------------------------------------------------------------

class CounterContractTierTests(TestCase):

    def setUp(self):
        self.user = make_user("counter_gate", "counter_gate@example.com")

    def test_no_subscription_returns_403(self):
        r = authed_client(self.user).post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_basic_tier_returns_403(self):
        _make_subscription(self.user, ai_tier="basic", has_sol=False)
        r = authed_client(self.user).post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Business", r.data["error"])

    def test_advanced_without_sol_returns_403(self):
        """Professional tier (advanced AI, no Sol) should be denied."""
        _make_subscription(self.user, ai_tier="advanced", has_sol=False)
        r = authed_client(self.user).post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 401)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_business_tier_returns_200(self, MockClient, _mock_pdf):
        """Business tier: advanced AI + has_sol."""
        MockClient.return_value = _mock_anthropic_response(_COUNTER_JSON).return_value
        _make_subscription(self.user, ai_tier="advanced", has_sol=True)
        r = authed_client(self.user).post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_anchor_tier_returns_200(self, MockClient, _mock_pdf):
        """Anchor tier: full AI + has_sol."""
        MockClient.return_value = _mock_anthropic_response(_COUNTER_JSON).return_value
        _make_subscription(self.user, ai_tier="full", has_sol=True)
        r = authed_client(self.user).post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# Counter Contract — functional
# ---------------------------------------------------------------------------

class CounterContractTests(TestCase):

    def setUp(self):
        self.user = make_user("counter_user", "counter_user@example.com")
        _make_subscription(self.user, ai_tier="advanced", has_sol=True)
        self.client = authed_client(self.user)

    def test_no_file_returns_400(self):
        r = self.client.post(COUNTER_URL, {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_returns_structured_fields(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_COUNTER_JSON).return_value
        r = self.client.post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertIn("conversation_id", r.data)
        self.assertIn("summary", r.data)
        self.assertIn("concerning_clauses", r.data)
        self.assertIn("negotiation_strategy", r.data)
        self.assertIn("revised_contract", r.data)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_response_values_match_ai_output(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_COUNTER_JSON).return_value
        r = self.client.post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.data["summary"], _COUNTER_JSON["summary"])
        self.assertEqual(len(r.data["concerning_clauses"]), 1)
        self.assertEqual(r.data["concerning_clauses"][0]["clause_reference"], "Section 4")
        self.assertIn("push_on", r.data["negotiation_strategy"])

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_saves_conversation(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_COUNTER_JSON).return_value
        r = self.client.post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        conv = AIConversation.objects.get(pk=r.data["conversation_id"])
        self.assertEqual(conv.user, self.user)
        self.assertEqual(len(conv.messages), 2)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_graceful_when_ai_returns_no_json(self, MockClient, _mock_pdf):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "I could not parse this contract."
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(COUNTER_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["summary"], "")
        self.assertEqual(r.data["concerning_clauses"], [])
        self.assertEqual(r.data["revised_contract"], "")


# ---------------------------------------------------------------------------
# Import Contract — tier gate
# ---------------------------------------------------------------------------

class ImportContractTierTests(TestCase):

    def setUp(self):
        self.user = make_user("import_gate", "import_gate@example.com")

    def test_no_subscription_returns_403(self):
        r = authed_client(self.user).post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_basic_tier_returns_403(self):
        _make_subscription(self.user, ai_tier="basic")
        r = authed_client(self.user).post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Anchor", r.data["error"])

    def test_advanced_tier_returns_403(self):
        _make_subscription(self.user, ai_tier="advanced", has_sol=True)
        r = authed_client(self.user).post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 401)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_full_tier_returns_201(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_IMPORT_JSON).return_value
        _make_subscription(self.user, ai_tier="full", has_sol=True)
        r = authed_client(self.user).post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 201)


# ---------------------------------------------------------------------------
# Import Contract — functional
# ---------------------------------------------------------------------------

class ImportContractTests(TestCase):

    def setUp(self):
        self.user = make_user("import_user", "import_user@example.com")
        _make_subscription(self.user, ai_tier="full", has_sol=True)
        self.client = authed_client(self.user)

    def test_no_file_returns_400(self):
        r = self.client.post(IMPORT_URL, {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_creates_contract(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_IMPORT_JSON).return_value
        r = self.client.post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertIn("contract_id", r.data)
        contract = Contract.objects.get(pk=r.data["contract_id"])
        self.assertEqual(contract.initiator, self.user)
        self.assertEqual(contract.structure_type, "ONGOING")

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_returns_structured_fields(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_IMPORT_JSON).return_value
        r = self.client.post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertIn("conversation_id", r.data)
        self.assertIn("contract_id", r.data)
        self.assertIn("counterparty_found", r.data)
        self.assertIn("obligations_created", r.data)
        self.assertIn("summary", r.data)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_no_counterparty_email_creates_contract_without_obligations(self, MockClient, _mock_pdf):
        """When counterparty cannot be found, contract is created but obligations are skipped."""
        MockClient.return_value = _mock_anthropic_response(_IMPORT_JSON).return_value
        r = self.client.post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["counterparty_found"])
        self.assertEqual(r.data["obligations_created"], [])
        # Contract still created
        self.assertTrue(Contract.objects.filter(pk=r.data["contract_id"]).exists())

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_creates_obligations_when_counterparty_exists(self, MockClient, _mock_pdf):
        """When counterparty email resolves to a bonUP user, obligations are created."""
        counterparty = make_user("cp_import", "cp_import@example.com")
        import_data = dict(_IMPORT_JSON)
        import_data["counterparty_email"] = "cp_import@example.com"

        MockClient.return_value = _mock_anthropic_response(import_data).return_value
        r = self.client.post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["counterparty_found"])
        self.assertEqual(len(r.data["obligations_created"]), 2)  # 1 payment + 1 service

        contract_id = r.data["contract_id"]
        self.assertEqual(ContractObligation.objects.filter(contract_id=contract_id).count(), 1)
        self.assertEqual(ContractServiceObligation.objects.filter(contract_id=contract_id).count(), 1)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_counterparty_email_override_takes_precedence(self, MockClient, _mock_pdf):
        """Caller-supplied counterparty_email overrides AI extraction."""
        counterparty = make_user("cp_override", "cp_override@example.com")
        # AI returns null for counterparty_email, but caller provides override
        MockClient.return_value = _mock_anthropic_response(_IMPORT_JSON).return_value
        r = self.client.post(
            IMPORT_URL,
            {"file": _fake_pdf(), "counterparty_email": "cp_override@example.com"},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["counterparty_found"])

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_saves_conversation_linked_to_contract(self, MockClient, _mock_pdf):
        MockClient.return_value = _mock_anthropic_response(_IMPORT_JSON).return_value
        r = self.client.post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        conv = AIConversation.objects.get(pk=r.data["conversation_id"])
        self.assertEqual(conv.user, self.user)
        self.assertEqual(str(conv.contract_id), r.data["contract_id"])
        self.assertEqual(len(conv.messages), 2)

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_graceful_when_ai_returns_no_json(self, MockClient, _mock_pdf):
        """If AI fails to return JSON, contract is still created with empty obligations."""
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "I could not extract data from this document."
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertIn("contract_id", r.data)
        self.assertEqual(r.data["obligations_created"], [])

    @patch("backend.api.ai.views._extract_pdf_text", return_value=_SAMPLE_PDF_TEXT)
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_obligations_have_correct_types(self, MockClient, _mock_pdf):
        counterparty = make_user("cp_types", "cp_types@example.com")
        import_data = dict(_IMPORT_JSON)
        import_data["counterparty_email"] = "cp_types@example.com"
        MockClient.return_value = _mock_anthropic_response(import_data).return_value

        r = self.client.post(IMPORT_URL, {"file": _fake_pdf()}, format="multipart")
        types = {o["type"] for o in r.data["obligations_created"]}
        self.assertIn("payment", types)
        self.assertIn("service", types)
