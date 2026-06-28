import json
import re
from datetime import datetime
from decimal import Decimal
from html import unescape

from django.db import transaction
from django.utils import timezone

from backend.agreement_exchange.models import AgreementExchange
from backend.agreement_exchange.notifications import find_user_by_email, notify_exchange_recipient
from backend.contracts.models import ContractVersion, LifecycleAgreement, LifecycleEvent, LifecycleItem, LifecycleItemAttachment, LifecycleItemResponse, LifecycleItemUserState
from backend.notifications.models import Notification


class LifecycleNotReadyError(Exception):
    pass


def find_signed_contract_version(contract):
    return resolve_lifecycle_ready_contract(contract)["signed_version"]


def find_source_exchange(contract, signed_version):
    return (
        AgreementExchange.objects
        .filter(
            current_contract_version=signed_version,
            status=AgreementExchange.STATUS_SIGNED,
        )
        .order_by("-updated_at", "-created_at")
        .first()
    )


def _contract_exchanges(contract):
    prefetched_exchanges = getattr(contract, "_prefetched_objects_cache", {}).get("agreement_exchanges")
    if prefetched_exchanges is not None:
        return sorted(prefetched_exchanges, key=lambda exchange: exchange.updated_at, reverse=True)
    return list(
        AgreementExchange.objects
        .filter(contract=contract)
        .select_related("current_contract_version", "current_contract_version__contract")
        .order_by("-updated_at", "-created_at")
    )


def resolve_lifecycle_ready_contract(contract):
    signed_version = (
        ContractVersion.objects
        .filter(contract=contract, status="signed")
        .order_by("-version_number", "-created_at")
        .select_related("contract")
        .first()
    )
    if signed_version is None:
        return {"contract": contract, "signed_version": None, "source_exchange": None}

    return {
        "contract": contract,
        "signed_version": signed_version,
        "source_exchange": find_source_exchange(contract, signed_version),
    }


def backfill_signed_exchange_versions(*, apply=False):
    exchanges = (
        AgreementExchange.objects
        .filter(status=AgreementExchange.STATUS_SIGNED)
        .exclude(current_contract_version__status="signed")
        .select_related("contract", "current_contract_version")
        .order_by("contract_id", "-updated_at", "-created_at")
    )
    repaired = []
    for exchange in exchanges:
        version = exchange.current_contract_version
        contract = version.contract
        repaired.append({
            "exchange_id": str(exchange.id),
            "contract_id": str(contract.id),
            "version_id": str(version.id),
            "version_status": version.status,
            "contract_status": contract.status,
        })
        if not apply:
            continue
        version.status = "signed"
        version.save(update_fields=["status"])
        if contract.status != "signed":
            contract.status = "signed"
            contract.save(update_fields=["status"])
    return repaired


def contract_is_lifecycle_ready(contract):
    return resolve_lifecycle_ready_contract(contract)["signed_version"] is not None



def _payment_method_from_metadata(metadata):
    payment_method = (metadata or {}).get("payment_method")
    if not payment_method:
        payment_methods = (metadata or {}).get("payment_methods")
        if isinstance(payment_methods, list) and payment_methods:
            payment_method = payment_methods[0]
    return payment_method



def _timeline_item_baseline_values(item):
    metadata = item.metadata or {}
    return {
        "title": item.title,
        "description": item.description,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "amount": str(item.amount) if item.amount is not None else None,
        "responsible_party": item.responsible_party,
        "payment_method": _payment_method_from_metadata(metadata),
        "status": item.status,
    }



def _timeline_item_user_state(item, user, *, create=False):
    if not getattr(user, "is_authenticated", False):
        return None
    qs = LifecycleItemUserState.objects.filter(lifecycle_item=item, user=user)
    if create:
        state, _ = LifecycleItemUserState.objects.get_or_create(lifecycle_item=item, user=user)
        return state
    return qs.first()



