# backend/api/contracts/prepare_views.py

import json
import re
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from html import unescape

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.activity.log import log_activity
from backend.api.contracts.permissions import contract_party_response, is_party
from backend.api.contracts.serializers import ContractVersionSerializer
from backend.contracts.models import Contract, ContractObligation, ContractServiceObligation, ContractVersion
from backend.contract_pro.models import ContractProOversightEvent
from backend.contract_pro.services import ContractProEditingService, ContractProOversightService
from backend.payments.models import Payment


def _parse_snapshot(raw):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, dict) else {"raw_content": raw or ""}
    except json.JSONDecodeError:
        return {"raw_content": raw or ""}


def _plain_text_from_snapshot(snapshot):
    html = snapshot.get("editor_html") or ""
    if html:
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"</(div|p|h[1-6]|li)>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", unescape(text)).strip()

    clauses = snapshot.get("clauses")
    if isinstance(clauses, list):
        bodies = [str(c.get("body", "")) for c in clauses if isinstance(c, dict)]
        if bodies:
            return "\n\n".join(bodies).strip()

    return str(snapshot.get("raw_content") or snapshot.get("summary") or "").strip()


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def _extract_amount(sentence):
    match = re.search(r"(?:[$]|USD\s*)\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", sentence, re.IGNORECASE)
    return match.group(1).replace(",", "") if match else None


def _extract_date(sentence):
    iso = re.search(r"\b(20[0-9]{2}-[01][0-9]-[0-3][0-9])\b", sentence)
    if iso:
        return iso.group(1)
    phrase = re.search(r"\bwithin\s+([0-9]+\s+(?:day|days|week|weeks|month|months))\b", sentence, re.IGNORECASE)
    return phrase.group(0) if phrase else None


def _extract_summary(text):
    sentences = _sentences(text)
    if not sentences:
        return text[:500].strip()
    return " ".join(sentences[:2])[:800].strip()


def _extract_parties(contract):
    initiator = contract.initiator
    return {
        "initiator": {
            "id": initiator.pk if initiator else None,
            "email": initiator.email if initiator else "",
            "name": str(initiator) if initiator else "",
        },
        "counterparty": {
            "name": contract.counterparty_name,
            "email": contract.counterparty_email,
        },
    }


def _normalize_clause_source(text):
    text = unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(div|p|h[1-6]|li|tr|section)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\r?\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ 	]+", " ", text)
    return text.strip()


def _parse_clause_heading(line):
    line = (line or "").strip().strip(":")
    if not line:
        return None, ""
    match = re.match(r"^(?:(?:section|clause)\s+)?(?P<number>\d+(?:\.\d+)*)(?:[\).:-]\s*|\s+)(?P<title>.+)$", line, re.IGNORECASE)
    if match:
        return match.group("number").strip(), match.group("title").strip()
    if len(line.split()) <= 12 and not line.endswith((".", "!", "?")):
        return None, line
    return None, ""


def _infer_clause_type(title, body):
    text = f"{title or ''} {body or ''}".lower()
    keyword_map = [
        ("payment", ["payment", "pay ", "fee", "invoice", "deposit", "installment", "retainer", "compensation"]),
        ("scope", ["scope", "service", "deliver", "provide", "perform", "work", "deliverable"]),
        ("confidentiality", ["confidential", "non-disclosure", "nda"]),
        ("termination", ["termination", "terminate"]),
        ("liability", ["liability", "indemn", "warranty", "liable"]),
        ("cancellation", ["cancel", "cancellation", "refund", "notice period"]),
        ("risk", ["risk", "assumption of risk"]),
        ("general", ["general", "miscellaneous"]),
    ]
    for clause_type, keywords in keyword_map:
        if any(keyword in text for keyword in keywords):
            return clause_type
    return None


