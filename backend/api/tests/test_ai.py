# backend/api/tests/test_ai.py
#
# Tests for the AI Assistant domain:
#   POST /api/ai/chat/
#   GET  /api/ai/conversations/
#   GET  /api/ai/conversations/<id>/

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from backend.ai.context import build_user_context
from backend.ai.models import AIConversation
from backend.billing.models import SubscriptionPlan, UserSubscription
from backend.contracts.models import Contract
from .helpers import authed_client, make_contract, make_user, make_subscription

CHAT_URL = "/api/ai/chat/"
CONVERSATIONS_URL = "/api/ai/conversations/"
GENERATE_CONTRACT_DRAFT_URL = "/api/ai/contracts/generate-draft/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_anthropic(response_text="This is the AI response."):
    """Return a mock that mimics anthropic.Anthropic().messages.create()."""
    mock_content = MagicMock()
    mock_content.text = response_text
    mock_msg = MagicMock()
    mock_msg.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mock_anthropic_cls = MagicMock(return_value=mock_client)
    return mock_anthropic_cls, mock_client


def make_ai_subscription(user, ai_tier="basic"):
    """Give user a subscription with the specified AI tier."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug=f"_test_ai_{ai_tier}",
        defaults={
            "display_name": f"Test {ai_tier} AI",
            "price_monthly": Decimal("0.00"),
            "max_active_contracts": None,
            "max_live_sessions_per_month": None,
            "has_lifecycle": True,
            "has_notifications": True,
            "has_negotiation_prep": True,
            "all_templates": True,
            "excluded_categories": [],
            "ai_tier": ai_tier,
        },
    )
    return UserSubscription.objects.create(
        user=user,
        plan=plan,
        status="active",
        billing_period="monthly",
        current_period_start=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Feature gate — tier checks
# ---------------------------------------------------------------------------

class AITierGateTests(TestCase):

    def setUp(self):
        self.user = make_user("gate_user", "gate_user@example.com")
        self.client = authed_client(self.user)

    def test_no_subscription_returns_403(self):
        r = self.client.post(CHAT_URL, {"message": "Hello"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("subscription", r.data["error"].lower())

    def test_none_ai_tier_returns_403(self):
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="_test_no_ai",
            defaults={
                "display_name": "No AI",
                "price_monthly": Decimal("0.00"),
                "ai_tier": "none",
                "has_lifecycle": False,
                "has_notifications": False,
                "has_negotiation_prep": False,
                "all_templates": True,
                "excluded_categories": [],
            },
        )
        UserSubscription.objects.create(
            user=self.user, plan=plan, status="active",
            billing_period="monthly", current_period_start=timezone.now(),
        )
        r = self.client.post(CHAT_URL, {"message": "Hello"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().post(CHAT_URL, {"message": "Hello"}, format="json")
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Contract draft generation
# ---------------------------------------------------------------------------

class AIContractDraftGenerationTests(TestCase):

    def setUp(self):
        self.user = make_user("generate_user", "generate_user@example.com")
        make_ai_subscription(self.user, "basic")
        self.client = authed_client(self.user)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_missing_prompt_or_fields_returns_400(self):
        r = self.client.post(GENERATE_CONTRACT_DRAFT_URL, {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("prompt", r.data["error"].lower())

    @override_settings(ANTHROPIC_API_KEY="")
    def test_provider_not_configured_returns_clear_error(self):
        r = self.client.post(
            GENERATE_CONTRACT_DRAFT_URL,
            {"prompt": "Draft a lawn service contract."},
            format="json",
        )
        self.assertEqual(r.status_code, 503)
        self.assertIn("not configured", r.data["error"].lower())
        self.assertEqual(Contract.objects.filter(initiator=self.user).count(), 0)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_generate_draft_returns_ai_text_and_metadata(self, MockClient):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "LAWN SERVICE AGREEMENT\n\n1. Services..."
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(
            GENERATE_CONTRACT_DRAFT_URL,
            {
                "prompt": "Draft a lawn service agreement.",
                "contract_type": "Lawn Service Agreement",
                "jurisdiction": "Florida",
                "include_clauses": ["payment", "service_obligations"],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["draft_text"], "LAWN SERVICE AGREEMENT\n\n1. Services...")
        self.assertEqual(r.data["title"], "AI Draft - Lawn Service Agreement")
        self.assertIn("missing_fields", r.data)
        self.assertEqual(Contract.objects.filter(initiator=self.user).count(), 0)



# ---------------------------------------------------------------------------
# Chat — basic tier
# ---------------------------------------------------------------------------

class AIChatBasicTests(TestCase):

    def setUp(self):
        self.user = make_user("chat_user", "chat_user@example.com")
        make_ai_subscription(self.user, "basic")
        self.client = authed_client(self.user)

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_chat_returns_response(self, MockClient):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Hello from AI"
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(CHAT_URL, {"message": "What is bonUP?"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["response"], "Hello from AI")
        self.assertIn("conversation_id", r.data)
        self.assertIsNone(r.data["action_taken"])

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_chat_creates_conversation(self, MockClient):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "AI reply"
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(CHAT_URL, {"message": "Hello"}, format="json")
        self.assertEqual(r.status_code, 200)
        conv_id = r.data["conversation_id"]
        conv = AIConversation.objects.get(pk=conv_id)
        self.assertEqual(conv.user, self.user)
        self.assertEqual(len(conv.messages), 2)
        self.assertEqual(conv.messages[0]["role"], "user")
        self.assertEqual(conv.messages[0]["content"], "Hello")
        self.assertEqual(conv.messages[1]["role"], "assistant")
        self.assertEqual(conv.messages[1]["content"], "AI reply")

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_chat_continues_existing_conversation(self, MockClient):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Second reply"
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        conv = AIConversation.objects.create(
            user=self.user,
            messages=[{"role": "user", "content": "First"}, {"role": "assistant", "content": "First reply"}],
        )

        r = self.client.post(
            CHAT_URL,
            {"message": "Follow up", "conversation_id": str(conv.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        conv.refresh_from_db()
        self.assertEqual(len(conv.messages), 4)
        self.assertEqual(conv.messages[2]["content"], "Follow up")
        self.assertEqual(conv.messages[3]["content"], "Second reply")

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_chat_sends_history_to_api(self, MockClient):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "response"
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        conv = AIConversation.objects.create(
            user=self.user,
            messages=[{"role": "user", "content": "Prev"}, {"role": "assistant", "content": "Prev reply"}],
        )
        self.client.post(CHAT_URL, {"message": "New msg", "conversation_id": str(conv.id)}, format="json")
        call_kwargs = mock_instance.messages.create.call_args
        sent_messages = call_kwargs[1]["messages"]
        self.assertEqual(len(sent_messages), 3)  # 2 existing + 1 new

    def test_missing_message_returns_400(self):
        r = self.client.post(CHAT_URL, {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_wrong_conversation_id_returns_404(self):
        r = self.client.post(
            CHAT_URL,
            {"message": "hi", "conversation_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_basic_tier_does_not_execute_actions(self, MockClient):
        """Basic tier: even if response contains action JSON, it is NOT executed."""
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = (
            'Here is your contract.\n```json\n{"action": "create_contract", '
            '"contract": {"counterparty_email": "x@x.com", "structure_type": "ONE_TIME", "content": ""},'
            '"obligations": []}\n```'
        )
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(CHAT_URL, {"message": "Write me a contract"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["action_taken"])
        self.assertEqual(Contract.objects.filter(initiator=self.user).count(), 0)


# ---------------------------------------------------------------------------
# Chat — full tier action execution
# ---------------------------------------------------------------------------

class AIChatFullTierActionTests(TestCase):

    def setUp(self):
        self.user = make_user("full_user", "full_user@example.com")
        make_ai_subscription(self.user, "full")
        self.client = authed_client(self.user)

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_full_tier_executes_create_contract_action(self, MockClient):
        other_user = make_user("full_other", "full_other@example.com")
        action_json = (
            '```json\n'
            '{"action": "create_contract", '
            '"contract": {"title": "Test", "counterparty_email": "full_other@example.com", '
            '"structure_type": "ONE_TIME", "content": "Terms here."}, '
            '"obligations": []}\n```'
        )
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = f"Here is your contract.\n{action_json}"
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(CHAT_URL, {"message": "Create a contract with full_other"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data["action_taken"])
        self.assertEqual(r.data["action_taken"]["status"], "created")
        self.assertEqual(r.data["action_taken"]["action"], "create_contract")
        self.assertEqual(Contract.objects.filter(initiator=self.user).count(), 1)

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_full_tier_no_action_block_returns_none(self, MockClient):
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Here is some advice about your contract."
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(CHAT_URL, {"message": "Explain my obligations"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["action_taken"])

    @patch("backend.api.ai.views.anthropic.Anthropic")
    def test_full_tier_blocked_when_no_subscription_budget(self, MockClient):
        """Contract creation blocked at gate, but chat still succeeds."""
        from backend.billing.models import UserSubscription
        sub = UserSubscription.objects.get(user=self.user)
        plan = sub.plan
        plan.max_active_contracts = 0
        plan.save()

        action_json = (
            '```json\n{"action": "create_contract", '
            '"contract": {"counterparty_email": "x@x.com", "structure_type": "ONE_TIME", "content": ""},'
            '"obligations": []}\n```'
        )
        mock_instance = MagicMock()
        mock_content = MagicMock()
        mock_content.text = f"Here is your contract.\n{action_json}"
        mock_instance.messages.create.return_value = MagicMock(content=[mock_content])
        MockClient.return_value = mock_instance

        r = self.client.post(CHAT_URL, {"message": "Create a contract"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["action_taken"]["status"], "blocked")


# ---------------------------------------------------------------------------
# Action extraction
# ---------------------------------------------------------------------------

class ActionExtractionTests(TestCase):

    def test_extracts_fenced_json(self):
        from backend.api.ai.views import _extract_action
        text = 'Here is your contract.\n```json\n{"action": "create_contract"}\n```'
        result = _extract_action(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "create_contract")

    def test_returns_none_for_no_block(self):
        from backend.api.ai.views import _extract_action
        text = "Here is some advice with no action block."
        self.assertIsNone(_extract_action(text))

    def test_returns_none_for_malformed_json(self):
        from backend.api.ai.views import _extract_action
        text = '```json\n{bad json here}\n```'
        self.assertIsNone(_extract_action(text))


# ---------------------------------------------------------------------------
# Conversation list
# ---------------------------------------------------------------------------

class AIConversationListTests(TestCase):

    def setUp(self):
        self.user = make_user("cl_user", "cl_user@example.com")
        self.other = make_user("cl_other", "cl_other@example.com")
        self.client = authed_client(self.user)

    def test_list_returns_own_conversations(self):
        AIConversation.objects.create(user=self.user, messages=[])
        AIConversation.objects.create(user=self.other, messages=[])
        r = self.client.get(CONVERSATIONS_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)

    def test_list_is_paginated(self):
        for _ in range(25):
            AIConversation.objects.create(user=self.user, messages=[])
        r = self.client.get(CONVERSATIONS_URL)
        self.assertEqual(r.data["count"], 25)
        self.assertEqual(len(r.data["results"]), 20)
        r2 = self.client.get(f"{CONVERSATIONS_URL}?page=2")
        self.assertEqual(len(r2.data["results"]), 5)

    def test_list_result_has_expected_fields(self):
        AIConversation.objects.create(user=self.user, messages=[
            {"role": "user", "content": "hi"}
        ])
        r = self.client.get(CONVERSATIONS_URL)
        item = r.data["results"][0]
        for field in ("id", "conversation_type", "contract_id",
                      "message_count", "created_at", "updated_at"):
            self.assertIn(field, item)
        self.assertEqual(item["message_count"], 1)

    def test_list_does_not_include_messages(self):
        AIConversation.objects.create(user=self.user, messages=[{"role": "user", "content": "hi"}])
        r = self.client.get(CONVERSATIONS_URL)
        self.assertNotIn("messages", r.data["results"][0])

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(CONVERSATIONS_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Conversation detail
# ---------------------------------------------------------------------------

class AIConversationDetailTests(TestCase):

    def setUp(self):
        self.user = make_user("cd_user", "cd_user@example.com")
        self.other = make_user("cd_other", "cd_other@example.com")
        self.client = authed_client(self.user)

    def test_retrieve_own_conversation(self):
        conv = AIConversation.objects.create(
            user=self.user,
            messages=[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}],
        )
        r = self.client.get(f"{CONVERSATIONS_URL}{conv.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], str(conv.id))
        self.assertIn("messages", r.data)
        self.assertEqual(len(r.data["messages"]), 2)

    def test_cannot_retrieve_others_conversation(self):
        conv = AIConversation.objects.create(user=self.other, messages=[])
        r = self.client.get(f"{CONVERSATIONS_URL}{conv.id}/")
        self.assertEqual(r.status_code, 404)

    def test_nonexistent_returns_404(self):
        r = self.client.get(f"{CONVERSATIONS_URL}{uuid.uuid4()}/")
        self.assertEqual(r.status_code, 404)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        conv = AIConversation.objects.create(user=self.user, messages=[])
        r = APIClient().get(f"{CONVERSATIONS_URL}{conv.id}/")
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Context builder (unit)
# ---------------------------------------------------------------------------

class BuildUserContextTests(TestCase):

    def setUp(self):
        self.user = make_user("ctx_user", "ctx_user@example.com")

    def test_context_includes_username(self):
        ctx = build_user_context(self.user)
        self.assertIn("ctx_user", ctx)

    def test_context_includes_bon_id(self):
        profile = self.user.bon_profile
        ctx = build_user_context(self.user)
        self.assertIn(profile.bon_id, ctx)

    def test_context_includes_subscription_info(self):
        make_ai_subscription(self.user, "basic")
        ctx = build_user_context(self.user)
        self.assertIn("AI Tier", ctx)

    def test_context_includes_contracts(self):
        other = make_user("ctx_other", "ctx_other@example.com")
        make_contract(self.user, other.email)
        ctx = build_user_context(self.user)
        self.assertIn("Active Contracts", ctx)

    def test_context_no_subscription_says_none(self):
        ctx = build_user_context(self.user)
        self.assertIn("Subscription: None", ctx)