def _snapshot_to_plain_text(content_snapshot):
    raw = str(content_snapshot or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = None

    if isinstance(parsed, dict):
        for key in ("final_editor_html", "editor_html", "content_html", "html", "body", "text", "raw_content", "summary"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                raw = value
                break
        else:
            sections = parsed.get("sections")
            if isinstance(sections, list):
                chunks = []
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    title = section.get("title") or section.get("heading") or section.get("name") or ""
                    body = section.get("body") or section.get("text") or section.get("content") or section.get("html") or section.get("content_html") or section.get("editor_html") or ""
                    chunks.append("\n".join(str(part) for part in (title, body) if part))
                raw = "\n\n".join(chunks)

    text = unescape(raw)
    text = re.sub(r"<\/?(h[1-6]|p|div|li|br|section|article|tr|td|th)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _parse_money(value):
    return Decimal(str(value).replace(",", ""))


def _parse_contract_date(value):
    cleaned = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", str(value or ""), flags=re.IGNORECASE).strip().rstrip(".,;")
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return timezone.make_aware(datetime.strptime(cleaned, fmt), timezone.get_current_timezone())
        except ValueError:
            continue
    return None


_DATE_PATTERN = r"(?:[A-Z][a-z]+\s+\d{1,2},\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})"
_MONEY_PATTERN = r"\d[\d,]*(?:\.\d{2})?"


_LOAN_REPAYMENT_MARKERS = (
    "repayment schedule",
    "loan funds",
    "loan amount",
    "borrower will repay",
    "lender agrees to lend",
    "personal loan",
    "personal repayment agreement",
)


def _detect_agreement_category(text):
    normalized = " ".join(str(text or "").lower().split())
    if not normalized:
        return "generic_contract"
    if any(marker in normalized for marker in _LOAN_REPAYMENT_MARKERS):
        return "loan_repayment"
    return "generic_contract"


PAYMENT_METHOD_PATTERNS = (
    r"loan may be delivered by (?P<method>[^.]+)",
    r"payments by (?P<method>[^.]+)",
)


def _extract_payment_methods(text):
    for pattern in PAYMENT_METHOD_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group("method").strip().rstrip(".")
    return ""


def _extract_repayment_installments(text):
    installments = []
    seen = set()
    patterns = [
        re.compile(rf"\bPayment\s+(?P<number>\d{{1,2}})\s*[:\-]?\s*\$\s*(?P<amount>{_MONEY_PATTERN})\s+due\s+(?P<date>{_DATE_PATTERN})", re.IGNORECASE),
        re.compile(rf"(?:^|\n)\s*(?P<number>\d{{1,2}})\s+(?P<date>{_DATE_PATTERN})\s+\$\s*(?P<amount>{_MONEY_PATTERN})", re.IGNORECASE),
        re.compile(rf"\bInstallment\s+(?P<number>\d{{1,2}})\s*[:\-]?\s*(?:due\s+)?(?P<date>{_DATE_PATTERN}).{{0,80}}?\$\s*(?P<amount>{_MONEY_PATTERN})", re.IGNORECASE),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            number = int(match.group("number"))
            amount = _parse_money(match.group("amount"))
            due_date = _parse_contract_date(match.group("date"))
            key = (number, str(amount), due_date.date().isoformat() if due_date else "")
            if due_date is None or key in seen:
                continue
            seen.add(key)
            installments.append({"number": number, "amount": amount, "due_date": due_date})
    return sorted(installments, key=lambda item: item["number"])


def _extract_loan_amount(text):
    patterns = [
        rf"lender agrees to lend[^.]*?\$\s*(?P<amount>{_MONEY_PATTERN})",
        rf"total amount of[^.]*?\$\s*(?P<amount>{_MONEY_PATTERN})",
        rf"loan amount[^.]*?\$\s*(?P<amount>{_MONEY_PATTERN})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _parse_money(match.group("amount"))
    return None


def _extract_first_date_after(pattern, text):
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    date_match = re.search(_DATE_PATTERN, match.group(0))
    return _parse_contract_date(date_match.group(0)) if date_match else None


def _extract_loan_delivery_obligation(text):
    date = _extract_first_date_after(rf"loan funds.{{0,160}}?no later than\s+{_DATE_PATTERN}", text)
    if not date:
        date = _extract_first_date_after(rf"provide.{{0,80}}?loan.{{0,80}}?(?:by|before|on|no later than)\s+{_DATE_PATTERN}", text)
    if not date and not re.search(r"lender (?:will provide|must provide|agrees to lend)", text, flags=re.IGNORECASE):
        return None

    method = _extract_payment_methods(text)
    amount = _extract_loan_amount(text)
    return {"amount": amount, "due_date": date, "method": method}


def _extract_borrower_responsibilities(text):
    rules = [
        ("borrower_repayment", r"responsible for making each payment on time", "Borrower must make each repayment on time.", "Borrower responsibilities"),
        ("borrower_payment_proof", r"borrower (?:is responsible for keeping|should keep) proof of (?:each )?payment", "Borrower should keep proof of payment.", "Borrower responsibilities"),
        ("borrower_late_notice", r"borrower must notify the lender before a due date if .*payment may be late", "Borrower must notify the lender before a due date if payment may be late.", "Borrower responsibilities"),
        ("borrower_late_contact", r"if a payment is late, the borrower must contact the lender", "Borrower must contact the lender and provide an expected payment date if a payment is late.", "Late payment clause"),
        ("written_communication", r"resolve the issue through written communication|keep written records of important communications", "Parties should communicate agreement issues in writing and keep records.", "Communication and records clause"),
    ]
    return [
        {"key": key, "title": title, "description": title, "source_label": label}
        for key, pattern, title, label in rules
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    ]


def _extract_lender_responsibilities(text):
    rules = [
        ("lender_confirm_receipt", r"lender is responsible for confirming receipt of each payment", "Lender must confirm receipt of each payment within the stated timeframe.", "Lender responsibilities"),
        ("lender_records", r"lender is responsible for keeping a record of payments received", "Lender must keep a record of payments received.", "Lender responsibilities"),
        ("lender_provide_loan", rf"lender agrees to lend .*\$\s*{_MONEY_PATTERN}|lender will provide the loan funds", "Lender must provide the loan amount under the signed agreement.", "Loan amount and delivery clauses"),
    ]
    return [
        {"key": key, "title": title, "description": title, "source_label": label}
        for key, pattern, title, label in rules
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    ]


def _extract_late_payment_default_rules(text):
    if not re.search(r"late fee|default", text, flags=re.IGNORECASE):
        return []
    return [
        {
            "key": "late_default_rules",
            "title": "Review late payment and default rules if a repayment is missed.",
            "description": "The signed agreement contains late payment or default rules. Review them before treating any extra amount as due.",
            "source_label": "Late payment/default clause",
        }
    ]


def _timeline_item_exists(agreement, source_id):
    return LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_id=source_id).exists()


def _create_contract_derived_item(agreement, *, item_type, title, source_id, description="", due_date=None, amount=None, source_label="Signed agreement", responsible_party="", beneficiary_party=""):
    if _timeline_item_exists(agreement, source_id):
        return None
    return LifecycleItem.objects.create(
        lifecycle_agreement=agreement,
        item_type=item_type,
        title=title,
        description=description,
        responsible_party=responsible_party,
        beneficiary_party=beneficiary_party,
        due_date=due_date,
        amount=amount,
        status=LifecycleItem.STATUS_PENDING,
        source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
        source_id=source_id,
        source_label=source_label,
        source_version=agreement.signed_version,
        source_exchange=agreement.source_exchange,
        is_contract_derived=True,
        locked_fields=["title", "description", "amount", "due_date", "source_type", "source_id", "source_label", "source_version", "source_exchange", "is_contract_derived", "locked_fields"],
        metadata={"extractor": "signed_agreement_timeline_v2"},
        created_by=agreement.owner,
    )


def _build_source_id(prefix, version_key, key):
    return f"{prefix}:{version_key}:{key}"


def ensure_signed_contract_timeline_records(agreement):
    signed_version = agreement.signed_version
    text = _snapshot_to_plain_text(signed_version.content_snapshot)
    if not text:
        return []

    category = _detect_agreement_category(text)
    if category != "loan_repayment":
        return []

    created = []
    version_key = str(signed_version.id)
    payment_methods = _extract_payment_methods(text)
    installments = _extract_repayment_installments(text)
    delivery = _extract_loan_delivery_obligation(text)

    for installment in installments:
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title=f"Payment installment {installment['number']}",
            source_id=_build_source_id("repayment_schedule", version_key, installment["number"]),
            description="Scheduled repayment from the signed agreement.",
            due_date=installment["due_date"],
            amount=installment["amount"],
            source_label="Repayment schedule",
            responsible_party="Borrower",
            beneficiary_party="Lender",
        )
        if item:
            if payment_methods:
                item.metadata = {**(item.metadata or {}), "payment_methods": payment_methods}
                item.save(update_fields=["metadata", "updated_at"])
            created.append(item)

    if delivery and delivery["due_date"]:
        delivery_description = "Lender provides the loan funds to the borrower by the stated delivery deadline."
        if delivery["method"]:
            delivery_description = f"{delivery_description} Delivery method: {delivery['method']}."
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_DUE_DATE,
            title="Loan funds delivery deadline",
            source_id=f"loan_delivery:{version_key}",
            description=delivery_description,
            due_date=delivery["due_date"],
            amount=delivery["amount"],
            source_label="Loan delivery clause",
            responsible_party="Lender",
            beneficiary_party="Borrower",
        )
        if item:
            created.append(item)

    if delivery:
        work_description = "Lender provides the loan funds to the borrower."
        if delivery["method"]:
            work_description = f"{work_description} Delivery method: {delivery['method']}."
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            source_id=f"loan_delivery_work:{version_key}",
            description=work_description,
            due_date=delivery["due_date"],
            amount=delivery["amount"],
            source_label="Loan delivery clause",
            responsible_party="Lender",
            beneficiary_party="Borrower",
        )
        if item:
            created.append(item)

    for entry in _extract_borrower_responsibilities(text):
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title=entry["title"],
            source_id=_build_source_id("responsibility", version_key, entry["key"]),
            description=entry["description"],
            source_label=entry["source_label"],
            responsible_party="Borrower",
            beneficiary_party="Lender",
        )
        if item:
            created.append(item)

    for entry in _extract_lender_responsibilities(text):
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title=entry["title"],
            source_id=_build_source_id("responsibility", version_key, entry["key"]),
            description=entry["description"],
            source_label=entry["source_label"],
            responsible_party="Lender",
            beneficiary_party="Borrower",
        )
        if item:
            created.append(item)

    for entry in _extract_late_payment_default_rules(text):
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title=entry["title"],
            source_id=_build_source_id("responsibility", version_key, entry["key"]),
            description=entry["description"],
            source_label=entry["source_label"],
        )
        if item:
            created.append(item)

    return created


