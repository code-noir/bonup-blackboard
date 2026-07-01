# backend/api/contracts/prepare_views.py

import hashlib
import json
import logging
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
from backend.contracts.models import (
    Contract,
    ContractExtractionCandidate,
    ContractExtractionRun,
    ContractObligation,
    ContractServiceObligation,
    ContractVersion,
)
from backend.contract_pro.models import ContractProOversightEvent
from backend.contract_pro.services import ContractProEditingService, ContractProOversightService
from backend.payments.models import Payment

logger = logging.getLogger(__name__)

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

def _prepare_shadow_source_hash(snapshot, draft_text, prepared_terms):
    source_payload = {
        "draft_text": draft_text or "",
        "editor_html": snapshot.get("editor_html") or "",
        "raw_content": snapshot.get("raw_content") or "",
        "sections": snapshot.get("sections") if isinstance(snapshot.get("sections"), list) else [],
        "summary": snapshot.get("summary") or "",
        "prepared_terms": prepared_terms or {},
    }
    encoded = json.dumps(source_payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

MONTH_NAME_RE = re.compile(
    r"\b(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+"
    r"(?P<day>\d{1,2}),\s*(?P<year>20\d{2})\b",
    re.IGNORECASE,
)

MONTH_NUMBERS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

def _candidate_title(term, fallback):
    title = str(term.get("title") or term.get("clause_title") or "").strip()
    if not title:
        description = str(term.get("description") or "").strip()
        title = description[:80].strip()
    return (title or fallback)[:255]

def _candidate_due_date(raw_due, contract):
    due_at = _due_datetime(raw_due, contract)
    return due_at.date() if due_at else None

def _candidate_missing_terms(term, required_fields, due_date=None, amount=None):
    missing = []
    for field in required_fields:
        if field == "due_date":
            if due_date is None:
                missing.append(field)
            continue
        if field == "amount":
            if amount is None:
                missing.append(field)
            continue
        if term.get(field) in (None, ""):
            missing.append(field)
    return missing

def _candidate_metadata(prepared_terms_key, index, original_model, extra=None):
    metadata = {
        "shadow_write": True,
        "source": "prepare",
        "prepared_terms_key": prepared_terms_key,
        "prepared_terms_index": index,
        "original_model": original_model,
    }
    if extra:
        metadata.update(extra)
    return metadata

def _candidate_source_location(term):
    location = {}
    if term.get("clause_number"):
        location["clause_number"] = term.get("clause_number")
    if term.get("clause_title"):
        location["clause_title"] = term.get("clause_title")
    if term.get("clause_type"):
        location["clause_type"] = term.get("clause_type")
    return location

def _shadow_source_text(prepared_terms, draft_text):
    if draft_text:
        return draft_text
    descriptions = []
    for key in ("payment_terms", "service_obligations", "milestones"):
        for term in prepared_terms.get(key) or []:
            if isinstance(term, dict) and term.get("description"):
                descriptions.append(str(term["description"]))
    return "\n".join(descriptions)

def _shadow_sentences(source_text):
    normalized = _normalize_clause_source(source_text)
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [part.strip() for part in parts if len(part.strip()) > 8]

def _parse_shadow_roles(source_text, contract):
    roles = {}
    for match in re.finditer(r"^\s*(?P<label>client|contractor|customer|provider|owner)\s*:\s*(?P<name>[^\n]+?)\s*$", source_text or "", re.IGNORECASE | re.MULTILINE):
        label = match.group("label").strip().title()
        name = match.group("name").strip().rstrip(".")
        roles[label.lower()] = {"label": label, "name": name, "display": f"{label} / {name}"}

    if "client" not in roles and contract.initiator:
        roles["client"] = {"label": "Client", "name": str(contract.initiator), "display": f"Client / {contract.initiator}"}
    if "contractor" not in roles and (contract.counterparty_name or contract.counterparty_email):
        name = contract.counterparty_name or contract.counterparty_email
        roles["contractor"] = {"label": "Contractor", "name": name, "display": f"Contractor / {name}"}
    return roles

def _role_display(roles, role, fallback=""):
    value = roles.get(role)
    if value:
        return value["display"]
    return fallback

def _extract_fixed_due_date(text):
    iso = re.search(r"\b(20[0-9]{2}-[01][0-9]-[0-3][0-9])\b", text or "")
    if iso:
        return parse_date(iso.group(1))

    match = MONTH_NAME_RE.search(text or "")
    if not match:
        return None
    month_key = match.group("month").lower().rstrip(".")
    month = MONTH_NUMBERS.get(month_key)
    if not month:
        return None
    try:
        return datetime(int(match.group("year")), month, int(match.group("day"))).date()
    except ValueError:
        return None

def _extract_relative_due_rule(text):
    match = re.search(
        r"\bwithin\s+(?P<amount>\d+)\s+(?P<unit>day|days|week|weeks|month|months)"
        r"(?:\s+(?P<direction>after|before)\s+(?P<event>[^.]+?))?(?:\.|$)",
        text or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    event = (match.group("event") or "").strip()
    if not event and "delivery" in (text or "").lower():
        event = "delivery"
    return {
        "amount": int(match.group("amount")),
        "unit": match.group("unit").lower().rstrip("s") + "s",
        "direction": (match.group("direction") or "after").lower(),
        "event": event,
    }

def _extract_due_trigger(text):
    match = re.search(r"\bwhen\s+(?P<trigger>[^.]+?)(?:\.|$)", text or "", re.IGNORECASE)
    if not match:
        return ""
    trigger = match.group("trigger").strip()
    return f"when {trigger}"

def _extract_all_amounts(text):
    amounts = []
    for match in re.finditer(r"(?P<currency>\$|USD\s*)\s*(?P<amount>[0-9][0-9,]*(?:\.[0-9]{2})?)", text or "", re.IGNORECASE):
        amounts.append({
            "raw": match.group(0).strip(),
            "amount": match.group("amount").replace(",", ""),
            "currency": "USD" if match.group("currency").strip().upper().startswith("USD") or match.group("currency") == "$" else match.group("currency").strip(),
        })
    return amounts

def _money_title_amount(amount_info):
    raw = amount_info.get("raw") or ""
    if raw.startswith("$"):
        return raw
    amount = amount_info.get("amount") or ""
    if not amount:
        return raw
    whole, dot, cents = amount.partition(".")
    try:
        whole = f"{int(whole):,}"
    except ValueError:
        pass
    return f"${whole}{dot}{cents}"

def _object_from_text(text):
    lowered = (text or "").lower()
    object_patterns = [
        ("homepage mockup", "homepage mockup"),
        ("full website", "full website"),
        ("five-page business website", "five-page business website"),
        ("reasonable bugs", "reasonable bugs"),
        ("each delivery", "each delivery"),
        ("loan funds", "loan funds"),
    ]
    for key, value in object_patterns:
        if key in lowered:
            return value
    deliver = re.search(r"\bdeliver\s+(?:the\s+)?(?P<object>.+?)(?:\s+by\s+|\s+within\s+|\.|$)", text or "", re.IGNORECASE)
    if deliver:
        return deliver.group("object").strip()
    pay_for = re.search(r"\bfor\s+(?:the\s+)?(?P<object>.+?)(?:\s+when\s+|\.|$)", text or "", re.IGNORECASE)
    if pay_for:
        return pay_for.group("object").strip()
    return ""

def _title_for_shadow_sentence(candidate_type, sentence, amount_info=None):
    lowered = sentence.lower()
    obj = _object_from_text(sentence)
    if candidate_type == ContractExtractionCandidate.TYPE_PAYMENT:
        amount = _money_title_amount(amount_info or {})
        if "homepage mockup" in lowered:
            return f"Pay {amount} for homepage mockup"
        if "full website" in lowered:
            return f"Pay {amount} for full website"
        return f"Pay {amount}".strip()
    if re.search(r"\bdeliver\b", lowered) and obj:
        return f"Deliver {obj}"
    if "fix" in lowered and "bug" in lowered:
        return "Fix reasonable bugs after delivery"
    if "review" in lowered and "delivery" in lowered:
        return "Review each delivery"
    if "provide" in lowered and obj:
        return f"Provide {obj}"
    if "design" in lowered and obj:
        return f"Design {obj}"
    return sentence[:80].strip()

def _sentence_candidate_type(sentence):
    lowered = sentence.lower()
    if _extract_all_amounts(sentence) or re.search(r"\bpay\b|\bpayment\b", lowered):
        return ContractExtractionCandidate.TYPE_PAYMENT
    if "client" in lowered and "review" in lowered:
        return ContractExtractionCandidate.TYPE_RESPONSIBILITY
    if "contractor" in lowered and any(word in lowered for word in ["deliver", "fix", "provide", "perform", "must"]):
        return ContractExtractionCandidate.TYPE_SERVICE_WORK
    if any(word in lowered for word in ["deliver", "fix", "provide", "perform"]):
        return ContractExtractionCandidate.TYPE_SERVICE_WORK
    if _extract_fixed_due_date(sentence):
        return ContractExtractionCandidate.TYPE_DEADLINE
    return ""

def _shadow_parties_for_sentence(sentence, candidate_type, roles, contract):
    lowered = sentence.lower()
    client = _role_display(roles, "client", str(contract.initiator) if contract.initiator else "")
    contractor = _role_display(roles, "contractor", contract.counterparty_name or contract.counterparty_email or "")

    if candidate_type == ContractExtractionCandidate.TYPE_PAYMENT:
        return client or "payer/client", contractor
    if candidate_type == ContractExtractionCandidate.TYPE_RESPONSIBILITY:
        if "client" in lowered:
            return client, contractor
        return "", ""
    if candidate_type == ContractExtractionCandidate.TYPE_SERVICE_WORK:
        if "contractor" in lowered:
            return contractor, client
        return contractor or "service provider", client
    return "", ""

def _raw_sentence_payload(sentence, source_index, amount_info=None, due_trigger="", relative_due=None):
    payload = {"sentence": sentence, "source_index": source_index}
    if amount_info:
        payload["amount"] = amount_info.get("amount")
        payload["amount_raw"] = amount_info.get("raw")
    if due_trigger:
        payload["due_trigger"] = due_trigger
    if relative_due:
        payload["relative_due"] = relative_due
    return payload

def _metadata_for_shadow_sentence(index, original_model, extra=None):
    metadata = {
        "shadow_write": True,
        "source": "prepare",
        "prepared_terms_key": "draft_text_sentences",
        "prepared_terms_index": index,
        "original_model": original_model,
        "extraction_level": "sentence",
    }
    if extra:
        metadata.update(extra)
    return metadata

def _build_sentence_shadow_candidates(contract, version, run, prepared_terms, draft_text):
    source_text = _shadow_source_text(prepared_terms, draft_text)
    roles = _parse_shadow_roles(source_text, contract)
    candidates = []

    for index, sentence in enumerate(_shadow_sentences(source_text), start=1):
        lowered = sentence.lower()
        if re.match(r"^(website design service agreement|client:\s*|contractor:\s*)", sentence, re.IGNORECASE):
            continue
        if re.match(r"^[A-Z][A-Za-z /-]{2,60} Terms\.$", sentence):
            continue
        candidate_type = _sentence_candidate_type(sentence)
        if not candidate_type:
            continue
        if "agrees to design" in lowered and not _extract_fixed_due_date(sentence) and not _extract_relative_due_rule(sentence):
            continue

        fixed_due_date = _extract_fixed_due_date(sentence)
        relative_due = _extract_relative_due_rule(sentence)
        due_trigger = _extract_due_trigger(sentence)
        responsible_party, beneficiary_party = _shadow_parties_for_sentence(sentence, candidate_type, roles, contract)
        metadata_extra = {}
        if due_trigger:
            metadata_extra["due_trigger"] = due_trigger
        if relative_due:
            metadata_extra["relative_due"] = relative_due
        metadata_extra["role_map"] = roles

        if candidate_type == ContractExtractionCandidate.TYPE_PAYMENT:
            amounts = _extract_all_amounts(sentence) or [{"raw": "", "amount": None, "currency": contract.currency or ""}]
            for amount_index, amount_info in enumerate(amounts, start=1):
                amount = _to_decimal(amount_info.get("amount"))
                missing_terms = [] if amount is not None else ["amount"]
                candidates.append(ContractExtractionCandidate(
                    run=run,
                    contract=contract,
                    contract_version=version,
                    candidate_type=candidate_type,
                    title=_title_for_shadow_sentence(candidate_type, sentence, amount_info),
                    description=sentence,
                    responsible_party=responsible_party,
                    beneficiary_party=beneficiary_party,
                    due_date=fixed_due_date if not (due_trigger or relative_due) else None,
                    amount=amount,
                    currency=amount_info.get("currency") or contract.currency or "",
                    source_clause_text=sentence,
                    source_clause_key=f"sentence-{index:03d}",
                    source_location={"sentence_index": index, "amount_index": amount_index},
                    missing_terms=missing_terms,
                    raw_payload=_raw_sentence_payload(sentence, index, amount_info, due_trigger, relative_due),
                    metadata=_metadata_for_shadow_sentence(index, "ContractObligation", metadata_extra),
                ))
            continue

        original_model = "ContractServiceObligation" if candidate_type == ContractExtractionCandidate.TYPE_SERVICE_WORK else "prepared_terms.responsibility"
        candidates.append(ContractExtractionCandidate(
            run=run,
            contract=contract,
            contract_version=version,
            candidate_type=candidate_type,
            title=_title_for_shadow_sentence(candidate_type, sentence),
            description=sentence,
            responsible_party=responsible_party,
            beneficiary_party=beneficiary_party,
            due_date=fixed_due_date if not relative_due else None,
            currency=contract.currency or "",
            source_clause_text=sentence,
            source_clause_key=f"sentence-{index:03d}",
            source_location={"sentence_index": index},
            missing_terms=[],
            raw_payload=_raw_sentence_payload(sentence, index, relative_due=relative_due),
            metadata=_metadata_for_shadow_sentence(index, original_model, metadata_extra),
        ))

    return candidates

def _build_prepared_term_shadow_candidates(contract, version, run, prepared_terms):
    candidates = []
    represented_deadlines = set()
    represented_clause_keys = set()

    for index, term in enumerate(prepared_terms.get("payment_terms") or [], start=1):
        if not isinstance(term, dict):
            continue
        raw_due = term.get("due_date")
        if raw_due:
            represented_deadlines.add(str(raw_due))
        if term.get("clause_key"):
            represented_clause_keys.add(str(term.get("clause_key")))
        due_date = _candidate_due_date(raw_due, contract)
        amount = _to_decimal(term.get("amount"))
        candidates.append(ContractExtractionCandidate(
            run=run,
            contract=contract,
            contract_version=version,
            candidate_type=ContractExtractionCandidate.TYPE_PAYMENT,
            title=_candidate_title(term, f"Payment term {index}"),
            description=term.get("description", ""),
            responsible_party=term.get("responsible_party", ""),
            beneficiary_party=str(contract.initiator) if contract.initiator else "",
            due_date=due_date,
            amount=amount,
            currency=term.get("currency") or contract.currency or "",
            source_clause_text=term.get("description", "") or term.get("trigger_condition", ""),
            source_clause_key=term.get("clause_key") or "",
            source_location=_candidate_source_location(term),
            missing_terms=_candidate_missing_terms(term, ["amount", "due_date"], due_date=due_date, amount=amount),
            raw_payload=term,
            metadata=_candidate_metadata("payment_terms", index, "ContractObligation"),
        ))

    for index, term in enumerate(prepared_terms.get("service_obligations") or [], start=1):
        if not isinstance(term, dict):
            continue
        raw_due = term.get("due_date")
        if raw_due:
            represented_deadlines.add(str(raw_due))
        if term.get("clause_key"):
            represented_clause_keys.add(str(term.get("clause_key")))
        due_date = _candidate_due_date(raw_due, contract)
        candidates.append(ContractExtractionCandidate(
            run=run,
            contract=contract,
            contract_version=version,
            candidate_type=ContractExtractionCandidate.TYPE_SERVICE_WORK,
            title=_candidate_title(term, f"Service obligation {index}"),
            description=term.get("description", ""),
            responsible_party=term.get("responsible_party", ""),
            beneficiary_party=contract.counterparty_name or contract.counterparty_email or "",
            due_date=due_date,
            currency=term.get("currency") or contract.currency or "",
            source_clause_text=term.get("description", "") or term.get("trigger_condition", ""),
            source_clause_key=term.get("clause_key") or "",
            source_location=_candidate_source_location(term),
            missing_terms=_candidate_missing_terms(term, ["description", "due_date"], due_date=due_date),
            raw_payload=term,
            metadata=_candidate_metadata("service_obligations", index, "ContractServiceObligation"),
        ))

    for index, term in enumerate(prepared_terms.get("milestones") or [], start=1):
        if not isinstance(term, dict):
            continue
        clause_key = str(term.get("clause_key") or "")
        if clause_key and clause_key in represented_clause_keys:
            continue
        raw_due = term.get("deadline") or term.get("due_date")
        due_date = _candidate_due_date(raw_due, contract)
        candidates.append(ContractExtractionCandidate(
            run=run,
            contract=contract,
            contract_version=version,
            candidate_type=ContractExtractionCandidate.TYPE_DEADLINE if due_date else ContractExtractionCandidate.TYPE_OTHER,
            title=_candidate_title(term, f"Milestone {index}"),
            description=term.get("description", ""),
            due_date=due_date,
            currency=contract.currency or "",
            source_clause_text=term.get("description", "") or term.get("trigger_condition", ""),
            source_clause_key=term.get("clause_key") or "",
            source_location=_candidate_source_location(term),
            missing_terms=_candidate_missing_terms(term, ["description", "due_date"], due_date=due_date),
            raw_payload=term,
            metadata=_candidate_metadata("milestones", index, "prepared_terms.milestones"),
        ))

    for index, raw_deadline in enumerate(prepared_terms.get("deadlines") or [], start=1):
        if not raw_deadline or str(raw_deadline) in represented_deadlines:
            continue
        due_date = _candidate_due_date(raw_deadline, contract)
        candidates.append(ContractExtractionCandidate(
            run=run,
            contract=contract,
            contract_version=version,
            candidate_type=ContractExtractionCandidate.TYPE_DEADLINE,
            title=f"Deadline {raw_deadline}"[:255],
            description=str(raw_deadline),
            due_date=due_date,
            currency=contract.currency or "",
            missing_terms=[] if due_date else ["due_date"],
            raw_payload={"deadline": raw_deadline},
            metadata=_candidate_metadata("deadlines", index, "prepared_terms.deadlines"),
        ))

    return candidates

def _build_prepare_shadow_candidates(contract, version, run, prepared_terms, draft_text=""):
    sentence_candidates = _build_sentence_shadow_candidates(contract, version, run, prepared_terms, draft_text)
    if sentence_candidates:
        return sentence_candidates
    return _build_prepared_term_shadow_candidates(contract, version, run, prepared_terms)

def _persist_prepare_extraction_shadow(contract, version, snapshot, draft_text, prepared_terms, created_records, user):
    source_hash = _prepare_shadow_source_hash(snapshot, draft_text, prepared_terms)
    existing_run = ContractExtractionRun.objects.filter(
        contract=contract,
        contract_version=version,
        stage=ContractExtractionRun.STAGE_PREPARE,
        source_hash=source_hash,
        status=ContractExtractionRun.STATUS_COMPLETED,
    ).first()
    if existing_run:
        return existing_run

    ContractExtractionRun.objects.filter(
        contract=contract,
        contract_version=version,
        stage=ContractExtractionRun.STAGE_PREPARE,
    ).exclude(source_hash=source_hash).exclude(status=ContractExtractionRun.STATUS_SUPERSEDED).update(
        status=ContractExtractionRun.STATUS_SUPERSEDED,
    )

    run = ContractExtractionRun.objects.create(
        contract=contract,
        contract_version=version,
        stage=ContractExtractionRun.STAGE_PREPARE,
        source_kind=ContractExtractionRun.SOURCE_EDITOR_HTML,
        source_hash=source_hash,
        engine_name="prepare_shadow_extractor",
        engine_version="v1",
        status=ContractExtractionRun.STATUS_COMPLETED,
        warnings=list(created_records.get("skipped") or []),
        metadata={
            "shadow_write": True,
            "prepare_version_id": str(version.id),
            "prepared_terms_keys": sorted(prepared_terms.keys()),
            "source": "ContractPrepareAPIView",
        },
        created_by=user,
        completed_at=timezone.now(),
    )

    for candidate in _build_prepare_shadow_candidates(contract, version, run, prepared_terms, draft_text):
        candidate.save()

    return run

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

                try:
                    with transaction.atomic():
                        _persist_prepare_extraction_shadow(
                            contract,
                            version,
                            prepared_snapshot,
                            draft_text,
                            prepared_terms,
                            created_records,
                            request.user,
                        )
                except Exception:
                    logger.exception("Prepare extraction shadow persistence failed for contract %s", contract.id)

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
