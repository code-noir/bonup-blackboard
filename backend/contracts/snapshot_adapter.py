"""Read-only adapter for legacy and current contract content snapshots."""

from __future__ import annotations

import json
import re
from html import unescape

from .schema import (
    SOURCE_TYPE_EDITOR_HTML,
    SOURCE_TYPE_FINAL_EDITOR_HTML,
    SOURCE_TYPE_LEGACY_TEXT,
    SOURCE_TYPE_PREPARED_TERMS,
    SOURCE_TYPE_RAW_CONTENT,
    SOURCE_TYPE_SECTIONS,
    SOURCE_TYPE_TEMPLATE_CLAUSES,
    empty_schema,
    make_missing_field,
    make_source_provenance,
)

_ROMAN_NUMERAL_RE = r"[IVXLCDM]+"
_HEADING_PREFIX_RE = re.compile(
    rf"^(?:(?:section|article|clause)\s+)?(?P<number>\d+(?:\.\d+)*|{_ROMAN_NUMERAL_RE})(?:\s*[\).:-]\s+|\s+-\s+|\s+)(?P<title>.+)$",
    re.IGNORECASE,
)
_UPPERCASE_HEADING_WORDS = {
    "PARTIES",
    "SCOPE OF SERVICES",
    "SERVICES",
    "SERVICE SCHEDULE",
    "SERVICE OBLIGATIONS",
    "PAYMENT TERMS",
    "COMPENSATION",
    "FEES",
    "LATE PAYMENT",
    "TERMINATION",
    "CANCELLATION",
    "INSURANCE",
    "CONFIDENTIALITY",
    "DISPUTE RESOLUTION",
    "GOVERNING LAW",
    "NOTICES",
    "CHANGE ORDERS",
    "CHANGE ORDER",
    "SIGNATURES",
}
_SIGNATURE_HEADING_RE = re.compile(r"^(signature|signatures|signed by|in witness whereof)\b", re.IGNORECASE)
_ADDRESS_HINT_RE = re.compile(r"\b(street|st\.?|avenue|ave\.?|road|rd\.?|drive|dr\.?|lane|ln\.?|boulevard|blvd\.?|miami|florida|\d{5})\b", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"\{\{\s*[^{}]+?\s*\}\}|\[[A-Z0-9][A-Z0-9 _/-]{1,80}\]|_{3,}")
_AMOUNT_RE = re.compile(r"(?P<currency>\$|USD\s*)\s*(?P<amount>\d[\d,]*(?:\.\d{2})?)", re.IGNORECASE)


def normalize_content_snapshot(content_snapshot, contract=None, version=None) -> dict:
    """Return a canonical BlackboardContractSchema dict for any known snapshot shape.

    This adapter is intentionally read-only. It does not mutate the provided
    contract/version and is not wired into current runtime behavior.
    """
    schema = empty_schema()
    _apply_contract_context(schema, contract)
    if version is not None:
        schema["extraction_report"]["version_id"] = str(getattr(version, "pk", "") or "")
        schema["extraction_report"]["version_number"] = getattr(version, "version_number", None)

    snapshot, raw_text, warnings = _coerce_snapshot(content_snapshot)
    for warning in warnings:
        _warn(schema, warning)

    if content_snapshot is None:
        _warn(schema, "content_snapshot is empty.")
        _record_unresolved_defaults(schema)
        return schema

    if isinstance(snapshot, dict):
        _normalize_dict_snapshot(schema, snapshot, raw_text)
    else:
        _set_render_cache(schema, "raw_content", raw_text)
        _add_source_type(schema, SOURCE_TYPE_LEGACY_TEXT)
        _clauses_from_text(schema, raw_text, SOURCE_TYPE_LEGACY_TEXT, "content_snapshot")

    _post_process_schema(schema)
    _record_unresolved_defaults(schema)
    return schema


def _coerce_snapshot(content_snapshot):
    if content_snapshot is None:
        return {}, "", []

    if isinstance(content_snapshot, dict):
        return content_snapshot, "", []

    raw = str(content_snapshot)
    stripped = raw.strip()
    if not stripped:
        return {}, raw, ["content_snapshot is blank."]

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        if stripped[:1] in ("{", "["):
            return None, raw, ["content_snapshot looked like JSON but could not be parsed."]
        return None, raw, []

    if isinstance(parsed, dict):
        return parsed, raw, []

    return None, raw, ["content_snapshot JSON did not decode to an object."]