def _timeline_item_exists(agreement, source_id):
    return LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_id=source_id).exists()


def _create_contract_derived_item(agreement, *, item_type, title, source_id, description="", due_date=None, amount=None, source_label="Signed agreement", responsible_party="", beneficiary_party=""):
    if _timeline_item_exists(agreement, source_id):
        return None
    return LifecycleItem.objects.create(
        lifecycle_agreement=agreement,
        item_type=item_type,
        title=title,
        description=description,
        responsible_party=responsible_party,
        beneficiary_party=beneficiary_party,
        due_date=due_date,
        amount=amount,
        status=LifecycleItem.STATUS_PENDING,
        source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
        source_id=source_id,
        source_label=source_label,
        source_version=agreement.signed_version,
        source_exchange=agreement.source_exchange,
        is_contract_derived=True,
        locked_fields=["title", "description", "amount", "due_date", "source_type", "source_id", "source_label", "source_version", "source_exchange", "is_contract_derived", "locked_fields"],
        metadata={"extractor": "signed_agreement_timeline_v2"},
        created_by=agreement.owner,
    )


def _build_source_id(prefix, version_key, key):
    return f"{prefix}:{version_key}:{key}"


def ensure_signed_contract_timeline_records(agreement):
    signed_version = agreement.signed_version
    text = _snapshot_to_plain_text(signed_version.content_snapshot)
    if not text:
        return []

    category = _detect_agreement_category(text)
    if category != "loan_repayment":
        return []

    created = []
    version_key = str(signed_version.id)
    payment_methods = _extract_payment_methods(text)
    installments = _extract_repayment_installments(text)
    delivery = _extract_loan_delivery_obligation(text)

    for installment in installments:
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title=f"Payment installment {installment['number']}",
            source_id=_build_source_id("repayment_schedule", version_key, installment["number"]),
            description="Scheduled repayment from the signed agreement.",
            due_date=installment["due_date"],
            amount=installment["amount"],
            source_label="Repayment schedule",
            responsible_party="Borrower",
            beneficiary_party="Lender",
        )
        if item:
            if payment_methods:
                item.metadata = {**(item.metadata or {}), "payment_methods": payment_methods}
                item.save(update_fields=["metadata", "updated_at"])
            created.append(item)

    if delivery and delivery["due_date"]:
        delivery_description = "Lender provides the loan funds to the borrower by the stated delivery deadline."
        if delivery["method"]:
            delivery_description = f"{delivery_description} Delivery method: {delivery['method']}."
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_DUE_DATE,
            title="Loan funds delivery deadline",
            source_id=f"loan_delivery:{version_key}",
            description=delivery_description,
            due_date=delivery["due_date"],
            amount=delivery["amount"],
            source_label="Loan delivery clause",
            responsible_party="Lender",
            beneficiary_party="Borrower",
        )
        if item:
            created.append(item)

    if delivery:
        work_description = "Lender provides the loan funds to the borrower."
        if delivery["method"]:
            work_description = f"{work_description} Delivery method: {delivery['method']}."
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            source_id=f"loan_delivery_work:{version_key}",
            description=work_description,
            due_date=delivery["due_date"],
            amount=delivery["amount"],
            source_label="Loan delivery clause",
            responsible_party="Lender",
            beneficiary_party="Borrower",
        )
        if item:
            created.append(item)

    for entry in _extract_borrower_responsibilities(text):
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title=entry["title"],
            source_id=_build_source_id("responsibility", version_key, entry["key"]),
            description=entry["description"],
            source_label=entry["source_label"],
            responsible_party="Borrower",
            beneficiary_party="Lender",
        )
        if item:
            created.append(item)

    for entry in _extract_lender_responsibilities(text):
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title=entry["title"],
            source_id=_build_source_id("responsibility", version_key, entry["key"]),
            description=entry["description"],
            source_label=entry["source_label"],
            responsible_party="Lender",
            beneficiary_party="Borrower",
        )
        if item:
            created.append(item)

    for entry in _extract_late_payment_default_rules(text):
        item = _create_contract_derived_item(
            agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title=entry["title"],
            source_id=_build_source_id("responsibility", version_key, entry["key"]),
            description=entry["description"],
            source_label=entry["source_label"],
        )
        if item:
            created.append(item)

    return created