def _extract_clauses(snapshot, draft_text):
    raw_clauses = snapshot.get("clauses")
    clauses = []

    if isinstance(raw_clauses, list) and raw_clauses:
        for index, raw_clause in enumerate(raw_clauses, start=1):
            if not isinstance(raw_clause, dict):
                continue
            title = str(raw_clause.get("title") or "").strip()
            body = str(raw_clause.get("body") or "").strip()
            source_text = str(raw_clause.get("source_text") or body or title or "").strip()
            clause_number = raw_clause.get("clause_number") or raw_clause.get("number")
            clause_type = str(raw_clause.get("clause_type") or "").strip() or None
            order = int(raw_clause.get("order") or index)
            if not clause_type:
                clause_type = _infer_clause_type(title, body)
            clauses.append({
                "clause_key": str(raw_clause.get("clause_key") or f"clause-{order:03d}"),
                "clause_number": str(clause_number).strip() if clause_number not in (None, "") else None,
                "order": order,
                "title": title,
                "body": body or source_text,
                "clause_type": clause_type,
                "source_text": source_text,
                "extracted_metadata": {
                    "extraction_method": raw_clause.get("extraction_method") or "prepared_snapshot",
                    "source": raw_clause.get("source") or "content_snapshot",
                },
            })
        if clauses:
            return clauses

    blocks = [block.strip() for block in re.split(r"\n\s*\n+", draft_text or "") if block.strip()]
    for index, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        first_line = lines[0] if lines else block
        clause_number, heading_title = _parse_clause_heading(first_line)
        if heading_title and len(lines) > 1:
            body = "\n".join(lines[1:]).strip()
            title = heading_title
        elif heading_title and len(lines) == 1:
            body = block.strip()
            title = heading_title
        else:
            title = heading_title if heading_title else ""
            body = block.strip()

        clause_type = _infer_clause_type(title, body)
        clauses.append({
            "clause_key": f"clause-{index:03d}",
            "clause_number": str(clause_number).strip() if clause_number not in (None, "") else None,
            "order": index,
            "title": title,
            "body": body,
            "clause_type": clause_type,
            "source_text": block,
            "extracted_metadata": {
                "extraction_method": "rule_based_mvp",
                "source": "editor_html" if snapshot.get("editor_html") else "draft_text",
            },
        })

    return clauses


def _extract_prepared_terms(clauses, contract=None):
    payment_terms = []
    service_obligations = []
    milestones = []

    for clause in clauses:
        clause_title = clause.get("title") or ""
        clause_body = clause.get("body") or ""
        clause_text = f"{clause_title}\n{clause_body}".strip()
        lowered = clause_text.lower()
        amount = _extract_amount(clause_text)
        due = _extract_date(clause_text)
        clause_key = clause.get("clause_key")

        if clause.get("clause_type") == "payment" or any(word in lowered for word in ["payment", "pay ", "fee", "invoice", "deposit", "installment", "retainer"]) or amount:
            payment_terms.append({
                "clause_key": clause_key,
                "clause_number": clause.get("clause_number"),
                "clause_title": clause_title,
                "clause_type": clause.get("clause_type") or "payment",
                "description": clause_text,
                "amount": amount,
                "due_date": due,
                "responsible_party": "payer/client",
                "trigger_condition": clause_text[:240] or "as stated in draft",
            })

        if clause.get("clause_type") in {"scope", "service", "general"} or any(word in lowered for word in ["shall provide", "shall perform", "deliver", "complete", "service", "scope of"]):
            service_obligations.append({
                "clause_key": clause_key,
                "clause_number": clause.get("clause_number"),
                "clause_title": clause_title,
                "clause_type": clause.get("clause_type") or "scope",
                "description": clause_text,
                "due_date": due,
                "responsible_party": "service provider",
                "trigger_condition": clause_text[:240] or "as stated in draft",
            })

        if any(word in lowered for word in ["milestone", "phase", "deliverable"]):
            milestones.append({
                "clause_key": clause_key,
                "clause_number": clause.get("clause_number"),
                "clause_title": clause_title,
                "description": clause_text,
                "deadline": due,
                "trigger_condition": clause_text[:240] or "as stated in draft",
            })

    deadlines = sorted({item["due_date"] for item in payment_terms + service_obligations if item.get("due_date")})
    if not deadlines:
        deadlines = sorted({item["deadline"] for item in milestones if item.get("deadline")})

    return {
        "summary": _extract_summary("\n\n".join(clause.get("body") or clause.get("title") or "" for clause in clauses)),
        "parties": _extract_parties(contract) if contract else {},
        "clauses": clauses,
        "payment_terms": payment_terms[:20],
        "service_obligations": service_obligations[:20],
        "delivery_obligations": service_obligations[:20],
        "milestones": milestones[:20],
        "deadlines": deadlines,
        "trigger_conditions": ["as stated in draft"] if payment_terms or service_obligations or milestones else [],
        "extraction_method": "rule_based_mvp",
    }


def _to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _as_aware_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    return timezone.make_aware(datetime.combine(value, time.min))