def _normalize_dict_snapshot(schema, snapshot, raw_text):
    if raw_text:
        _set_render_cache(schema, "raw_content", raw_text)

    editor_html = _string(snapshot.get("editor_html"))
    final_editor_html = _string(snapshot.get("final_editor_html"))
    raw_content = _string(snapshot.get("raw_content"))
    summary = _string(snapshot.get("summary"))
    sections = snapshot.get("sections")
    clauses = snapshot.get("clauses")
    prepared_terms = snapshot.get("prepared_terms")

    if editor_html:
        _set_render_cache(schema, "editor_html", editor_html)
        _add_source_type(schema, SOURCE_TYPE_EDITOR_HTML)

    if final_editor_html:
        _set_render_cache(schema, "final_editor_html", final_editor_html)
        _add_source_type(schema, SOURCE_TYPE_FINAL_EDITOR_HTML)
        schema["source_provenance"].append(
            make_source_provenance(
                SOURCE_TYPE_FINAL_EDITOR_HTML,
                "final_editor_html",
                extraction_method="preserved_render_cache",
                raw_excerpt=_excerpt(_html_to_text(final_editor_html)),
            )
        )

    if isinstance(sections, list):
        schema["render_cache"]["sections"] = _normalize_sections(sections)
        _add_source_type(schema, SOURCE_TYPE_SECTIONS)
        _clauses_from_sections(schema, sections)

    if isinstance(prepared_terms, dict):
        schema["render_cache"]["prepared_terms"] = prepared_terms
        _add_source_type(schema, SOURCE_TYPE_PREPARED_TERMS)
        _participants_from_prepared_terms(schema, prepared_terms)
        _obligations_from_prepared_terms(schema, prepared_terms)

    if isinstance(clauses, list) and clauses:
        _add_source_type(schema, SOURCE_TYPE_TEMPLATE_CLAUSES)
        _clauses_from_snapshot_clauses(schema, clauses)
    elif not schema["clauses"]:
        source_text = ""
        source_type = ""
        source_field = ""
        if editor_html:
            source_text = _html_to_text(editor_html)
            source_type = SOURCE_TYPE_EDITOR_HTML
            source_field = "editor_html"
        elif raw_content:
            source_text = raw_content
            source_type = SOURCE_TYPE_RAW_CONTENT
            source_field = "raw_content"
            _set_render_cache(schema, "raw_content", raw_content)
            _add_source_type(schema, SOURCE_TYPE_RAW_CONTENT)
        elif summary:
            source_text = summary
            source_type = SOURCE_TYPE_RAW_CONTENT
            source_field = "summary"
            _add_source_type(schema, SOURCE_TYPE_RAW_CONTENT)

        if source_text:
            _clauses_from_text(schema, source_text, source_type, source_field)

    plain_text = _html_to_text(editor_html) if editor_html else raw_content or summary
    if plain_text:
        _set_render_cache(schema, "plain_text", plain_text)


def _apply_contract_context(schema, contract):
    if contract is None:
        return

    identity = schema["contract_identity"]
    for key in (
        "title",
        "contract_type",
        "description",
        "structure_type",
        "currency",
        "jurisdiction",
        "governing_law",
    ):
        identity[key] = _string(getattr(contract, key, ""))
    identity["start_date"] = _date_string(getattr(contract, "start_date", None))
    identity["end_date"] = _date_string(getattr(contract, "end_date", None))
    identity["source_type"] = "contract_model"

    initiator = getattr(contract, "initiator", None)
    if initiator is not None:
        schema["participants"].append(
            {
                "id": f"user:{getattr(initiator, 'pk', '')}",
                "role": "initiator",
                "display_name": _display_name(initiator),
                "legal_name": _display_name(initiator),
                "email": _string(getattr(initiator, "email", "")),
                "address": "",
                "party_type": "person",
                "source": "contract.initiator",
                "unresolved_fields": [],
            }
        )

    counterparty_email = _string(getattr(contract, "counterparty_email", ""))
    counterparty_name = _string(getattr(contract, "counterparty_name", ""))
    if counterparty_email or counterparty_name:
        unresolved = []
        if not counterparty_name:
            unresolved.append("legal_name")
        if not counterparty_email:
            unresolved.append("email")
        schema["participants"].append(
            {
                "id": "counterparty",
                "role": "counterparty",
                "display_name": counterparty_name or counterparty_email,
                "legal_name": counterparty_name,
                "email": counterparty_email,
                "address": "",
                "party_type": "unknown",
                "source": "contract.counterparty",
                "unresolved_fields": unresolved,
            }
        )


