import re

from backend.contracts.models import ContractExtractionCandidate

from .amounts import extract_amounts, money_title_amount, to_decimal
from .dates import due_datetime, fixed_due_date, fixed_due_dates
from .domains.rental import is_rental_term, rental_candidate_type, rental_title
from .domains.service import service_candidate_type, service_title
from .roles import parse_roles, parties_for_sentence
from .text import prepared_source_text, split_sentences
from .triggers import before_trigger, due_rule, due_trigger, monthly_rent_recurrence, relative_due_rule


def _candidate_title(term, fallback):
    title = str(term.get("title") or term.get("clause_title") or "").strip()
    if not title:
        description = str(term.get("description") or "").strip()
        title = description[:80].strip()
    return (title or fallback)[:255]


def _candidate_due_date(raw_due, contract):
    due_at = due_datetime(raw_due, contract)
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


def _metadata_for_sentence(index, original_model, extra=None):
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


def _candidate_source_location(term):
    location = {}
    if term.get("clause_number"):
        location["clause_number"] = term.get("clause_number")
    if term.get("clause_title"):
        location["clause_title"] = term.get("clause_title")
    if term.get("clause_type"):
        location["clause_type"] = term.get("clause_type")
    return location


def _raw_sentence_payload(sentence, source_index, amount_info=None, trigger="", relative_due=None):
    payload = {"sentence": sentence, "source_index": source_index}
    if amount_info:
        payload["amount"] = amount_info.get("amount")
        payload["amount_raw"] = amount_info.get("raw")
    if trigger:
        payload["due_trigger"] = trigger
    if relative_due:
        payload["relative_due"] = relative_due
    return payload


def _title_for_sentence(candidate_type, sentence, amount_info=None):
    rental = rental_title(sentence, candidate_type, ContractExtractionCandidate)
    if rental:
        return rental
    lowered = sentence.lower()
    if candidate_type == ContractExtractionCandidate.TYPE_PAYMENT:
        amount = money_title_amount(amount_info or {})
        if "homepage mockup" in lowered:
            return f"Pay {amount} for homepage mockup"
        if "full website" in lowered:
            return f"Pay {amount} for full website"
        return f"Pay {amount}".strip()
    service = service_title(sentence)
    if service:
        return service
    return sentence[:80].strip()


def _sentence_candidate_type(sentence):
    lowered = sentence.lower()
    rental_type = rental_candidate_type(sentence, ContractExtractionCandidate)
    if rental_type:
        return rental_type
    if extract_amounts(sentence) or re.search(r"\bpay\b|\bpayment\b", lowered):
        return ContractExtractionCandidate.TYPE_PAYMENT
    service_type = service_candidate_type(sentence, ContractExtractionCandidate)
    if service_type:
        return service_type
    if fixed_due_date(sentence):
        return ContractExtractionCandidate.TYPE_DEADLINE
    return ""


def _build_rental_term_candidates(contract, version, run, sentence, index, metadata_extra):
    candidates = []
    term_dates = fixed_due_dates(sentence)
    term_specs = [
        ("Rental term begins", term_dates[0] if len(term_dates) > 0 else None, "term_start_date"),
        ("Rental term ends", term_dates[1] if len(term_dates) > 1 else None, "term_end_date"),
    ]
    for title, term_date, metadata_key in term_specs:
        metadata = dict(metadata_extra)
        if term_date:
            metadata[metadata_key] = term_date.isoformat()
        candidates.append(ContractExtractionCandidate(
            run=run, contract=contract, contract_version=version, candidate_type=ContractExtractionCandidate.TYPE_DEADLINE,
            title=title, description=sentence, due_date=term_date, currency=contract.currency or "",
            source_clause_text=sentence, source_clause_key=f"sentence-{index:03d}",
            source_location={"sentence_index": index, "term_marker": metadata_key},
            missing_terms=[] if term_date else ["due_date"],
            raw_payload={"sentence": sentence, "source_index": index, metadata_key: term_date.isoformat() if term_date else None},
            metadata=_metadata_for_sentence(index, "prepared_terms.rental_term", metadata),
        ))
    return candidates


