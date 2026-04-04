# backend/api/ai/views.py

import json
import re

import anthropic

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.ai.context import build_user_context
from backend.ai.models import AIConversation
from backend.ai.prompts import BASIC_PROMPT, ADVANCED_PROMPT, FULL_PROMPT
from backend.billing.gates import get_ai_tier
from backend.contracts.models import Contract, ContractVersion, ContractObligation, ContractServiceObligation

TIER_PROMPTS = {
    "basic": BASIC_PROMPT,
    "advanced": ADVANCED_PROMPT,
    "full": FULL_PROMPT,
}

AI_MODEL = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6")
AI_MAX_TOKENS = 2000
PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_conversation(conv, include_messages=False):
    data = {
        "id": str(conv.id),
        "conversation_type": conv.conversation_type,
        "contract_id": str(conv.contract_id) if conv.contract_id else None,
        "message_count": len(conv.messages),
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }
    if include_messages:
        data["messages"] = conv.messages
    return data


def _extract_action(text: str):
    """
    Extract a JSON action block from the end of the assistant response.
    Returns a dict or None.
    """
    # Look for ```json ... ``` fenced block
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            return None

    # Fallback: look for a bare { ... } block containing "action" near the end
    bare = re.search(r'(\{[^{}]*"action"\s*:[^{}]*\})\s*$', text, re.DOTALL)
    if bare:
        try:
            return json.loads(bare.group(1))
        except json.JSONDecodeError:
            return None

    return None


def _execute_action(action_data: dict, user) -> dict:
    """
    Execute a parsed action block. Returns a summary dict.
    """
    action = action_data.get("action")

    if action == "instantiate_template":
        return _execute_instantiate_template(action_data, user)
    elif action == "create_contract":
        return _execute_create_contract(action_data, user)
    else:
        return {"status": "unknown_action", "action": action}


def _execute_instantiate_template(data: dict, user) -> dict:
    from backend.contract_templates.services.template_instantiation_service import (
        TemplateInstantiationService,
        TemplateInstantiationError,
    )
    from backend.billing.gates import can_create_contract, increment_contracts_used, consume_trial_contract

    allowed, msg = can_create_contract(user)
    if not allowed:
        return {"status": "blocked", "reason": msg}

    template_id = data.get("template_id")
    counterparty_email = data.get("counterparty_email", "")
    guided_field_values = data.get("guided_field_values", {})
    start_date_str = data.get("start_date", timezone.now().date().isoformat())

    if not template_id or not counterparty_email:
        return {"status": "error", "reason": "template_id and counterparty_email are required"}

    service = TemplateInstantiationService()
    try:
        result = service.instantiate(
            template_id=template_id,
            guided_field_values=guided_field_values,
            initiator=user,
            counterparty_email=counterparty_email,
            start_date_str=start_date_str,
        )
    except TemplateInstantiationError as exc:
        return {"status": "error", "reason": str(exc)}

    increment_contracts_used(user)
    consume_trial_contract(user)

    return {
        "status": "created",
        "action": "instantiate_template",
        "contract_id": str(result["contract"].id),
        "payment_obligations_created": len(result["payment_obligations"]),
        "service_obligations_created": len(result["service_obligations"]),
    }