def _participants_from_prepared_terms(schema, prepared_terms):
    parties = prepared_terms.get("parties")
    if not isinstance(parties, dict):
        return

    for role in ("initiator", "counterparty"):
        raw = parties.get(role)
        if not isinstance(raw, dict):
            continue
        email = _string(raw.get("email"))
        name = _string(raw.get("name")) or email
        if not name and not email:
            continue
        if _has_participant(schema, role, email):
            continue
        schema["participants"].append(
            {
                "id": f"prepared:{role}",
                "role": role,
                "display_name": name,
                "legal_name": name,
                "email": email,
                "address": _string(raw.get("address")),
                "party_type": "unknown",
                "source": "prepared_terms.parties",
                "unresolved_fields": [],
            }
        )


def _obligations_from_prepared_terms(schema, prepared_terms):
    for index, term in enumerate(prepared_terms.get("payment_terms") or [], start=1):
        if not isinstance(term, dict):
            continue
        schema["payment_obligations"].append(
            {
                "id": f"payment-{index:03d}",
                "description": _string(term.get("description")),
                "amount": _nullable_string(term.get("amount")),
                "currency": _string(term.get("currency")),
                "payer": _string(term.get("responsible_party")),
                "payee": "",
                "frequency": None,
                "invoice_rule": "",
                "due_date_rule": _nullable_string(term.get("due_date")),
                "payment_method": "",
                "trigger_condition": _string(term.get("trigger_condition")),
                "recurrence": None,
                "source_clause_id": _nullable_string(term.get("clause_key")),
                "missing_fields": _missing_obligation_fields(term, ["amount", "due_date"]),
                "source": "prepared_terms.payment_terms",
            }
        )

    service_terms = prepared_terms.get("service_obligations") or prepared_terms.get("delivery_obligations") or []
    for index, term in enumerate(service_terms, start=1):
        if not isinstance(term, dict):
            continue
        schema["service_obligations"].append(
            {
                "id": f"service-{index:03d}",
                "description": _string(term.get("description")),
                "responsible_party": _string(term.get("responsible_party")),
                "owed_to_party": "",
                "frequency": None,
                "service_days": [],
                "service_hours": "",
                "location": "",
                "obligor": _string(term.get("responsible_party")),
                "obligee": "",
                "due_date": _nullable_string(term.get("due_date") or term.get("deadline")),
                "trigger_condition": _string(term.get("trigger_condition")),
                "acceptance_terms": "",
                "proof_terms": "",
                "source_clause_id": _nullable_string(term.get("clause_key")),
                "missing_fields": _missing_obligation_fields(term, ["description"]),
                "source": "prepared_terms.service_obligations",
            }
        )


def _clauses_from_snapshot_clauses(schema, clauses):
    for index, raw_clause in enumerate(clauses, start=1):
        if not isinstance(raw_clause, dict):
            continue
        body = _string(raw_clause.get("body") or raw_clause.get("source_text"))
        title = _clean_heading_title(_string(raw_clause.get("title")))
        if not body and not title:
            continue
        clause = _make_clause(
            index=index,
            title=title,
            body=body or title,
            clause_type=_infer_clause_type(title, body),
            number=_nullable_string(raw_clause.get("clause_number") or raw_clause.get("number")),
            source_type=SOURCE_TYPE_TEMPLATE_CLAUSES,
            source_field="clauses",
            raw_excerpt=body or title,
            clause_key=_string(raw_clause.get("clause_key")),
        )
        _append_clause(schema, clause)