@transaction.atomic
def get_or_create_lifecycle_for_signed_contract(contract, user):
    locked_contract = contract.__class__.objects.select_for_update().get(pk=contract.pk)
    lifecycle_target = resolve_lifecycle_ready_contract(locked_contract)
    signed_version = lifecycle_target["signed_version"]
    if signed_version is None:
        raise LifecycleNotReadyError("Lifecycle is available only after the contract has a signed version.")

    lifecycle_contract = locked_contract
    source_exchange = lifecycle_target["source_exchange"]
    agreement, created = LifecycleAgreement.objects.get_or_create(
        contract=lifecycle_contract,
        defaults={
            "signed_version": signed_version,
            "source_exchange": source_exchange,
            "owner": user if getattr(user, "is_authenticated", False) else locked_contract.initiator,
            "status": LifecycleAgreement.STATUS_SETUP,
            "metadata": {"source": "signed_contract"},
        },
    )

    if created:
        LifecycleEvent.objects.create(
            lifecycle_agreement=agreement,
            event_type="timeline_setup_started",
            title="Timeline setup started",
            description="Agreement Timeline setup was opened for the signed contract.",
            metadata={
                "contract_id": str(lifecycle_contract.id),
                "signed_version_id": str(signed_version.id),
                "source_exchange_id": str(source_exchange.id) if source_exchange else None,
            },
        )

    ensure_signed_contract_timeline_records(agreement)
    return agreement

# Agreement Timeline management actions

PERFORMANCE_ACTIONS = {"mark_completed", "mark_paid", "mark_work_performed"}
CHANGE_ACTIONS = {"propose_change_order", "accept_change_order", "reject_change_order"}
ADD_ON_ACTIONS = {"propose_add_on", "accept_add_on", "reject_add_on"}
TIMELINE_ACTIONS = PERFORMANCE_ACTIONS | {
    "request_confirmation",
    "confirm_completion",
    "reject_completion",
    "add_note",
    "update_due_date",
    "upload_or_attach_document",
} | CHANGE_ACTIONS | ADD_ON_ACTIONS

ACTION_EVENT_MAP = {
    "mark_completed": "item_completed",
    "mark_paid": "payment_marked_paid",
    "mark_work_performed": "work_marked_performed",
    "request_confirmation": "confirmation_requested",
    "confirm_completion": "completion_confirmed",
    "reject_completion": "completion_rejected",
    "add_note": "note_added",
    "update_due_date": "due_date_changed",
    "upload_or_attach_document": "document_attached",
    "propose_change_order": "change_order_proposed",
    "accept_change_order": "change_order_accepted",
    "reject_change_order": "change_order_rejected",
    "propose_add_on": "add_on_proposed",
    "accept_add_on": "add_on_accepted",
    "reject_add_on": "add_on_rejected",
}

ACTION_TITLES = {
    "mark_completed": "Item completed",
    "mark_paid": "Payment marked paid",
    "mark_work_performed": "Work marked performed",
    "request_confirmation": "Confirmation requested",
    "confirm_completion": "Completion confirmed",
    "reject_completion": "Completion rejected",
    "add_note": "Note added",
    "update_due_date": "Due date changed",
    "upload_or_attach_document": "Document attached",
    "propose_change_order": "Change order proposed",
    "accept_change_order": "Change order accepted",
    "reject_change_order": "Change order rejected",
    "propose_add_on": "Add-on proposed",
    "accept_add_on": "Add-on accepted",
    "reject_add_on": "Add-on rejected",
    "contract_activated": "Contract activated",
}

ACTION_STATUSES = {
    "mark_completed": "completed",
    "mark_paid": "completed",
    "mark_work_performed": "completed",
    "confirm_completion": "confirmed",
    "reject_completion": "rejected",
    "propose_change_order": "proposed",
    "propose_add_on": "proposed",
    "accept_change_order": "confirmed",
    "accept_add_on": "confirmed",
    "reject_change_order": "rejected",
    "reject_add_on": "rejected",
}


DOCUMENT_IMAGE_MAX_SIZE = 25 * 1024 * 1024
VIDEO_MAX_SIZE = 100 * 1024 * 1024

ALLOWED_PROOF_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

PROOF_EXTENSION_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _actor_label(actor):
    name = " ".join(part for part in [getattr(actor, "first_name", ""), getattr(actor, "last_name", "")] if part).strip()
    return name or getattr(actor, "email", "") or "A party"


def _timeline_target_url(agreement):
    return f"/lifecycle?contract={agreement.contract_id}"


def _timeline_recipient(agreement, actor):
    contract = agreement.contract
    if actor and getattr(actor, "is_authenticated", False) and contract.initiator_id == actor.id:
        return find_user_by_email(contract.counterparty_email), contract.counterparty_email
    return contract.initiator, getattr(contract.initiator, "email", "")


def _normalise_party_token(value):
    return " ".join(str(value or "").strip().lower().split())


