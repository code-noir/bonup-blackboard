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
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.ai.context import build_user_context
from backend.ai.models import AIConversation
from backend.ai.prompts import BASIC_PROMPT, ADVANCED_PROMPT, FULL_PROMPT
from backend.billing.gates import get_ai_tier, has_feature
from backend.contracts.models import Contract, ContractVersion, ContractObligation, ContractServiceObligation

TIER_PROMPTS = {
    "basic": BASIC_PROMPT,
    "advanced": ADVANCED_PROMPT,
    "full": FULL_PROMPT,
}

AI_MODEL = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6")
AI_MAX_TOKENS = 2000
AI_MAX_TOKENS_ANALYSIS = 4000
PAGE_SIZE = 20

# ---------------------------------------------------------------------------
# System prompts for contract tool endpoints
# ---------------------------------------------------------------------------

ANALYZE_CONTRACT_PROMPT = """\
You are a contract analysis specialist. The user has uploaded a contract PDF for review.
Analyze it thoroughly and return a structured analysis.

Return your analysis using this exact JSON format inside a ```json ... ``` block at the END \
of your response:

```json
{
  "summary": "2-3 paragraph plain language summary of the entire contract",
  "key_terms": {
    "parties": ["Name and role of each party"],
    "dates": ["Key dates and their significance"],
    "amounts": ["Dollar amounts and what they represent"],
    "duration": "Contract duration or term length"
  },
  "red_flags": ["Each concerning clause, missing protection, or unfair term"],
  "questions": ["Specific questions to ask before signing"]
}
```

You may include a brief introductory sentence before the JSON block.
Do NOT include any text after the closing ``` of the JSON block.
"""

COUNTER_CONTRACT_PROMPT = """\
You are a contract negotiation expert. The user has uploaded a contract from a bank, \
landlord, employer, dealership, or corporation and wants help negotiating better terms.

Provide: a summary of concerning clauses, specific counter language for each, a negotiation \
strategy, and a full revised counter version of the contract.

Return using this exact JSON format inside a ```json ... ``` block at the END of your response:

```json
{
  "summary": "Overview of the contract and its most concerning elements",
  "concerning_clauses": [
    {
      "clause_reference": "Section or location in contract",
      "concern": "Why this clause is problematic",
      "counter_language": "Specific revised language to propose"
    }
  ],
  "negotiation_strategy": {
    "push_on": ["Issues where you should push hard for changes"],
    "concede": ["Issues where you can accept their terms or compromise"]
  },
  "revised_contract": "Full revised contract text with all suggested changes incorporated"
}
```

You may include a brief introductory sentence before the JSON block.
Do NOT include any text after the closing ``` of the JSON block.
"""

IMPORT_CONTRACT_PROMPT = """\
You are a contract data extraction specialist. The user has uploaded an existing contract PDF. \
Extract all structured data from it to create records in the bonUP contract management system.

Extract parties, contract type, term, key dates, all payment obligations, and all \
service/delivery obligations.

Return ONLY a ```json ... ``` block containing:

```json
{
  "title": "Short descriptive title for this contract",
  "counterparty_email": "email@example.com or null if not found in the contract",
  "structure_type": "ONE_TIME or ONGOING",
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "summary": "2-3 sentence summary of what this contract is",
  "payment_obligations": [
    {
      "description": "What this payment is for",
      "amount": 0.00,
      "due_date": "YYYY-MM-DD",
      "recurrence_interval_days": null
    }
  ],
  "service_obligations": [
    {
      "description": "What must be done",
      "due_date": "YYYY-MM-DD"
    }
  ]
}
```

Use null for any field you cannot determine from the contract text.
Return ONLY the JSON block with no surrounding text.
"""


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


# ---------------------------------------------------------------------------
# PDF helpers (shared by analyze, counter, import endpoints)
# ---------------------------------------------------------------------------