def _clauses_from_sections(schema, sections):
    for raw_section in sections:
        if not isinstance(raw_section, dict):
            continue
        body = _string(raw_section.get("body") or raw_section.get("content") or raw_section.get("source_text") or raw_section.get("text"))
        title = _clean_heading_title(_string(raw_section.get("name") or raw_section.get("title")))
        if not body:
            schema["source_provenance"].append(
                make_source_provenance(
                    SOURCE_TYPE_SECTIONS,
                    "sections",
                    extraction_method="navigation_hint",
                    raw_excerpt=title,
                )
            )
            continue
        clause = _make_clause(
            index=len(schema["clauses"]) + 1,
            title=title,
            body=body,
            clause_type=_infer_clause_type(title, body),
            number=_nullable_string(raw_section.get("number")),
            source_type=SOURCE_TYPE_SECTIONS,
            source_field="sections",
            raw_excerpt=body,
            clause_key=_string(raw_section.get("id")),
        )
        _append_clause(schema, clause)


def _clauses_from_text(schema, text, source_type, source_field):
    normalized = _normalize_plain_text(text)
    if not normalized:
        return

    blocks = _split_clause_blocks(normalized)
    if not blocks:
        blocks = [{"number": None, "title": "General Terms", "body": normalized}]

    for block in blocks:
        title = _clean_heading_title(block["title"])
        body = _normalize_plain_text(block["body"])
        if not body and title:
            body = title
        if not body:
            continue
        clause = _make_clause(
            index=len(schema["clauses"]) + 1,
            title=title,
            body=body,
            clause_type=_infer_clause_type(title, body),
            number=block["number"],
            source_type=source_type,
            source_field=source_field,
            raw_excerpt=body,
        )
        _append_clause(schema, clause)


def _split_clause_blocks(text):
    lines = [line.strip() for line in text.splitlines()]
    blocks = []
    current = None

    for line in lines:
        if not line:
            if current and current["body_lines"] and current["body_lines"][-1] != "":
                current["body_lines"].append("")
            continue

        heading = _parse_heading(line)
        if heading:
            if current:
                blocks.append(current)
            current = {"number": heading["number"], "title": heading["title"], "body_lines": []}
            continue

        if current is None:
            current = {"number": None, "title": "General Terms", "body_lines": []}
        current["body_lines"].append(line)

    if current:
        blocks.append(current)

    results = []
    for block in blocks:
        title = _clean_heading_title(block["title"])
        body = "\n".join(block["body_lines"]).strip()
        if not body and title:
            body = title
        if not body:
            continue
        results.append({"number": block["number"], "title": title, "body": body})

    if len(results) == 1 and results[0]["title"] == "General Terms":
        return []
    return results


def _parse_heading(line):
    raw = _normalize_plain_text(line).strip(" :-")
    if not raw or len(raw) > 150:
        return None
    if _is_address_like(raw):
        return None

    match = _HEADING_PREFIX_RE.match(raw)
    if match:
        title = _clean_heading_title(match.group("title"))
        if _is_bad_heading_title(title):
            return None
        return {"number": match.group("number"), "title": title}

    if _SIGNATURE_HEADING_RE.match(raw):
        return {"number": None, "title": "Signatures"}

    compact = re.sub(r"\s+", " ", raw).strip()
    if compact.upper() in _UPPERCASE_HEADING_WORDS:
        return {"number": None, "title": _title_case_heading(compact)}

    if _looks_like_uppercase_heading(compact) and not _is_bad_heading_title(compact):
        return {"number": None, "title": _title_case_heading(compact)}

    return None


def _make_clause(
    *,
    index,
    title,
    body,
    clause_type,
    number,
    source_type,
    source_field,
    raw_excerpt,
    clause_key="",
):
    clause_id = clause_key or f"clause-{index:03d}"
    missing = []
    if not title:
        missing.append("title")
    return {
        "id": clause_id,
        "order": index,
        "number": number,
        "title": title,
        "body": body,
        "clause_type": clause_type or "general",
        "normalized_status": "normalized",
        "source_type": source_type,
        "source_field": source_field,
        "missing_fields": missing,
    }


def _append_clause(schema, clause):
    schema["clauses"].append(clause)
    schema["source_provenance"].append(
        make_source_provenance(
            clause["source_type"],
            clause["source_field"],
            clause_id=clause["id"],
            raw_excerpt=_excerpt(clause["body"]),
        )
    )


def _post_process_schema(schema):
    _detect_placeholders(schema)
    for clause in schema["clauses"]:
        _promote_clause_terms(schema, clause)
        _extract_clause_obligations(schema, clause)