def _party_name(user):
    return _normalise_party_token(" ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part))


def _counterparty_user(contract):
    return find_user_by_email(contract.counterparty_email)


def _party_value_sets(agreement):
    contract = agreement.contract
    counterparty = _counterparty_user(contract)
    initiator_values = {
        str(contract.initiator_id or ""),
        _normalise_party_token(getattr(contract.initiator, "email", "")),
        _party_name(contract.initiator),
        "initiator",
        "owner",
        "lender",
        "provider",
    }
    counterparty_values = {
        _normalise_party_token(contract.counterparty_email),
        _normalise_party_token(contract.counterparty_name),
        str(getattr(counterparty, "id", "") or ""),
        _normalise_party_token(getattr(counterparty, "email", "")),
        _party_name(counterparty),
        "counterparty",
        "borrower",
        "client",
    }
    initiator_values.discard("")
    counterparty_values.discard("")
    return initiator_values, counterparty_values, counterparty


def _responsible_party_matches_user(agreement, item, user):
    if not getattr(user, "is_authenticated", False):
        return False
    responsible = _normalise_party_token(item.responsible_party)
    if not responsible:
        return False

    contract = agreement.contract
    initiator_values, counterparty_values, _counterparty = _party_value_sets(agreement)

    if contract.initiator_id == user.id and responsible in initiator_values:
        return True
    if _normalise_party_token(getattr(user, "email", "")) == _normalise_party_token(contract.counterparty_email) and responsible in counterparty_values:
        return True
    return False


def _responsible_party_user(agreement, item):
    responsible = _normalise_party_token(item.responsible_party)
    if not responsible:
        return None
    initiator_values, counterparty_values, counterparty = _party_value_sets(agreement)
    if responsible in initiator_values:
        return agreement.contract.initiator
    if responsible in counterparty_values:
        return counterparty
    return None


def can_user_upload_lifecycle_item_proof(item, user):
    agreement = item.lifecycle_agreement
    return _responsible_party_matches_user(agreement, item, user)


def can_user_respond_to_lifecycle_item_proof(item, user):
    if not getattr(user, "is_authenticated", False):
        return False
    agreement = item.lifecycle_agreement
    if _responsible_party_matches_user(agreement, item, user):
        return False
    contract = agreement.contract
    user_email = _normalise_party_token(getattr(user, "email", ""))
    is_counterparty = user_email and user_email == _normalise_party_token(contract.counterparty_email)
    is_initiator = contract.initiator_id == user.id
    if not (is_counterparty or is_initiator):
        return False
    return item.attachments.exists()


def _performance_target_url():
    return "/agreement-performance"


def _performance_metadata_action(action):
    if action == "mark_work_performed":
        return "mark_performed"
    return action


def _performance_action_result_label(item, action):
    if action == "mark_paid":
        return "Paid"
    if action in {"mark_work_performed", "mark_completed"}:
        return "Performed"
    return ACTION_TITLES.get(action, humanize_timeline_action(action))


def _proof_content_type(uploaded_file):
    filename = (getattr(uploaded_file, "name", "") or "").lower()
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower().strip()
    if content_type in ALLOWED_PROOF_CONTENT_TYPES:
        return content_type
    for extension, extension_content_type in PROOF_EXTENSION_CONTENT_TYPES.items():
        if filename.endswith(extension):
            return extension_content_type
    return content_type


def validate_lifecycle_item_attachment_file(uploaded_file):
    if not uploaded_file:
        raise ValueError("Proof file is required.")
    content_type = _proof_content_type(uploaded_file)
    if content_type not in ALLOWED_PROOF_CONTENT_TYPES:
        raise ValueError("Unsupported proof file type. Upload a PDF, image, video, DOC, or DOCX file.")
    size = getattr(uploaded_file, "size", 0) or 0
    limit = VIDEO_MAX_SIZE if content_type.startswith("video/") else DOCUMENT_IMAGE_MAX_SIZE
    if size > limit:
        max_mb = limit // (1024 * 1024)
        raise ValueError(f"Proof file is too large. Maximum size is {max_mb} MB for this file type.")
    return content_type, size


def _performance_notification_title(item, action):
    return _performance_action_result_label(item, action)


def _performance_notification_message(agreement, item, *, actor, action_title):
    return "\n".join([
        f"Agreement: {agreement.contract.title or 'Untitled contract'}",
        f"Item: {item.title}",
        f"Marked by: {_actor_label(actor)}",
        f"Action: {action_title}",
    ])


def notify_agreement_performance_counterparty(agreement, item, *, actor, action, event):
    recipient, _email = _timeline_recipient(agreement, actor)
    if not recipient or (getattr(actor, "is_authenticated", False) and recipient.id == actor.id):
        return None
    action_title = _performance_notification_title(item, action)
    notification = Notification.objects.create(
        user=recipient,
        notification_type="agreement_timeline",
        title=action_title,
        message=_performance_notification_message(agreement, item, actor=actor, action_title=action_title),
        related_contract=agreement.contract,
        metadata={
            "source": "agreement_performance_action",
            "action": _performance_metadata_action(action),
            "api_action": action,
            "contract_id": str(agreement.contract_id),
            "lifecycle_agreement_id": str(agreement.id),
            "lifecycle_item_id": str(item.id),
            "lifecycle_event_id": str(event.id),
            "attachment_id": str((event.metadata or {}).get("attachment_id") or "") or None,
            "item_title": item.title,
            "actor_id": str(actor.id) if getattr(actor, "is_authenticated", False) else None,
            "actor_label": _actor_label(actor),
            "target_url": _performance_target_url(),
            "redirect_url": _performance_target_url(),
        },
    )
    return {
        "in_app_created": True,
        "notification_id": str(notification.id),
        "recipient_id": str(recipient.id),
    }


def _proof_upload_message(agreement, item, *, actor, attachment):
    return "\n".join([
        f"Agreement: {agreement.contract.title or 'Untitled contract'}",
        f"Item: {item.title}",
        f"Uploaded by: {_actor_label(actor)}",
        f"File: {attachment.original_filename}",
    ])


def notify_agreement_performance_proof_counterparty(agreement, item, *, actor, attachment, event):
    recipient, _email = _timeline_recipient(agreement, actor)
    if not recipient or (getattr(actor, "is_authenticated", False) and recipient.id == actor.id):
        return None
    notification = Notification.objects.create(
        user=recipient,
        notification_type="agreement_timeline",
        title="Proof uploaded",
        message=_proof_upload_message(agreement, item, actor=actor, attachment=attachment),
        related_contract=agreement.contract,
        metadata={
            "source": "agreement_performance_proof",
            "action": "upload_proof",
            "contract_id": str(agreement.contract_id),
            "lifecycle_agreement_id": str(agreement.id),
            "lifecycle_item_id": str(item.id),
            "attachment_id": str(attachment.id),
            "lifecycle_event_id": str(event.id),
            "item_title": item.title,
            "actor_id": str(actor.id) if getattr(actor, "is_authenticated", False) else None,
            "actor_label": _actor_label(actor),
            "target_url": _performance_target_url(),
            "redirect_url": _performance_target_url(),
        },
    )
    return {
        "in_app_created": True,
        "notification_id": str(notification.id),
        "recipient_id": str(recipient.id),
    }


@transaction.atomic
def upload_lifecycle_item_attachment(item, user, uploaded_file, note="", *, create_event=True, notify_counterparty=True):
    agreement = LifecycleAgreement.objects.select_for_update(of=("self",)).select_related("contract", "contract__initiator").get(pk=item.lifecycle_agreement_id)
    item = LifecycleItem.objects.select_related("lifecycle_agreement", "lifecycle_agreement__contract").get(pk=item.pk)
    filename = getattr(uploaded_file, "name", "") or "proof"
    if not can_user_upload_lifecycle_item_proof(item, user):
        raise PermissionError("Only the responsible party can upload proof for this obligation.")
    content_type, file_size = validate_lifecycle_item_attachment_file(uploaded_file)
    attachment = LifecycleItemAttachment.objects.create(
        lifecycle_item=item,
        lifecycle_agreement=agreement,
        contract=agreement.contract,
        uploaded_by=user if getattr(user, "is_authenticated", False) else None,
        file=uploaded_file,
        original_filename=filename[:255],
        content_type=content_type[:120],
        file_size=file_size,
        note=(note or "").strip(),
    )
    if create_event:
        actor_label = _actor_label(user)
        event = create_timeline_event(
            agreement,
            event_type="proof_uploaded",
            title="Proof uploaded",
            description=f'{actor_label} uploaded proof for "{item.title}".',
            metadata={
                "source": "agreement_performance_proof",
                "action": "upload_proof",
                "contract_id": str(agreement.contract_id),
                "lifecycle_agreement_id": str(agreement.id),
                "item_id": str(item.id),
                "lifecycle_item_id": str(item.id),
                "item_type": item.item_type,
                "item_title": item.title,
                "attachment_id": str(attachment.id),
                "filename": attachment.original_filename,
                "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None,
                "actor_label": actor_label,
            },
        )
        notification = notify_agreement_performance_proof_counterparty(agreement, item, actor=user, attachment=attachment, event=event) if notify_counterparty else None
        if notification:
            event.metadata = {**(event.metadata or {}), "notification": notification}
            event.save(update_fields=["metadata"])
    return attachment




def _response_label(response):
    return {
        LifecycleItemResponse.RESPONSE_RECEIVED: "Received",
        LifecycleItemResponse.RESPONSE_STILL_WAITING: "Still waiting",
        LifecycleItemResponse.RESPONSE_NOT_RECEIVED: "Not received",
    }.get(response, humanize_timeline_action(response))


def _response_event_title(response):
    if response == LifecycleItemResponse.RESPONSE_RECEIVED:
        return "Received"
    if response == LifecycleItemResponse.RESPONSE_NOT_RECEIVED:
        return "Not received"
    return "Still waiting"


def _performance_response_message(agreement, item, *, actor, response):
    return "\n".join([
        f"Agreement: {agreement.contract.title or 'Untitled contract'}",
        f"Item: {item.title}",
        f"Response by: {_actor_label(actor)}",
        f"Response: {_response_label(response)}",
    ])


def notify_agreement_performance_response_recipient(agreement, item, *, actor, response, event):
    recipient = _responsible_party_user(agreement, item)
    if not recipient or (getattr(actor, "is_authenticated", False) and recipient.id == actor.id):
        return None
    notification = Notification.objects.create(
        user=recipient,
        notification_type="agreement_timeline",
        title=f"Response: {_response_label(response)}",
        message=_performance_response_message(agreement, item, actor=actor, response=response),
        related_contract=agreement.contract,
        metadata={
            "source": "agreement_performance_response",
            "action": response,
            "contract_id": str(agreement.contract_id),
            "lifecycle_agreement_id": str(agreement.id),
            "lifecycle_item_id": str(item.id),
            "lifecycle_event_id": str(event.id),
            "item_title": item.title,
            "actor_id": str(actor.id) if getattr(actor, "is_authenticated", False) else None,
            "actor_label": _actor_label(actor),
            "target_url": _performance_target_url(),
            "redirect_url": _performance_target_url(),
        },
    )
    return {
        "in_app_created": True,
        "notification_id": str(notification.id),
        "recipient_id": str(recipient.id),
    }


@transaction.atomic
def submit_lifecycle_item_response(item, user, response, note=""):
    if response not in {choice[0] for choice in LifecycleItemResponse.RESPONSE_CHOICES}:
        raise ValueError("Unsupported response.")
    agreement = LifecycleAgreement.objects.select_for_update(of=("self",)).select_related("contract", "contract__initiator").get(pk=item.lifecycle_agreement_id)
    item = LifecycleItem.objects.select_for_update(of=("self",)).select_related("lifecycle_agreement", "lifecycle_agreement__contract").get(pk=item.pk)
    if not can_user_respond_to_lifecycle_item_proof(item, user):
        raise PermissionError("Only the counterparty can respond to proof for this obligation.")

    item_response, _created = LifecycleItemResponse.objects.update_or_create(
        lifecycle_item=item,
        responder=user,
        defaults={
            "lifecycle_agreement": agreement,
            "contract": agreement.contract,
            "response": response,
            "note": (note or "").strip(),
        },
    )
    label = _response_event_title(response)
    actor_label = _actor_label(user)
    event = create_timeline_event(
        agreement,
        event_type="proof_response",
        title=label,
        description=f'{actor_label} responded "{label}" for "{item.title}".',
        metadata={
            "source": "agreement_performance_response",
            "action": response,
            "contract_id": str(agreement.contract_id),
            "lifecycle_agreement_id": str(agreement.id),
            "item_id": str(item.id),
            "lifecycle_item_id": str(item.id),
            "item_type": item.item_type,
            "item_title": item.title,
            "response_id": str(item_response.id),
            "response": response,
            "response_label": label,
            "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None,
            "actor_label": actor_label,
        },
    )
    notification = notify_agreement_performance_response_recipient(agreement, item, actor=user, response=response, event=event)
    if notification:
        event.metadata = {**(event.metadata or {}), "notification": notification}
        event.save(update_fields=["metadata"])
    return item_response


def _timeline_notification_message(agreement, item, *, actor, action_title):
    return "\n".join([
        f"Contract: {agreement.contract.title or 'Untitled contract'}",
        f"From: {_actor_label(actor)}",
        f"Timeline item: {item.title}",
        f"Action: {action_title}",
    ])


def notify_timeline_counterparty(agreement, item, *, actor, action, event_type):
    recipient, email = _timeline_recipient(agreement, actor)
    action_title = ACTION_TITLES.get(action, humanize_timeline_action(action))
    metadata = {
        "source": "agreement_timeline",
        "source_event": event_type,
        "action_type": action,
        "contract_id": str(agreement.contract_id),
        "timeline_id": str(agreement.id),
        "lifecycle_agreement_id": str(agreement.id),
        "item_id": str(item.id),
        "item_type": item.item_type,
        "item_title": item.title,
        "contract_title": agreement.contract.title or "Untitled contract",
        "actor_label": _actor_label(actor),
        "redirect_url": _timeline_target_url(agreement),
    }
    return notify_exchange_recipient(
        user=recipient,
        email=email,
        notification_type="agreement_timeline",
        title=action_title,
        message=_timeline_notification_message(agreement, item, actor=actor, action_title=action_title),
        contract=agreement.contract,
        metadata=metadata,
    )


def humanize_timeline_action(action):
    return str(action or "timeline_action").replace("_", " ").title()


def create_timeline_event(agreement, *, event_type, title, description="", metadata=None):
    return LifecycleEvent.objects.create(
        lifecycle_agreement=agreement,
        event_type=event_type,
        title=title,
        description=description,
        metadata=metadata or {},
    )


def _notification_delivered(result):
    return bool(result and (result.get("in_app_created") or result.get("email_sent") or result.get("email_attempted")))


def maybe_start_agreement_performance(agreement, action, actor):
    if action not in PERFORMANCE_ACTIONS:
        return False
    if agreement.status != LifecycleAgreement.STATUS_SETUP:
        return False
    agreement.status = LifecycleAgreement.STATUS_ACTIVE
    metadata = dict(agreement.metadata or {})
    metadata.setdefault("performance_started_at", timezone.now().isoformat())
    metadata.setdefault("performance_started_by", str(actor.id) if getattr(actor, "is_authenticated", False) else None)
    metadata.setdefault("performance_started_action", action)
    agreement.metadata = metadata
    agreement.save(update_fields=["status", "metadata", "updated_at"])
    return True


def create_timeline_item(agreement, user, data):
    from decimal import Decimal
    from django.utils.dateparse import parse_datetime
    from backend.contracts.models import LifecycleItem

    item_type = data.get("item_type")
    valid_types = {choice[0] for choice in LifecycleItem.ITEM_TYPE_CHOICES}
    if item_type not in valid_types:
        raise ValueError("Invalid timeline item type.")
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("title is required.")
    amount = data.get("amount")
    due_date = data.get("due_date") or None
    if isinstance(due_date, str):
        due_date = parse_datetime(due_date) if due_date else None
    source_type = data.get("source_type") or LifecycleItem.SOURCE_MANUAL
    source_id = data.get("source_id") or None
    source_label = data.get("source_label") or None
    source_version = data.get("source_version") or data.get("source_version_id") or None
    source_exchange = data.get("source_exchange") or data.get("source_exchange_id") or None
    is_contract_derived = data.get("is_contract_derived")
    locked_fields = data.get("locked_fields")
    item = LifecycleItem.objects.create(
        lifecycle_agreement=agreement,
        item_type=item_type,
        title=title,
        description=data.get("description") or "",
        responsible_party=data.get("responsible_party") or "",
        beneficiary_party=data.get("beneficiary_party") or "",
        due_date=due_date,
        amount=Decimal(str(amount)) if amount not in (None, "") else None,
        recurrence=data.get("recurrence") or None,
        status=data.get("status") or (LifecycleItem.STATUS_PROPOSED if item_type in {LifecycleItem.TYPE_CHANGE_ORDER, LifecycleItem.TYPE_ADD_ON} else LifecycleItem.STATUS_PENDING),
        source_type=source_type,
        source_id=source_id,
        source_label=source_label,
        source_version_id=getattr(source_version, "pk", source_version),
        source_exchange_id=getattr(source_exchange, "pk", source_exchange),
        is_contract_derived=bool(is_contract_derived) if is_contract_derived is not None else False,
        locked_fields=locked_fields if isinstance(locked_fields, list) else [],
        source_clause=data.get("source_clause") or None,
        metadata=data.get("metadata") or {},
        created_by=user if getattr(user, "is_authenticated", False) else None,
        visibility=data.get("visibility") or LifecycleItem.VISIBILITY_PARTIES,
    )
    create_timeline_event(
        agreement,
        event_type="item_created",
        title="Timeline item created",
        description=item.title,
        metadata={"item_id": str(item.id), "item_type": item.item_type, "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None},
    )
    return item


@transaction.atomic
def update_timeline_item(item, user, data):
    from decimal import Decimal
    from django.utils.dateparse import parse_datetime

    protected_origin_fields = {
        "source_type", "source_id", "source_label", "source_version", "source_version_id",
        "source_exchange", "source_exchange_id", "is_contract_derived", "locked_fields",
    }

    def _origin_field_value(field):
        if field in {"source_version", "source_version_id"}:
            return str(item.source_version_id) if item.source_version_id else None
        if field in {"source_exchange", "source_exchange_id"}:
            return str(item.source_exchange_id) if item.source_exchange_id else None
        return getattr(item, field)

    requested_origin_fields = []
    for field in sorted(protected_origin_fields):
        if field not in data:
            continue
        requested_value = data.get(field)
        current_value = _origin_field_value(field)
        if isinstance(current_value, bool):
            matches_current = requested_value is current_value
        elif isinstance(current_value, list):
            matches_current = requested_value == current_value
        else:
            matches_current = (requested_value or None) == (str(current_value) if current_value is not None else None)
        if not matches_current:
            requested_origin_fields.append(field)
    if requested_origin_fields:
        raise ValueError(f"Timeline item origin fields cannot be edited: {', '.join(requested_origin_fields)}.")

    overlay = _timeline_item_user_state(item, user, create=True)
    baseline_values = _timeline_item_baseline_values(item)
    current_metadata = dict(overlay.metadata or {})
    original_values = dict(current_metadata.get("original_values") or {})
    corrections = list(current_metadata.get("corrections") or [])
    changed_fields = []
    overlay_changed = False

    field_map = {
        "title": ("title_override", baseline_values["title"]),
        "description": ("description_override", baseline_values["description"]),
        "responsible_party": ("responsible_party_override", baseline_values["responsible_party"]),
        "amount": ("amount_override", baseline_values["amount"]),
        "due_date": ("due_date_override", baseline_values["due_date"]),
        "status": ("status_override", baseline_values["status"]),
        "payment_method": ("payment_method_override", baseline_values["payment_method"]),
    }

    def _normalise(value, field):
        if field == "amount":
            return Decimal(str(value)) if value not in (None, "") else None
        if field == "due_date":
            if isinstance(value, str):
                return parse_datetime(value) if value else None
            return value
        value = (value or "").strip()
        return value or None

    for field, (overlay_field, baseline_value) in field_map.items():
        if field not in data:
            continue
        value = _normalise(data.get(field), field)
        current_value = getattr(overlay, overlay_field)
        if current_value == value:
            continue
        if field not in original_values:
            original_values[field] = baseline_value
        setattr(overlay, overlay_field, value)
        changed_fields.append(field)
        overlay_changed = True

    if "notes" in data:
        notes = (data.get("notes") or "").strip()
        if overlay.notes != notes:
            overlay.notes = notes
            changed_fields.append("notes")
            overlay_changed = True

    if "reminder_at" in data:
        reminder_at = data.get("reminder_at") or None
        if isinstance(reminder_at, str):
            reminder_at = parse_datetime(reminder_at) if reminder_at else None
        if overlay.reminder_at != reminder_at:
            overlay.reminder_at = reminder_at
            changed_fields.append("reminder_at")
            overlay_changed = True

    if original_values:
        current_metadata["original_values"] = original_values
    if changed_fields:
        corrections.append({
            "updated_fields": changed_fields,
            "corrected_at": timezone.now().isoformat(),
            "corrected_by": str(user.id) if getattr(user, "is_authenticated", False) else None,
        })
        current_metadata["corrections"] = corrections
        overlay_changed = True

    if overlay_changed:
        overlay.metadata = current_metadata
        overlay.save()
    return item


@transaction.atomic
def perform_timeline_item_action(item, user, action, data=None):
    from django.utils.dateparse import parse_datetime
    from backend.contracts.models import LifecycleItem

    data = data or {}
    if action not in TIMELINE_ACTIONS:
        raise ValueError("Unsupported timeline action.")

    agreement = LifecycleAgreement.objects.select_for_update(of=("self",)).select_related("contract", "contract__initiator").get(pk=item.lifecycle_agreement_id)
    item = LifecycleItem.objects.select_for_update(of=("self",)).select_related("lifecycle_agreement", "lifecycle_agreement__contract").get(pk=item.pk)

    if action in PERFORMANCE_ACTIONS:
        if not _responsible_party_matches_user(agreement, item, user):
            raise PermissionError("Only the responsible party can mark this obligation performed.")
        target_status = ACTION_STATUSES.get(action)
        if target_status and item.status == target_status:
            return item
        uploaded_file = data.get("file") if hasattr(data, "get") else None
        if uploaded_file:
            validate_lifecycle_item_attachment_file(uploaded_file)
        elif not LifecycleItemAttachment.objects.filter(lifecycle_item=item, uploaded_by=user).exists():
            raise ValueError("Upload proof or receipt below before marking this obligation performed.")

    metadata = dict(item.metadata or {})
    note = data.get("note") or data.get("message") or ""
    if note:
        metadata.setdefault("notes", []).append({"action": action, "note": note, "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None})
    if action == "update_due_date":
        due_date = data.get("due_date")
        if not due_date:
            raise ValueError("due_date is required.")
        item.due_date = parse_datetime(due_date) if isinstance(due_date, str) else due_date
    if action in {"upload_or_attach_document"}:
        metadata.setdefault("documents", []).append({"title": data.get("document_title") or data.get("title") or "Document", "url": data.get("document_url") or ""})
    attachment = None
    if action in PERFORMANCE_ACTIONS:
        uploaded_file = data.get("file") if hasattr(data, "get") else None
        if uploaded_file:
            attachment = upload_lifecycle_item_attachment(
                item,
                user,
                uploaded_file,
                note,
                create_event=False,
                notify_counterparty=False,
            )
        else:
            attachment = (
                LifecycleItemAttachment.objects
                .filter(lifecycle_item=item, uploaded_by=user)
                .order_by("-created_at")
                .first()
            )
    if action in ACTION_STATUSES:
        item.status = ACTION_STATUSES[action]
    if action in PERFORMANCE_ACTIONS:
        metadata.setdefault("performance_actions", {})[action] = {
            "status": item.status,
            "acted_at": timezone.now().isoformat(),
            "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None,
            "attachment_id": str(attachment.id) if attachment else None,
        }
    if action == "propose_change_order":
        item.item_type = LifecycleItem.TYPE_CHANGE_ORDER
    if action == "propose_add_on":
        item.item_type = LifecycleItem.TYPE_ADD_ON
    item.metadata = metadata
    item.save(update_fields=["item_type", "status", "due_date", "metadata", "updated_at"])

    event_type = ACTION_EVENT_MAP[action]
    title = _performance_action_result_label(item, action) if action in PERFORMANCE_ACTIONS else ACTION_TITLES[action]
    performance_started = False
    if action in PERFORMANCE_ACTIONS:
        performance_started = maybe_start_agreement_performance(agreement, action, user)

    event = create_timeline_event(
        agreement,
        event_type=event_type,
        title=title,
        description=note or item.title,
        metadata={
            "item_id": str(item.id),
            "lifecycle_item_id": str(item.id),
            "item_type": item.item_type,
            "action": action,
            "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None,
            "actor_label": _actor_label(user),
            "status": item.status,
            "result_status": item.status,
            "result_label": title,
            "attachment_id": str(attachment.id) if attachment else None,
            "performance_started": performance_started,
        },
    )

    notification = None
    if action in PERFORMANCE_ACTIONS:
        notification = notify_agreement_performance_counterparty(agreement, item, actor=user, action=action, event=event)
    elif action != "add_note" and action != "upload_or_attach_document":
        notification = notify_timeline_counterparty(agreement, item, actor=user, action=action, event_type=event_type)
    if notification:
        event.metadata = {**(event.metadata or {}), "notification": notification}
        event.save(update_fields=["metadata"])
    return item