def _get_pdf_bytes(request):
    """
    Return (bytes, None) on success or (None, error_Response) on failure.
    Accepts multipart 'file' upload OR 'upload_id' of an existing Upload record.
    """
    file = request.FILES.get("file")
    if file:
        return file.read(), None

    upload_id = request.data.get("upload_id")
    if upload_id:
        from django.core.files.storage import default_storage
        from backend.uploads.models import Upload

        try:
            upload = Upload.objects.get(pk=upload_id, user=request.user)
        except Upload.DoesNotExist:
            return None, Response({"error": "Upload not found."}, status=status.HTTP_404_NOT_FOUND)
        if upload.file_type != "pdf":
            return None, Response(
                {"error": "The referenced upload is not a PDF file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        f = default_storage.open(upload.storage_key)
        try:
            return f.read(), None
        finally:
            f.close()

    return None, Response(
        {"error": "Provide either a 'file' upload or an 'upload_id'."},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    import io
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages) or "[No readable text found in PDF]"


def _extract_json_block(text: str):
    """
    Extract the first ```json ... ``` fenced block from an AI response.
    Returns a parsed dict or None.
    """
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _parse_iso_date(date_str):
    """Parse YYYY-MM-DD string to a date object, returning None on failure."""
    if not date_str:
        return None
    try:
        from datetime import date
        return date.fromisoformat(str(date_str))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# POST /api/ai/analyze-contract/   (Professional tier and above)
# ---------------------------------------------------------------------------

class AnalyzeContractView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        ai_tier = get_ai_tier(request.user)
        if ai_tier not in ("advanced", "full"):
            return Response(
                {"error": _("Contract analysis requires a Professional, Business, or Anchor subscription.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        pdf_bytes, err = _get_pdf_bytes(request)
        if err is not None:
            return err

        pdf_text = _extract_pdf_text(pdf_bytes)
        user_message = f"Please analyze this contract:\n\n{pdf_text}"

        conv = AIConversation(user=request.user, conversation_type="contract_help", messages=[])
        conv.messages.append({"role": "user", "content": user_message})

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        api_response = client.messages.create(
            model=AI_MODEL,
            max_tokens=AI_MAX_TOKENS_ANALYSIS,
            system=ANALYZE_CONTRACT_PROMPT,
            messages=list(conv.messages),
        )
        assistant_text = api_response.content[0].text
        conv.messages.append({"role": "assistant", "content": assistant_text})
        conv.save()

        parsed = _extract_json_block(assistant_text) or {}

        return Response({
            "conversation_id": str(conv.id),
            "summary": parsed.get("summary", ""),
            "key_terms": parsed.get("key_terms", {}),
            "red_flags": parsed.get("red_flags", []),
            "questions": parsed.get("questions", []),
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# POST /api/ai/counter-contract/   (Business and Anchor tiers only)
# ---------------------------------------------------------------------------

class CounterContractView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        if not has_feature(request.user, "sol"):
            return Response(
                {"error": _("Contract counter-drafting requires a Business or Anchor subscription.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        pdf_bytes, err = _get_pdf_bytes(request)
        if err is not None:
            return err

        pdf_text = _extract_pdf_text(pdf_bytes)
        user_message = f"Please help me counter this contract:\n\n{pdf_text}"

        conv = AIConversation(user=request.user, conversation_type="contract_help", messages=[])
        conv.messages.append({"role": "user", "content": user_message})

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        api_response = client.messages.create(
            model=AI_MODEL,
            max_tokens=AI_MAX_TOKENS_ANALYSIS,
            system=COUNTER_CONTRACT_PROMPT,
            messages=list(conv.messages),
        )
        assistant_text = api_response.content[0].text
        conv.messages.append({"role": "assistant", "content": assistant_text})
        conv.save()

        parsed = _extract_json_block(assistant_text) or {}

        return Response({
            "conversation_id": str(conv.id),
            "summary": parsed.get("summary", ""),
            "concerning_clauses": parsed.get("concerning_clauses", []),
            "negotiation_strategy": parsed.get("negotiation_strategy", {}),
            "revised_contract": parsed.get("revised_contract", ""),
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# POST /api/ai/import-contract/   (Anchor tier only)
# ---------------------------------------------------------------------------

class ImportContractView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        ai_tier = get_ai_tier(request.user)
        if ai_tier != "full":
            return Response(
                {"error": _("Contract import requires an Anchor subscription.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        pdf_bytes, err = _get_pdf_bytes(request)
        if err is not None:
            return err

        pdf_text = _extract_pdf_text(pdf_bytes)
        # Allow caller to override counterparty_email if AI cannot extract it
        counterparty_override = (request.data.get("counterparty_email") or "").strip() or None

        conv = AIConversation(user=request.user, conversation_type="contract_help", messages=[])
        conv.messages.append({"role": "user", "content": pdf_text})

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        api_response = client.messages.create(
            model=AI_MODEL,
            max_tokens=AI_MAX_TOKENS_ANALYSIS,
            system=IMPORT_CONTRACT_PROMPT,
            messages=list(conv.messages),
        )
        assistant_text = api_response.content[0].text
        conv.messages.append({"role": "assistant", "content": assistant_text})

        extracted = _extract_json_block(assistant_text) or {}

        counterparty_email = (
            counterparty_override
            or extracted.get("counterparty_email")
            or ""
        )
        structure_type = extracted.get("structure_type", "ONE_TIME")
        if structure_type not in ("ONE_TIME", "ONGOING"):
            structure_type = "ONE_TIME"

        obligations_created = []

        with transaction.atomic():
            contract = Contract.objects.create(
                initiator=request.user,
                counterparty_email=counterparty_email,
                structure_type=structure_type,
            )
            conv.contract = contract

            content_snapshot = extracted.get("summary", assistant_text[:2000])
            version = ContractVersion.objects.create(
                contract=contract,
                version_number=1,
                created_by=request.user,
                content_snapshot=content_snapshot,
                status="draft",
            )

            # Look up counterparty user for obligation FKs
            counterparty_user = None
            if counterparty_email:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    counterparty_user = User.objects.get(email=counterparty_email)
                except User.DoesNotExist:
                    counterparty_user = None

            if counterparty_user:
                pay_count = 0
                for obl in extracted.get("payment_obligations", []):
                    due_date = _parse_iso_date(obl.get("due_date"))
                    if due_date is None:
                        due_date = (timezone.now() + timezone.timedelta(days=30)).date()
                    try:
                        amount = float(obl.get("amount") or 0)
                    except (TypeError, ValueError):
                        amount = 0
                    pay_count += 1
                    pay_obl = ContractObligation.objects.create(
                        contract=contract,
                        version=version,
                        obligor=request.user,
                        obligee=counterparty_user,
                        installment_number=pay_count,
                        amount_due=amount,
                        due_date=timezone.make_aware(
                            timezone.datetime.combine(due_date, timezone.datetime.min.time())
                        ),
                    )
                    obligations_created.append({
                        "type": "payment",
                        "id": str(pay_obl.id),
                        "description": obl.get("description", ""),
                        "amount": str(pay_obl.amount_due),
                        "due_date": str(due_date),
                    })

                for obl in extracted.get("service_obligations", []):
                    due_date = _parse_iso_date(obl.get("due_date"))
                    if due_date is None:
                        due_date = (timezone.now() + timezone.timedelta(days=30)).date()
                    svc_obl = ContractServiceObligation.objects.create(
                        contract=contract,
                        version=version,
                        obligor=request.user,
                        obligee=counterparty_user,
                        description=obl.get("description", ""),
                        due_date=timezone.make_aware(
                            timezone.datetime.combine(due_date, timezone.datetime.min.time())
                        ),
                    )
                    obligations_created.append({
                        "type": "service",
                        "id": str(svc_obl.id),
                        "description": svc_obl.description,
                        "due_date": str(due_date),
                    })

        conv.save()

        from backend.billing.gates import can_create_contract, increment_contracts_used, consume_trial_contract
        allowed, _gate_msg = can_create_contract(request.user)
        if allowed:
            increment_contracts_used(request.user)
            consume_trial_contract(request.user)

        return Response({
            "conversation_id": str(conv.id),
            "contract_id": str(contract.id),
            "counterparty_found": counterparty_user is not None,
            "obligations_created": obligations_created,
            "summary": extracted.get("summary", ""),
        }, status=status.HTTP_201_CREATED)