def _detect_placeholders(schema):
    seen = set()
    for key in ("editor_html", "raw_content", "plain_text"):
        value = schema["render_cache"].get(key)
        if value:
            _add_placeholders(schema, value, f"render_cache.{key}", seen)
    # final_editor_html is render cache only, but unresolved placeholders in it are still useful warnings.
    if schema["render_cache"].get("final_editor_html"):
        _add_placeholders(schema, schema["render_cache"]["final_editor_html"], "render_cache.final_editor_html", seen)
    for clause in schema["clauses"]:
        _add_placeholders(schema, clause.get("body") or "", f"clauses.{clause['id']}.body", seen, clause.get("id"))


def _add_placeholders(schema, text, field_path, seen, clause_id=None):
    plain = _html_to_text(text) if "<" in _string(text) else _string(text)
    for match in _PLACEHOLDER_RE.finditer(plain):
        token = match.group(0).strip()
        key = (field_path, token)
        if key in seen:
            continue
        seen.add(key)
        schema["missing_unresolved_fields"].append(
            make_missing_field(
                field_path,
                f"Unresolved placeholder {token} found.",
                severity="warning",
                source_context=_excerpt(plain[max(0, match.start() - 60): match.end() + 60]),
            )
        )


def _promote_clause_terms(schema, clause):
    ctype = clause.get("clause_type")
    raw_text = clause.get("body") or ""
    source_clause_id = clause.get("id")

    if ctype == "termination" and schema.get("termination_terms") is None:
        schema["termination_terms"] = {
            "source_clause_id": source_clause_id,
            "raw_text": raw_text,
            "notice_period": _extract_notice_period(raw_text),
            "termination_for_cause": _contains_any(raw_text, ["for cause", "materially breaches", "breach"]),
            "missing_fields": [],
        }
    elif ctype == "dispute_resolution" and schema.get("dispute_terms") is None:
        method = _first_match(raw_text, ["arbitration", "mediation", "negotiation", "court", "venue"])
        terms = {
            "source_clause_id": source_clause_id,
            "raw_text": raw_text,
            "method": method,
            "venue": _extract_venue(raw_text),
            "missing_fields": [] if method else ["method"],
        }
        schema["dispute_terms"] = terms
        schema["resolution_terms"] = terms
    elif ctype == "notices" and schema.get("notices") is None:
        schema["notices"] = {
            "source_clause_id": source_clause_id,
            "raw_text": raw_text,
            "methods": _extract_notice_methods(raw_text),
            "notice_period": _extract_notice_period(raw_text),
            "missing_fields": [],
        }
    elif ctype == "governing_law" and schema.get("governing_law") is None:
        jurisdiction = _extract_governing_law(raw_text)
        schema["governing_law"] = {
            "source_clause_id": source_clause_id,
            "raw_text": raw_text,
            "jurisdiction": jurisdiction,
            "missing_fields": [] if jurisdiction else ["jurisdiction"],
        }


def _extract_clause_obligations(schema, clause):
    ctype = clause.get("clause_type")
    if ctype in {"payment", "late_payment"}:
        if not _has_obligation_for_clause(schema["payment_obligations"], clause["id"]):
            schema["payment_obligations"].append(_payment_obligation_from_clause(clause, len(schema["payment_obligations"]) + 1))
    if ctype in {"services", "scope", "service_schedule"}:
        if not _has_obligation_for_clause(schema["service_obligations"], clause["id"]):
            schema["service_obligations"].append(_service_obligation_from_clause(clause, len(schema["service_obligations"]) + 1))


def _payment_obligation_from_clause(clause, index):
    text = clause.get("body") or ""
    amount, currency = _extract_amount(text)
    invoice_rule = _extract_sentence_with(text, ["invoice", "invoiced"])
    due_date_rule = _extract_due_rule(text)
    payment_method = _first_match(text, ["cash", "check", "credit card", "ACH", "wire", "bank transfer", "manual"])
    payer = _first_match(text, ["client", "customer", "tenant", "buyer", "counterparty", "homeowner"])
    payee = _first_match(text, ["provider", "contractor", "consultant", "landlord", "seller", "initiator"])
    missing = []
    if amount is None:
        missing.append("amount")
    if due_date_rule is None:
        missing.append("due_date_rule")
    return {
        "id": f"payment-{index:03d}",
        "description": _excerpt(text, 500),
        "amount": amount,
        "currency": currency or "",
        "payer": payer or "",
        "payee": payee or "",
        "frequency": _extract_frequency(text),
        "invoice_rule": invoice_rule,
        "due_date_rule": due_date_rule,
        "payment_method": payment_method or "",
        "trigger_condition": _extract_trigger(text),
        "recurrence": None,
        "source_clause_id": clause["id"],
        "missing_fields": missing,
        "source": "clause_text",
    }