def build_sentence_candidates(contract, version, run, prepared_terms, draft_text):
    source_text = prepared_source_text(prepared_terms, draft_text)
    roles = parse_roles(source_text, contract)
    candidates = []
    for index, sentence in enumerate(split_sentences(source_text), start=1):
        lowered = sentence.lower()
        if re.match(r"^(website design service agreement|residential room rental agreement|client:\s*|contractor:\s*|landlord:\s*|tenant:\s*)", sentence, re.IGNORECASE):
            continue
        if re.match(r"^[A-Z][A-Za-z /-]{2,60} Terms\.$", sentence):
            continue
        candidate_type = _sentence_candidate_type(sentence)
        if not candidate_type:
            continue
        if "agrees to design" in lowered and not fixed_due_date(sentence) and not relative_due_rule(sentence):
            continue

        fixed = fixed_due_date(sentence)
        relative = relative_due_rule(sentence)
        trigger = due_trigger(sentence)
        responsible, beneficiary = parties_for_sentence(sentence, candidate_type, roles, contract, ContractExtractionCandidate)
        metadata_extra = {"role_map": roles}
        if trigger:
            metadata_extra["due_trigger"] = trigger
        if relative:
            metadata_extra["relative_due"] = relative

        if is_rental_term(sentence):
            candidates.extend(_build_rental_term_candidates(contract, version, run, sentence, index, metadata_extra))
            continue

        if candidate_type in {ContractExtractionCandidate.TYPE_PAYMENT, ContractExtractionCandidate.TYPE_DEPOSIT}:
            amounts = extract_amounts(sentence) or [{"raw": "", "amount": None, "currency": contract.currency or ""}]
            before = before_trigger(sentence)
            for amount_index, amount_info in enumerate(amounts, start=1):
                amount = to_decimal(amount_info.get("amount"))
                missing_terms = [] if amount is not None else ["amount"]
                recurrence = monthly_rent_recurrence(sentence, amount)
                payment_metadata = dict(metadata_extra)
                if recurrence:
                    payment_metadata["payment_kind"] = "rent"
                    payment_metadata["due_rule"] = due_rule(sentence)
                if before:
                    payment_metadata["due_trigger"] = before
                if candidate_type == ContractExtractionCandidate.TYPE_DEPOSIT:
                    payment_metadata["payment_kind"] = "security_deposit"
                raw_payload = _raw_sentence_payload(sentence, index, amount_info, trigger or before, relative)
                if recurrence:
                    raw_payload["recurrence"] = recurrence
                candidates.append(ContractExtractionCandidate(
                    run=run, contract=contract, contract_version=version, candidate_type=candidate_type,
                    title=_title_for_sentence(candidate_type, sentence, amount_info), description=sentence,
                    responsible_party=responsible, beneficiary_party=beneficiary,
                    due_date=fixed if not (trigger or relative or before or recurrence) else None,
                    amount=amount, currency=amount_info.get("currency") or contract.currency or "", recurrence=recurrence,
                    source_clause_text=sentence, source_clause_key=f"sentence-{index:03d}",
                    source_location={"sentence_index": index, "amount_index": amount_index}, missing_terms=missing_terms,
                    raw_payload=raw_payload, metadata=_metadata_for_sentence(index, "ContractObligation", payment_metadata),
                ))
            continue

        original_model = "ContractServiceObligation" if candidate_type == ContractExtractionCandidate.TYPE_SERVICE_WORK else "prepared_terms.responsibility"
        candidates.append(ContractExtractionCandidate(
            run=run, contract=contract, contract_version=version, candidate_type=candidate_type,
            title=_title_for_sentence(candidate_type, sentence), description=sentence,
            responsible_party=responsible, beneficiary_party=beneficiary, due_date=fixed if not relative else None,
            currency=contract.currency or "", source_clause_text=sentence, source_clause_key=f"sentence-{index:03d}",
            source_location={"sentence_index": index}, missing_terms=[], raw_payload=_raw_sentence_payload(sentence, index, relative_due=relative),
            metadata=_metadata_for_sentence(index, original_model, metadata_extra),
        ))
    return candidates


def build_prepared_term_candidates(contract, version, run, prepared_terms):
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
        amount = to_decimal(term.get("amount"))
        candidates.append(ContractExtractionCandidate(
            run=run, contract=contract, contract_version=version, candidate_type=ContractExtractionCandidate.TYPE_PAYMENT,
            title=_candidate_title(term, f"Payment term {index}"), description=term.get("description", ""),
            responsible_party=term.get("responsible_party", ""), beneficiary_party=str(contract.initiator) if contract.initiator else "",
            due_date=due_date, amount=amount, currency=term.get("currency") or contract.currency or "",
            source_clause_text=term.get("description", "") or term.get("trigger_condition", ""), source_clause_key=term.get("clause_key") or "",
            source_location=_candidate_source_location(term), missing_terms=_candidate_missing_terms(term, ["amount", "due_date"], due_date=due_date, amount=amount),
            raw_payload=term, metadata=_candidate_metadata("payment_terms", index, "ContractObligation"),
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
            run=run, contract=contract, contract_version=version, candidate_type=ContractExtractionCandidate.TYPE_SERVICE_WORK,
            title=_candidate_title(term, f"Service obligation {index}"), description=term.get("description", ""),
            responsible_party=term.get("responsible_party", ""), beneficiary_party=contract.counterparty_name or contract.counterparty_email or "",
            due_date=due_date, currency=term.get("currency") or contract.currency or "",
            source_clause_text=term.get("description", "") or term.get("trigger_condition", ""), source_clause_key=term.get("clause_key") or "",
            source_location=_candidate_source_location(term), missing_terms=_candidate_missing_terms(term, ["description", "due_date"], due_date=due_date),
            raw_payload=term, metadata=_candidate_metadata("service_obligations", index, "ContractServiceObligation"),
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
            run=run, contract=contract, contract_version=version,
            candidate_type=ContractExtractionCandidate.TYPE_DEADLINE if due_date else ContractExtractionCandidate.TYPE_OTHER,
            title=_candidate_title(term, f"Milestone {index}"), description=term.get("description", ""), due_date=due_date, currency=contract.currency or "",
            source_clause_text=term.get("description", "") or term.get("trigger_condition", ""), source_clause_key=term.get("clause_key") or "",
            source_location=_candidate_source_location(term), missing_terms=_candidate_missing_terms(term, ["description", "due_date"], due_date=due_date),
            raw_payload=term, metadata=_candidate_metadata("milestones", index, "prepared_terms.milestones"),
        ))

    for index, raw_deadline in enumerate(prepared_terms.get("deadlines") or [], start=1):
        if not raw_deadline or str(raw_deadline) in represented_deadlines:
            continue
        due_date = _candidate_due_date(raw_deadline, contract)
        candidates.append(ContractExtractionCandidate(
            run=run, contract=contract, contract_version=version, candidate_type=ContractExtractionCandidate.TYPE_DEADLINE,
            title=f"Deadline {raw_deadline}"[:255], description=str(raw_deadline), due_date=due_date, currency=contract.currency or "",
            missing_terms=[] if due_date else ["due_date"], raw_payload={"deadline": raw_deadline},
            metadata=_candidate_metadata("deadlines", index, "prepared_terms.deadlines"),
        ))
    return candidates