def _execute_create_contract(data: dict, user) -> dict:
    from django.contrib.auth import get_user_model
    from backend.billing.gates import can_create_contract, increment_contracts_used, consume_trial_contract

    allowed, msg = can_create_contract(user)
    if not allowed:
        return {"status": "blocked", "reason": msg}

    contract_data = data.get("contract", {})
    obligations_data = data.get("obligations", [])

    counterparty_email = contract_data.get("counterparty_email", "")
    structure_type = contract_data.get("structure_type", "ONE_TIME")
    content = contract_data.get("content", "")

    if not counterparty_email:
        return {"status": "error", "reason": "counterparty_email is required"}

    User = get_user_model()

    with transaction.atomic():
        contract = Contract.objects.create(
            initiator=user,
            counterparty_email=counterparty_email,
            structure_type=structure_type,
        )

        version = ContractVersion.objects.create(
            contract=contract,
            version_number=1,
            created_by=user,
            content_snapshot=content,
            status="draft",
        )

        pay_count = 0
        svc_count = 0

        # Try to find counterparty for obligation FK
        try:
            counterparty = User.objects.get(email=counterparty_email)
        except User.DoesNotExist:
            counterparty = None

        for obl in obligations_data:
            obl_type = obl.get("obligation_type", "service")
            description = obl.get("description", "")
            amount = obl.get("amount", 0)
            offset_days = int(obl.get("due_date_offset_days", 0))
            due_date = timezone.now() + timezone.timedelta(days=offset_days)

            if counterparty is None:
                # Can't create obligations without a registered counterparty
                continue

            if obl_type == "payment":
                ContractObligation.objects.create(
                    contract=contract,
                    version=version,
                    obligor=user,
                    obligee=counterparty,
                    installment_number=pay_count + 1,
                    amount_due=amount,
                    due_date=due_date,
                )
                pay_count += 1
            else:
                ContractServiceObligation.objects.create(
                    contract=contract,
                    version=version,
                    obligor=user,
                    obligee=counterparty,
                    description=description,
                    due_date=due_date,
                )
                svc_count += 1

    increment_contracts_used(user)
    consume_trial_contract(user)

    return {
        "status": "created",
        "action": "create_contract",
        "contract_id": str(contract.id),
        "version_id": str(version.id),
        "payment_obligations_created": pay_count,
        "service_obligations_created": svc_count,
        "counterparty_found": counterparty is not None,
    }


# ---------------------------------------------------------------------------
# POST /api/ai/chat/
# ---------------------------------------------------------------------------

class AIChatView(APIView):

    def post(self, request):
        ai_tier = get_ai_tier(request.user)
        if ai_tier == "none":
            return Response(
                {"error": _("AI features require a Professional, Business, or Anchor subscription.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"error": _("message is required")}, status=status.HTTP_400_BAD_REQUEST)

        conversation_id = request.data.get("conversation_id")
        contract_id = request.data.get("contract_id")

        # Load or create conversation
        if conversation_id:
            conv = get_object_or_404(AIConversation, pk=conversation_id, user=request.user)
        else:
            conv = AIConversation(user=request.user)
            if contract_id:
                conv.contract_id = contract_id
            conv.messages = []

        # Build context and system prompt
        user_context = build_user_context(request.user)
        system_prompt = TIER_PROMPTS[ai_tier].replace("{{user_context}}", user_context)

        # Append user message
        conv.messages.append({"role": "user", "content": message})

        # Call Anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        api_response = client.messages.create(
            model=AI_MODEL,
            max_tokens=AI_MAX_TOKENS,
            system=system_prompt,
            messages=list(conv.messages),
        )
        assistant_text = api_response.content[0].text

        # Append assistant response
        conv.messages.append({"role": "assistant", "content": assistant_text})

        # Execute action if full tier and action block present
        action_taken = None
        if ai_tier == "full":
            action_data = _extract_action(assistant_text)
            if action_data:
                action_taken = _execute_action(action_data, request.user)

        conv.save()

        return Response({
            "response": assistant_text,
            "conversation_id": str(conv.id),
            "action_taken": action_taken,
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# GET /api/ai/conversations/
# ---------------------------------------------------------------------------

class AIConversationListView(APIView):

    def get(self, request):
        qs = AIConversation.objects.filter(user=request.user)
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        offset = (page - 1) * PAGE_SIZE
        total = qs.count()
        items = qs[offset: offset + PAGE_SIZE]
        return Response({
            "count": total,
            "page": page,
            "results": [_serialize_conversation(c) for c in items],
        })


# ---------------------------------------------------------------------------
# GET /api/ai/conversations/<id>/
# ---------------------------------------------------------------------------

class AIConversationDetailView(APIView):

    def get(self, request, conversation_id):
        conv = get_object_or_404(AIConversation, pk=conversation_id, user=request.user)
        return Response(_serialize_conversation(conv, include_messages=True))