def _service_obligation_from_clause(clause, index):
    text = clause.get("body") or ""
    location = _extract_location(text)
    return {
        "id": f"service-{index:03d}",
        "description": _excerpt(text, 500),
        "responsible_party": _first_match(text, ["provider", "contractor", "consultant", "service provider", "lawn care provider"]) or "",
        "owed_to_party": _first_match(text, ["client", "customer", "homeowner", "counterparty"]) or "",
        "frequency": _extract_frequency(text),
        "service_days": _extract_service_days(text),
        "service_hours": _extract_service_hours(text),
        "location": location or "",
        "obligor": "",
        "obligee": "",
        "due_date": None,
        "trigger_condition": _extract_trigger(text),
        "acceptance_terms": "",
        "proof_terms": "",
        "source_clause_id": clause["id"],
        "missing_fields": [] if text else ["description"],
        "source": "clause_text",
    }


def _normalize_sections(sections):
    normalized = []
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        normalized.append(
            {
                "id": _string(section.get("id")) or f"section-{index:03d}",
                "number": section.get("number") if isinstance(section.get("number"), int) else index,
                "name": _string(section.get("name") or section.get("title")),
                "has_body": bool(_string(section.get("body") or section.get("content") or section.get("text") or section.get("source_text"))),
            }
        )
    return normalized


def _record_unresolved_defaults(schema):
    if not schema["participants"]:
        schema["missing_unresolved_fields"].append(
            make_missing_field("participants", "No participants found in snapshot or contract context.")
        )
    if not schema["clauses"]:
        schema["missing_unresolved_fields"].append(
            make_missing_field("clauses", "No clause content found in snapshot.")
        )


def _missing_obligation_fields(term, keys):
    return [key for key in keys if term.get(key) in (None, "")]


def _infer_clause_type(title, body):
    text = f"{title or ''} {body or ''}".lower()
    keyword_map = [
        ("signatures", ["signature", "signed by", "in witness whereof"]),
        ("late_payment", ["late payment", "late fee", "interest", "overdue", "not paid within"]),
        ("payment", ["payment", "pay ", "pays", "paid", "fee", "fees", "invoice", "deposit", "installment", "compensation", "total of $"]),
        ("termination", ["termination", "terminate", "cancellation", "cancel"]),
        ("dispute_resolution", ["dispute", "arbitration", "mediation", "venue", "court", "resolution"]),
        ("governing_law", ["governing law", "laws of", "jurisdiction"]),
        ("notices", ["notice", "notices", "written notice"]),
        ("change_order", ["change order", "written amendment", "scope change", "modification"]),
        ("insurance", ["insurance", "insured", "liability coverage"]),
        ("confidentiality", ["confidential", "non-disclosure", "non disclosure", "confidentiality"]),
        ("service_schedule", ["schedule", "weekly", "monthly", "service days", "service hours", "frequency"]),
        ("services", ["scope", "service", "deliver", "perform", "work", "deliverable", "maintenance", "mow", "edge", "trim"]),
        ("parties", ["party", "parties"]),
    ]
    for clause_type, keywords in keyword_map:
        if any(keyword in text for keyword in keywords):
            return clause_type
    return "general"


def _html_to_text(html):
    text = _string(html)
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(div|p|h[1-6]|li|tr|section)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return _normalize_plain_text(unescape(text))


def _normalize_plain_text(text):
    text = _string(text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_heading_title(title):
    title = _normalize_plain_text(title).strip(" :-")
    title = re.sub(r"^(?:section|article|clause)\s+", "", title, flags=re.IGNORECASE).strip(" :-")
    return _title_case_heading(title) if title.isupper() else title


def _title_case_heading(value):
    small = {"of", "and", "or", "the", "to", "for", "in"}
    words = value.lower().split()
    return " ".join(word if i and word in small else word.capitalize() for i, word in enumerate(words))


def _looks_like_uppercase_heading(line):
    if len(line) > 80 or line.endswith((".", ",", ";")):
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 4:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) > 0.8 and len(line.split()) <= 8