def _due_datetime(raw_due, contract):
    if raw_due:
        parsed = parse_date(str(raw_due))
        if parsed:
            return _as_aware_datetime(parsed)

        relative = re.search(r"within\s+([0-9]+)\s+(day|days|week|weeks|month|months)", str(raw_due), re.IGNORECASE)
        if relative:
            quantity = int(relative.group(1))
            unit = relative.group(2).lower()
            if unit.startswith("week"):
                quantity *= 7
            elif unit.startswith("month"):
                quantity *= 30
            return timezone.now() + timedelta(days=quantity)

    if contract.end_date:
        return _as_aware_datetime(contract.end_date)
    return None


def _counterparty_user(contract):
    if not contract.counterparty_email:
        return None
    User = get_user_model()
    try:
        return User.objects.get(email=contract.counterparty_email)
    except User.DoesNotExist:
        return None


def _delete_prior_pending_prepared_records(contract, version):
    pending_payment_obligations = ContractObligation.objects.filter(contract=contract, state="pending")
    Payment.objects.filter(
        contract=contract,
        status="draft",
        metadata__source="contract_prepare",
    ).delete()
    pending_payment_obligations.delete()
    ContractServiceObligation.objects.filter(contract=contract, state="pending").delete()


def _create_prepared_records(contract, version, prepared_terms, clause_map=None):
    payment_terms = prepared_terms.get("payment_terms") or []
    service_terms = prepared_terms.get("service_obligations") or []
    counterparty = _counterparty_user(contract)

    if (payment_terms or service_terms) and counterparty is None:
        raise ValueError("Cannot prepare lifecycle records until the counterparty email belongs to a registered user.")

    created_payment_obligations = []
    created_service_obligations = []
    created_payments = []
    skipped = []

    _delete_prior_pending_prepared_records(contract, version)

    payment_index = 1
    for term in payment_terms:
        due_at = _due_datetime(term.get("due_date"), contract)
        amount = _to_decimal(term.get("amount"))
        source_clause = None
        if due_at is None:
            skipped.append({"type": "payment", "reason": "missing_due_date", "description": term.get("description", ""), "source_clause_key": term.get("clause_key")})
            continue
        if amount is None:
            skipped.append({"type": "payment", "reason": "missing_amount", "description": term.get("description", ""), "source_clause_key": term.get("clause_key")})
            continue

        obligation = ContractObligation.objects.create(
            contract=contract,
            version=version,
            obligor=counterparty,
            obligee=contract.initiator,
            installment_number=payment_index,
            amount_due=amount,
            currency=contract.currency,
            due_date=due_at,
            state="pending",
        )
        payment = Payment.objects.create(
            contract=contract,
            payment_obligation=obligation,
            payer=counterparty,
            payee=contract.initiator,
            amount=amount,
            currency=contract.currency,
            status="draft",
            payment_method="manual",
            idempotency_key=f"contract_prepare:{contract.id}:{version.id}:payment:{payment_index}",
            metadata={
                "source": "contract_prepare",
                "contract_version_id": str(version.id),
                "term_description": term.get("description", ""),
                "source_clause_key": term.get("clause_key"),
            },
        )
        created_payment_obligations.append({
            "id": str(obligation.id),
            "amount_due": str(obligation.amount_due),
            "currency": obligation.currency,
            "due_date": obligation.due_date.isoformat(),
            "state": obligation.state,
            "payment_id": str(payment.id),
        })
        created_payments.append({
            "id": str(payment.id),
            "amount": str(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "payment_obligation_id": str(obligation.id),
        })
        payment_index += 1

    for term in service_terms:
        due_at = _due_datetime(term.get("due_date"), contract)
        source_clause = None
        if due_at is None:
            skipped.append({"type": "service", "reason": "missing_due_date", "description": term.get("description", ""), "source_clause_key": term.get("clause_key")})
            continue

        obligation = ContractServiceObligation.objects.create(
            contract=contract,
            version=version,
            obligor=contract.initiator,
            obligee=counterparty,
            description=term.get("description", ""),
            due_date=due_at,
            state="pending",
        )
        created_service_obligations.append({
            "id": str(obligation.id),
            "description": obligation.description,
            "due_date": obligation.due_date.isoformat(),
            "state": obligation.state,
        })

    return {
        "payment_obligations": created_payment_obligations,
        "service_obligations": created_service_obligations,
        "payments": created_payments,
        "skipped": skipped,
    }


class ContractPrepareAPIView(APIView):
    """
    POST /api/contracts/<contract_id>/prepare/

    Extracts structured pre-send terms from the latest draft version, stores
    them in a prepared ContractVersion snapshot, and persists planned lifecycle
    records. It does not mark contracts or obligations active.
    """

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()
        if contract.initiator_id != request.user.pk:
            return Response({"error": "Only the contract initiator may prepare this contract."}, status=status.HTTP_403_FORBIDDEN)
        if not ContractProEditingService.owner_editing_allowed(contract, request.user):
            if contract.entity_id is not None:
                ContractProOversightService.record(
                    event_type=ContractProOversightEvent.EVENT_OWNER_EDIT_BLOCKED,
                    business=contract.entity,
                    contract=contract,
                    actor=request.user,
                )
            return Response({"error": "Direct editing is not allowed while an active Contract Pro delegation controls this contract."}, status=status.HTTP_403_FORBIDDEN)
        if contract.versions.filter(status="signed").exists():
            return Response({"error": "This contract is locked — it has a signed version."}, status=status.HTTP_403_FORBIDDEN)

        latest = contract.versions.order_by("-version_number").first()
        existing_count = contract.versions.count()
        if existing_count > 1:
            return Response(
                {"error": "Only draft Version 1 can be prepared. Later versions must use the negotiation flow."},
                status=status.HTTP_409_CONFLICT,
            )
        if existing_count >= contract.max_versions and latest is None:
            return Response({"error": f"Maximum version limit reached ({contract.max_versions})."}, status=status.HTTP_409_CONFLICT)

        request_html = str(request.data.get("editor_html") or "").strip()
        request_sections = request.data.get("sections")
        snapshot = _parse_snapshot(latest.content_snapshot) if latest else {}
        if request_html:
            snapshot["editor_html"] = request_html
        if isinstance(request_sections, list):
            snapshot["sections"] = request_sections

        draft_text = str(request.data.get("draft_text") or "").strip() or _plain_text_from_snapshot(snapshot)
        if not draft_text:
            return Response({"error": "No draft content found to prepare."}, status=status.HTTP_400_BAD_REQUEST)

        clause_candidates = _extract_clauses(snapshot, draft_text)
        prepared_terms = _extract_prepared_terms(clause_candidates, contract)
        prepared_terms.pop("clauses", None)
        try:
            with transaction.atomic():
                if latest:
                    if latest.version_number != 1 or latest.status != "draft":
                        return Response(
                            {"error": "Only an editable draft Version 1 can be prepared."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    version = latest
                else:
                    version = ContractVersion.objects.create(
                        contract=contract,
                        version_number=1,
                        created_by=request.user,
                        previous_version=None,
                        content_snapshot="",
                        status="draft",
                    )

                created_records = _create_prepared_records(contract, version, prepared_terms, None)

                prepared_snapshot = dict(snapshot)
                prepared_snapshot["source"] = "contract_prepare"
                prepared_snapshot["prepared_terms"] = prepared_terms
                prepared_snapshot["prepared_summary"] = {
                    "payment_terms_count": len(prepared_terms["payment_terms"]),
                    "service_obligations_count": len(prepared_terms["service_obligations"]),
                    "milestones_count": len(prepared_terms["milestones"]),
                    "payment_obligations_created": len(created_records["payment_obligations"]),
                    "service_obligations_created": len(created_records["service_obligations"]),
                    "payments_created": len(created_records["payments"]),
                    "skipped_count": len(created_records["skipped"]),
                }
                ContractVersion.objects.filter(pk=version.pk).update(content_snapshot=json.dumps(prepared_snapshot))
                version.refresh_from_db()

                contract.status = "draft"
                contract.state = "prepared"
                contract.save(update_fields=["status", "state"])
                log_activity(
                    contract=contract,
                    user=request.user,
                    activity_type="contract_updated",
                    description="Contract prepared for sending.",
                    metadata={
                        "version_id": str(version.id),
                        "prepared_summary": prepared_snapshot["prepared_summary"],
                        "created_records": created_records,
                    },
                )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response({
            "contract_id": str(contract.id),
            "state": contract.state,
            "status": contract.status,
            "version": ContractVersionSerializer(version).data,
            "prepared_terms": prepared_terms,
            "prepared_summary": prepared_snapshot["prepared_summary"],
            "created_records": created_records,
        }, status=status.HTTP_200_OK)
