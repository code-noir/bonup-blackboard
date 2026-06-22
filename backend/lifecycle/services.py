from django.db import transaction

from backend.agreement_exchange.models import AgreementExchange
from backend.agreement_exchange.notifications import find_user_by_email, notify_exchange_recipient
from backend.contracts.models import ContractVersion, LifecycleAgreement, LifecycleEvent


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


def maybe_activate_contract_from_timeline_action(agreement, action, actor, notification_result):
    if action not in PERFORMANCE_ACTIONS:
        return False
    if agreement.contract.status == "active" and agreement.status == LifecycleAgreement.STATUS_ACTIVE:
        return False
    if not _notification_delivered(notification_result):
        return False

    contract = agreement.contract
    if contract.status == "signed":
        contract.status = "active"
        contract.save(update_fields=["status"])
    if agreement.status == LifecycleAgreement.STATUS_SETUP:
        agreement.status = LifecycleAgreement.STATUS_ACTIVE
        agreement.save(update_fields=["status", "updated_at"])
    create_timeline_event(
        agreement,
        event_type="contract_activated",
        title=ACTION_TITLES["contract_activated"],
        description="The first notified performance action activated this signed agreement.",
        metadata={"action": action, "actor_id": str(actor.id) if getattr(actor, "is_authenticated", False) else None},
    )
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


def update_timeline_item(item, user, data):
    from decimal import Decimal
    from django.utils.dateparse import parse_datetime

    protected_origin_fields = {
        "source_type", "source_id", "source_label", "source_version", "source_version_id",
        "source_exchange", "source_exchange_id", "is_contract_derived", "locked_fields",
    }
    requested_origin_fields = sorted(field for field in protected_origin_fields if field in data)
    if requested_origin_fields:
        raise ValueError(f"Timeline item origin fields cannot be edited: {', '.join(requested_origin_fields)}.")

    allowed = {
        "title", "description", "responsible_party", "beneficiary_party", "due_date", "amount",
        "recurrence", "status", "source_clause", "metadata", "visibility",
    }
    if item.is_contract_derived:
        locked_fields = set(item.locked_fields or [])
        requested_locked_fields = sorted(field for field in locked_fields if field in data and field in allowed)
        if requested_locked_fields:
            raise ValueError(f"Contract-derived timeline fields cannot be edited: {', '.join(requested_locked_fields)}.")

    update_fields = []
    for field in allowed:
        if field not in data:
            continue
        value = data[field]
        if field == "amount":
            value = Decimal(str(value)) if value not in (None, "") else None
        elif field == "due_date":
            value = parse_datetime(value) if isinstance(value, str) and value else None
        setattr(item, field, value)
        update_fields.append(field)
    if update_fields:
        update_fields.append("updated_at")
        item.save(update_fields=update_fields)
        create_timeline_event(
            item.lifecycle_agreement,
            event_type="item_updated",
            title="Timeline item updated",
            description=item.title,
            metadata={"item_id": str(item.id), "updated_fields": update_fields, "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None},
        )
    return item


@transaction.atomic
def perform_timeline_item_action(item, user, action, data=None):
    from django.utils.dateparse import parse_datetime
    from backend.contracts.models import LifecycleItem

    data = data or {}
    if action not in TIMELINE_ACTIONS:
        raise ValueError("Unsupported timeline action.")

    agreement = LifecycleAgreement.objects.select_for_update().select_related("contract", "contract__initiator").get(pk=item.lifecycle_agreement_id)
    item = LifecycleItem.objects.select_for_update().select_related("lifecycle_agreement", "lifecycle_agreement__contract").get(pk=item.pk)

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
    if action in ACTION_STATUSES:
        item.status = ACTION_STATUSES[action]
    if action == "propose_change_order":
        item.item_type = LifecycleItem.TYPE_CHANGE_ORDER
    if action == "propose_add_on":
        item.item_type = LifecycleItem.TYPE_ADD_ON
    item.metadata = metadata
    item.save(update_fields=["item_type", "status", "due_date", "metadata", "updated_at"])

    event_type = ACTION_EVENT_MAP[action]
    title = ACTION_TITLES[action]
    notification = None
    if action != "add_note" and action != "upload_or_attach_document":
        notification = notify_timeline_counterparty(agreement, item, actor=user, action=action, event_type=event_type)

    create_timeline_event(
        agreement,
        event_type=event_type,
        title=title,
        description=note or item.title,
        metadata={
            "item_id": str(item.id),
            "item_type": item.item_type,
            "action": action,
            "actor_id": str(user.id) if getattr(user, "is_authenticated", False) else None,
            "notification": notification or {},
        },
    )
    maybe_activate_contract_from_timeline_action(agreement, action, user, notification)
    return item