def _is_bad_heading_title(title):
    if not title:
        return True
    if _is_address_like(title):
        return True
    if len(title.split()) > 12 and not title.isupper():
        return True
    if title.endswith((".", ",", ";")):
        return True
    return False


def _is_address_like(text):
    return bool(_ADDRESS_HINT_RE.search(text)) and bool(re.search(r"\d", text))


def _set_render_cache(schema, key, value):
    schema["render_cache"][key] = value


def _add_source_type(schema, source_type):
    source_types = schema["extraction_report"]["source_types"]
    if source_type and source_type not in source_types:
        source_types.append(source_type)


def _warn(schema, message):
    warnings = schema["extraction_report"]["warnings"]
    if message and message not in warnings:
        warnings.append(message)


def _contains_any(text, terms):
    lowered = _string(text).lower()
    return any(term.lower() in lowered for term in terms)


def _first_match(text, terms):
    lowered = _string(text).lower()
    for term in terms:
        if term.lower() in lowered:
            return term
    return None


def _extract_amount(text):
    match = _AMOUNT_RE.search(_string(text))
    if not match:
        return None, None
    currency = "USD" if match.group("currency").strip().upper().startswith(("$", "USD")) else match.group("currency").strip()
    return match.group("amount").replace(",", ""), currency


def _extract_frequency(text):
    return _first_match(text, ["weekly", "bi-weekly", "biweekly", "monthly", "quarterly", "annually", "one-time", "per session"])


def _extract_due_rule(text):
    patterns = [
        r"due within [^.\n;]+",
        r"due upon [^.\n;]+",
        r"due on [^.\n;]+",
        r"within \d+ (?:day|days|business days|week|weeks|month|months)[^.\n;]*",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def _extract_notice_period(text):
    match = re.search(r"\b(?:within\s+)?\d+\s+(?:business\s+)?(?:day|days|week|weeks|month|months)\b", _string(text), flags=re.IGNORECASE)
    return match.group(0) if match else None


def _extract_notice_methods(text):
    methods = []
    lowered = _string(text).lower()
    for method in ("email", "mail", "certified mail", "personal delivery", "written notice"):
        if method in lowered:
            methods.append(method)
    return methods


def _extract_governing_law(text):
    match = re.search(r"laws? of (?:the state of )?([A-Z][A-Za-z ]+)", _string(text))
    if match:
        return match.group(1).strip().rstrip(".")
    match = re.search(r"governed by ([^.]+)", _string(text), flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_venue(text):
    match = re.search(r"venue (?:shall be |is )?(?:in|within) ([^.]+)", _string(text), flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_sentence_with(text, terms):
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", _string(text)):
        if _contains_any(sentence, terms):
            return sentence.strip()
    return ""


def _extract_trigger(text):
    return _extract_sentence_with(text, ["upon", "after", "before", "if", "when"])


def _extract_service_days(text):
    days = []
    lowered = _string(text).lower()
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        if day in lowered:
            days.append(day)
    return days


def _extract_service_hours(text):
    match = re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*(?:-|to)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", _string(text), re.IGNORECASE)
    return match.group(0) if match else ""


def _extract_location(text):
    match = re.search(r"(?:at|located at|property at)\s+([^.;\n]+(?:\d{5})?)", _string(text), re.IGNORECASE)
    return match.group(1).strip() if match else None


def _has_obligation_for_clause(obligations, clause_id):
    return any(item.get("source_clause_id") == clause_id for item in obligations)


def _string(value):
    if value is None:
        return ""
    return str(value).strip()


def _nullable_string(value):
    value = _string(value)
    return value or None


def _date_string(value):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _display_name(user):
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = get_full_name().strip()
        if full_name:
            return full_name
    return _string(getattr(user, "email", "")) or _string(getattr(user, "username", "")) or str(user)


def _has_participant(schema, role, email):
    for participant in schema["participants"]:
        if participant.get("role") != role:
            continue
        if email and participant.get("email") == email:
            return True
        if not email:
            return True
    return False


def _excerpt(text, limit=240):
    text = _normalize_plain_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
