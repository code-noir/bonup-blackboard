from django.db import DatabaseError, connection
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.permissions import contract_party_response, is_party
from backend.contracts.models import (
    Contract,
    ContractObligation,
    ContractServiceObligation,
    LifecycleAgreement,
    LifecycleChangeProposal,
    LifecycleChangeProposalMessage,
    LifecycleItem,
    LifecycleItemMessage,
    LifecycleItemResponse,
    LifecycleItemUserState,
)
from backend.lifecycle.services import (
    LifecycleNotReadyError,
    can_user_respond_to_lifecycle_item_proof,
    can_user_upload_lifecycle_item_proof,
    create_lifecycle_change_proposal,
    create_lifecycle_change_proposal_message,
    decide_lifecycle_change_proposal,
    create_lifecycle_item_message,
    create_timeline_item,
    get_or_create_lifecycle_for_signed_contract,
    perform_timeline_item_action,
    submit_lifecycle_item_response,
    update_timeline_item,
    upload_lifecycle_item_attachment,
)
from backend.payments.models import Payment


_GROUPS = {
    LifecycleItem.TYPE_OBLIGATION: "obligations",
    LifecycleItem.TYPE_RESPONSIBILITY: "obligations",
    LifecycleItem.TYPE_PAYMENT: "payments",
    LifecycleItem.TYPE_DEADLINE: "deadlines",
    LifecycleItem.TYPE_DUE_DATE: "deadlines",
    LifecycleItem.TYPE_SERVICE: "services",
    LifecycleItem.TYPE_SERVICE_WORK: "services",
    LifecycleItem.TYPE_NOTICE: "notices",
    LifecycleItem.TYPE_DOCUMENT: "documents",
    LifecycleItem.TYPE_RISK: "risks",
    LifecycleItem.TYPE_CHANGE_ORDER: "changes",
    LifecycleItem.TYPE_ADD_ON: "changes",
    LifecycleItem.TYPE_NOTE: "notes",
}


def _iso(value):
    return value.isoformat() if value else None


def _money(value):
    return str(value) if value is not None else None


def _party_summary(user):
    if not user:
        return None
    name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return {"id": str(user.id), "email": user.email, "name": name}


def _attachment_summary(attachment):
    file_url = ""
    if attachment.file:
        try:
            file_url = attachment.file.url
        except ValueError:
            file_url = ""
    return {
        "id": str(attachment.id),
        "lifecycle_item_id": str(attachment.lifecycle_item_id),
        "lifecycle_agreement_id": str(attachment.lifecycle_agreement_id),
        "contract_id": str(attachment.contract_id),
        "filename": attachment.original_filename,
        "original_filename": attachment.original_filename,
        "content_type": attachment.content_type,
        "file_size": attachment.file_size,
        "kind": attachment.kind,
        "note": attachment.note,
        "uploaded_by": _party_summary(attachment.uploaded_by),
        "uploaded_by_email": attachment.uploaded_by.email if attachment.uploaded_by else None,
        "created_at": _iso(attachment.created_at),
        "updated_at": _iso(attachment.updated_at),
        "file_url": file_url,
    }


def _message_summary(message, user=None):
    return {
        "id": str(message.id),
        "lifecycle_item_id": str(message.lifecycle_item_id),
        "lifecycle_agreement_id": str(message.lifecycle_agreement_id),
        "contract_id": str(message.contract_id),
        "body": message.body,
        "sender": _party_summary(message.sender),
        "sender_email": message.sender.email if message.sender else None,
        "created_at": _iso(message.created_at),
        "updated_at": _iso(message.updated_at),
        "is_mine": bool(user and getattr(user, "is_authenticated", False) and message.sender_id == user.id),
    }


def _responsible_party_label(agreement, value):
    if value == LifecycleChangeProposal.RESPONSIBLE_INITIATOR:
        user = agreement.contract.initiator
        return (" ".join(part for part in [user.first_name, user.last_name] if part).strip() or user.email or "Initiator") if user else "Initiator"
    if value == LifecycleChangeProposal.RESPONSIBLE_COUNTERPARTY:
        return agreement.contract.counterparty_name or agreement.contract.counterparty_email or "Counterparty"
    return ""


def _proposal_party_option_label(role_label, display_label):
    cleaned = (display_label or "").strip()
    if cleaned and cleaned.lower() != role_label.lower():
        return f"{role_label} / {cleaned}"
    return role_label


def _proposal_party_options(agreement):
    initiator = agreement.contract.initiator
    initiator_name = (" ".join(part for part in [initiator.first_name, initiator.last_name] if part).strip() or initiator.email or "") if initiator else ""
    counterparty_name = agreement.contract.counterparty_name or agreement.contract.counterparty_email or ""
    return [
        {"value": LifecycleChangeProposal.RESPONSIBLE_INITIATOR, "label": _proposal_party_option_label("Initiator", initiator_name), "email": initiator.email if initiator else None},
        {"value": LifecycleChangeProposal.RESPONSIBLE_COUNTERPARTY, "label": _proposal_party_option_label("Counterparty", counterparty_name), "email": agreement.contract.counterparty_email},
    ]


def _proposal_affected_item_summary(item):
    if not item:
        return None
    return {
        "id": str(item.id),
        "title": item.title,
        "item_type": item.item_type,
        "status": item.status,
        "due_date": _iso(item.due_date),
        "amount": _money(item.amount),
        "responsible_party": item.responsible_party,
    }


def _accepted_add_on_items_for_proposal(proposal):
    if proposal.proposal_type != LifecycleChangeProposal.TYPE_ADD_ON:
        return []
    source_prefix = f"lifecycle_change_proposal:{proposal.id}"
    items = (
        LifecycleItem.objects
        .filter(
            lifecycle_agreement=proposal.lifecycle_agreement,
            source_type=LifecycleItem.SOURCE_ADD_ON,
            source_id__startswith=source_prefix,
        )
        .order_by("due_date", "created_at")
    )
    return [item for item in items if not (item.metadata or {}).get("superseded_by_add_on_generation")]


def _change_proposal_summary(proposal, user=None):
    agreement = proposal.lifecycle_agreement
    is_proposer = bool(user and getattr(user, "is_authenticated", False) and proposal.proposed_by_id == user.id)
    can_decide = bool(user and getattr(user, "is_authenticated", False) and proposal.status == LifecycleChangeProposal.STATUS_PROPOSED and proposal.proposed_by_id != user.id)
    created_items = _accepted_add_on_items_for_proposal(proposal)
    created_item = created_items[0] if created_items else None
    return {
        "id": str(proposal.id),
        "lifecycle_agreement_id": str(proposal.lifecycle_agreement_id),
        "contract_id": str(proposal.contract_id),
        "contract_title": proposal.contract.title if proposal.contract else None,
        "proposal_type": proposal.proposal_type,
        "status": proposal.status,
        "proposed_by": _party_summary(proposal.proposed_by),
        "proposed_by_email": proposal.proposed_by.email if proposal.proposed_by else None,
        "affected_item": _proposal_affected_item_summary(proposal.affected_item),
        "affected_item_id": str(proposal.affected_item_id) if proposal.affected_item_id else None,
        "created_item": _proposal_affected_item_summary(created_item),
        "created_item_id": str(created_item.id) if created_item else None,
        "created_items": [_proposal_affected_item_summary(item) for item in created_items],
        "created_item_ids": [str(item.id) for item in created_items],
        "generated_item_count": len(created_items),
        "generation_mode": getattr(proposal, "generation_mode", "single") or "single",
        "title": proposal.title,
        "description": proposal.description,
        "responsible_party": proposal.responsible_party,
        "responsible_party_label": _responsible_party_label(agreement, proposal.responsible_party),
        "amount": _money(proposal.amount),
        "due_date": proposal.due_date.isoformat() if proposal.due_date else None,
        "note": proposal.note,
        "final_due_date": proposal.final_due_date.isoformat() if getattr(proposal, "final_due_date", None) else None,
        "final_amount": _money(getattr(proposal, "final_amount", None)),
        "final_responsible_party": getattr(proposal, "final_responsible_party", "") or "",
        "created_at": _iso(proposal.created_at),
        "updated_at": _iso(proposal.updated_at),
        "decided_by": _party_summary(proposal.decided_by),
        "decided_at": _iso(proposal.decided_at),
        "decision_note": getattr(proposal, "decision_note", "") or "",
        "is_proposer": is_proposer,
        "can_decide": can_decide,
    }


def _change_proposal_message_summary(message, user=None):
    return {
        "id": str(message.id),
        "proposal_id": str(message.proposal_id),
        "lifecycle_agreement_id": str(message.lifecycle_agreement_id),
        "contract_id": str(message.contract_id),
        "body": message.body,
        "sender": _party_summary(message.sender),
        "sender_email": message.sender.email if message.sender else None,
        "created_at": _iso(message.created_at),
        "updated_at": _iso(message.updated_at),
        "is_mine": bool(user and getattr(user, "is_authenticated", False) and message.sender_id == user.id),
    }



def _response_summary(response):
    if not response:
        return None
    return {
        "id": str(response.id),
        "lifecycle_item_id": str(response.lifecycle_item_id),
        "lifecycle_agreement_id": str(response.lifecycle_agreement_id),
        "contract_id": str(response.contract_id),
        "response": response.response,
        "note": response.note,
        "responder": _party_summary(response.responder),
        "created_at": _iso(response.created_at),
        "updated_at": _iso(response.updated_at),
    }


def _model_table_exists(model):
    try:
        return model._meta.db_table in connection.introspection.table_names()
    except DatabaseError:
        return False


def _latest_response_summary(item):
    if not _model_table_exists(LifecycleItemResponse):
        return None
    try:
        response = item.counterparty_responses.select_related("responder").order_by("-updated_at", "-created_at").first()
    except DatabaseError:
        return None
    return _response_summary(response)


def _contract_summary(contract):
    return {
        "id": str(contract.id),
        "title": contract.title or "Untitled contract",
        "status": contract.status,
        "state": contract.state,
        "counterparty_name": contract.counterparty_name,
        "counterparty_email": contract.counterparty_email,
        "created_at": _iso(contract.created_at),
    }


def _signed_version_summary(version):
    return {
        "id": str(version.id),
        "version_number": version.version_number,
        "label": f"v{version.version_number}",
        "status": version.status,
        "content_snapshot": version.content_snapshot,
        "created_at": _iso(version.created_at),
    }


def _lifecycle_summary(agreement):
    return {
        "id": str(agreement.id),
        "status": agreement.status,
        "started_at": _iso(agreement.started_at),
        "source_exchange_id": str(agreement.source_exchange_id) if agreement.source_exchange_id else None,
        "performance_ready": agreement.performance_ready,
        "performance_ready_at": _iso(agreement.performance_ready_at),
        "performance_ready_by": str(agreement.performance_ready_by_id) if agreement.performance_ready_by_id else None,
        "metadata": agreement.metadata or {},
    }


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
        "due_date": _iso(item.due_date),
        "amount": _money(item.amount),
        "responsible_party": item.responsible_party,
        "payment_method": _payment_method_from_metadata(metadata),
        "status": item.status,
    }



def _uses_shared_tracking_fields(item):
    agreement = getattr(item, "lifecycle_agreement", None)
    return bool(agreement and (agreement.metadata or {}).get("source") == "signed_contract")


def _timeline_item_overlay_state(item, overlay):
    baseline = _timeline_item_baseline_values(item)
    if overlay is None:
        return baseline
    shared_status = baseline["status"]
    personal_status = overlay.status_override if overlay.status_override is not None else shared_status
    status = shared_status if shared_status in {"completed", "confirmed", "cancelled", "rejected"} else personal_status
    if _uses_shared_tracking_fields(item):
        return {
            "title": baseline["title"],
            "description": baseline["description"],
            "due_date": baseline["due_date"],
            "amount": baseline["amount"],
            "responsible_party": baseline["responsible_party"],
            "payment_method": overlay.payment_method_override if overlay.payment_method_override is not None else baseline["payment_method"],
            "status": status,
        }
    return {
        "title": overlay.title_override if overlay.title_override is not None else baseline["title"],
        "description": overlay.description_override if overlay.description_override is not None else baseline["description"],
        "due_date": _iso(overlay.due_date_override) if overlay.due_date_override else baseline["due_date"],
        "amount": _money(overlay.amount_override) if overlay.amount_override is not None else baseline["amount"],
        "responsible_party": overlay.responsible_party_override if overlay.responsible_party_override is not None else baseline["responsible_party"],
        "payment_method": overlay.payment_method_override if overlay.payment_method_override is not None else baseline["payment_method"],
        "status": status,
    }



def _serialize_lifecycle_item(item, overlay=None, user=None):
    source_type = getattr(item, "source_type", "manual") or "manual"
    metadata = item.metadata or {}
    state = _timeline_item_overlay_state(item, overlay)
    baseline_values = _timeline_item_baseline_values(item)
    overlay_metadata = getattr(overlay, "metadata", {}) or {}
    has_personal_overrides = bool(overlay and any(
        value not in (None, "", [])
        for value in (
            overlay.title_override,
            overlay.description_override,
            overlay.due_date_override,
            overlay.amount_override,
            overlay.responsible_party_override,
            overlay.payment_method_override,
            overlay.status_override,
            overlay.notes,
            overlay.reminder_at,
            overlay_metadata,
        )
    ))
    return {
        "id": str(item.id),
        "source": source_type,
        "source_type": source_type,
        "source_id": item.source_id,
        "source_label": item.source_label,
        "source_version_id": str(item.source_version_id) if item.source_version_id else None,
        "source_exchange_id": str(item.source_exchange_id) if item.source_exchange_id else None,
        "is_contract_derived": getattr(item, "is_contract_derived", False),
        "locked_fields": getattr(item, "locked_fields", []) or [],
        "item_type": item.item_type,
        "title": state["title"],
        "description": state["description"],
        "responsible_party": state["responsible_party"],
        "beneficiary_party": item.beneficiary_party,
        "due_date": state["due_date"],
        "amount": state["amount"],
        "recurrence": item.recurrence,
        "status": state["status"],
        "payment_method": state["payment_method"],
        "notes": overlay.notes if overlay is not None else "",
        "reminder_at": _iso(overlay.reminder_at) if overlay is not None and overlay.reminder_at else None,
        "source_clause": item.source_clause,
        "metadata": metadata,
        "manual_tracking_edit": metadata.get("manual_tracking_edit", False),
        "due_date_source": metadata.get("due_date_source"),
        "tracking_edited_by": metadata.get("tracking_edited_by"),
        "tracking_edited_at": metadata.get("tracking_edited_at"),
        "tracking_edit_reason": metadata.get("tracking_edit_reason"),
        "material_tracking_change": metadata.get("material_tracking_change", False),
        "baseline_values": baseline_values,
        "has_personal_overrides": has_personal_overrides,
        "created_by": str(item.created_by_id) if getattr(item, "created_by_id", None) else None,
        "visibility": getattr(item, "visibility", "parties"),
        "can_upload_proof": can_user_upload_lifecycle_item_proof(item, user) if user is not None else False,
        "can_respond_to_proof": can_user_respond_to_lifecycle_item_proof(item, user) if user is not None else False,
        "latest_response": _latest_response_summary(item),
    }


def _serialize_payment_obligation(obligation):
    return {
        "id": str(obligation.id),
        "source": "contract_payment_obligation",
        "item_type": "payment",
        "title": f"Payment installment {obligation.installment_number}",
        "description": "",
        "responsible_party": str(obligation.obligor_id),
        "beneficiary_party": str(obligation.obligee_id),
        "due_date": _iso(obligation.due_date),
        "amount": _money(obligation.amount_due),
        "amount_paid": _money(obligation.amount_paid),
        "currency": obligation.currency,
        "recurrence": None,
        "status": "completed" if obligation.state == "resolved" else "pending",
        "lifecycle_state": obligation.state,
        "source_clause": None,
        "metadata": {"version_id": str(obligation.version_id)},
    }


def _serialize_service_obligation(obligation):
    return {
        "id": str(obligation.id),
        "source": "contract_service_obligation",
        "item_type": "service",
        "title": obligation.description[:120] or "Service obligation",
        "description": obligation.description,
        "responsible_party": str(obligation.obligor_id),
        "beneficiary_party": str(obligation.obligee_id),
        "due_date": _iso(obligation.due_date),
        "amount": None,
        "recurrence": None,
        "status": "completed" if obligation.state == "resolved" else "pending",
        "lifecycle_state": obligation.state,
        "source_clause": None,
        "metadata": {"version_id": str(obligation.version_id), "completed_at": _iso(obligation.completed_at)},
    }


def _serialize_payment(payment):
    return {
        "id": str(payment.id),
        "source": "payment_record",
        "item_type": "payment",
        "title": f"Payment {payment.status}",
        "description": payment.reference or "",
        "responsible_party": str(payment.payer_id),
        "beneficiary_party": str(payment.payee_id),
        "due_date": None,
        "amount": _money(payment.amount),
        "currency": payment.currency,
        "recurrence": None,
        "status": "completed" if payment.status == "confirmed" else "pending",
        "payment_status": payment.status,
        "source_clause": None,
        "metadata": payment.metadata or {},
    }


def _empty_groups():
    return {
        "obligations": [],
        "payments": [],
        "deadlines": [],
        "services": [],
        "notices": [],
        "documents": [],
        "risks": [],
        "changes": [],
        "notes": [],
    }


def _looks_like_whole_contract_text(value):
    if not value:
        return False
    normalized = " ".join(str(value).lower().split())
    if len(normalized) < 500:
        return False
    markers = [
        "agreement is made between",
        "personal repayment agreement",
        "governing law",
        "signatures",
        "borrower",
        "lender",
        "provider",
        "client",
    ]
    return "agreement" in normalized and sum(1 for marker in markers if marker in normalized) >= 2


def _is_whole_contract_timeline_item(item):
    return _looks_like_whole_contract_text(item.get("title")) or _looks_like_whole_contract_text(item.get("description"))


def _append_timeline_item(grouped, group_name, item):
    if _is_whole_contract_timeline_item(item):
        return
    grouped[group_name].append(item)


def _is_signed_contract_document(item):
    return (
        item.item_type == LifecycleItem.TYPE_DOCUMENT
        and getattr(item, "source_type", None) == LifecycleItem.SOURCE_ORIGINAL_CONTRACT
    )


def _is_signed_contract_lifecycle(agreement):
    return (agreement.metadata or {}).get("source") == "signed_contract"


def _group_items(agreement, overlays_by_item_id=None, user=None):
    grouped = _empty_groups()
    overlays_by_item_id = overlays_by_item_id or {}
    for item in agreement.items.all():
        if _is_signed_contract_document(item):
            continue
        overlay = overlays_by_item_id.get(str(item.id))
        _append_timeline_item(grouped, _GROUPS[item.item_type], _serialize_lifecycle_item(item, overlay, user))

    if _is_signed_contract_lifecycle(agreement):
        return grouped

    for obligation in ContractObligation.objects.filter(contract=agreement.contract).order_by("due_date"):
        grouped["payments"].append(_serialize_payment_obligation(obligation))

    for obligation in ContractServiceObligation.objects.filter(contract=agreement.contract).order_by("due_date"):
        _append_timeline_item(grouped, "services", _serialize_service_obligation(obligation))

    for payment in Payment.objects.filter(contract=agreement.contract).order_by("-created_at"):
        grouped["payments"].append(_serialize_payment(payment))

    return grouped


def _serialize_event(event):
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "title": event.title,
        "description": event.description,
        "occurred_at": _iso(event.occurred_at),
        "metadata": event.metadata or {},
    }


def _is_open_timeline_status(item):
    return item.get("status") not in {"completed", "confirmed", "cancelled", "rejected"}


def _is_generated_repayment_schedule_item(item):
    return (
        item.get("source_type") == LifecycleItem.SOURCE_ORIGINAL_CONTRACT
        and str(item.get("source_id") or "").startswith("repayment_schedule:")
    )


def _is_loan_delivery_work_item(item):
    return str(item.get("source_id") or "").startswith("loan_delivery_work:")


def _normalise_status_key(value):
    return str(value or "").strip().lower()


def _is_completed_timeline_status(item):
    return _normalise_status_key(item.get("status")) in {"completed", "confirmed", "resolved"}


def _deadline_relation_key(item):
    return (
        item.get("due_date") or "",
        _normalise_status_key(item.get("responsible_party")),
        str(item.get("amount") or ""),
    )


def _source_related_deadline_key(item):
    source_id = str(item.get("source_id") or "")
    if source_id.startswith("loan_delivery_work:"):
        return source_id.replace("loan_delivery_work:", "loan_delivery:", 1)
    return ""


def _apply_related_deadline_statuses(action_items):
    completed_by_key = {}
    completed_by_source_deadline = {}
    for item in action_items:
        if item.get("item_type") in {"due_date", "deadline"}:
            continue
        if not _is_completed_timeline_status(item):
            continue
        completed_by_key.setdefault(_deadline_relation_key(item), item)
        related_source_id = _source_related_deadline_key(item)
        if related_source_id:
            completed_by_source_deadline[related_source_id] = item

    for item in action_items:
        if item.get("item_type") not in {"due_date", "deadline"}:
            continue
        if _is_completed_timeline_status(item):
            continue
        related = completed_by_source_deadline.get(str(item.get("source_id") or "")) or completed_by_key.get(_deadline_relation_key(item))
        if not related:
            continue
        item["status"] = related.get("status")
        metadata = dict(item.get("metadata") or {})
        metadata["related_performance_item_id"] = related.get("id")
        metadata["related_performance_item_type"] = related.get("item_type")
        item["metadata"] = metadata


def _without_legacy_generated_payment_sources(items, has_generated_repayment_schedule):
    if not has_generated_repayment_schedule:
        return items
    return [
        item for item in items
        if item.get("source") not in {"contract_payment_obligation", "payment_record"}
    ]


def _is_superseded_add_on_item(item):
    return bool((item.get("metadata") or {}).get("superseded_by_add_on_generation"))


def _chronological_worklist_items(items):
    return sorted(items, key=lambda item: (item.get("due_date") is None, item.get("due_date") or "", item.get("title") or "", item.get("id") or ""))


def _grouped_views(grouped, events):
    all_items = [item for values in grouped.values() for item in values]
    all_items = [item for item in all_items if not _is_superseded_add_on_item(item)]
    has_generated_repayment_schedule = any(_is_generated_repayment_schedule_item(item) for item in grouped["payments"])
    action_items = _without_legacy_generated_payment_sources(all_items, has_generated_repayment_schedule)
    _apply_related_deadline_statuses(action_items)
    due_dated_action_items = [
        item for item in action_items
        if item.get("due_date")
        and item.get("item_type") in {"payment", "service", "service_work", "responsibility", "obligation", "due_date", "deadline"}
    ]
    upcoming = sorted(due_dated_action_items, key=lambda item: item.get("due_date") or "")[:10]
    payment_items = _without_legacy_generated_payment_sources(grouped["payments"], has_generated_repayment_schedule)
    return {
        "upcoming": upcoming,
        "to_dos": [item for item in grouped["obligations"] if item.get("item_type") in {"responsibility", "obligation"}],
        "payments": [item for item in payment_items if item.get("item_type") == "payment"],
        "due_dates": sorted(due_dated_action_items, key=lambda item: item.get("due_date") or ""),
        "work_services": [item for item in grouped["services"] if item.get("item_type") in {"service", "service_work"} and not _is_superseded_add_on_item(item)],
        "my_obligations": _chronological_worklist_items([item for item in action_items if item.get("can_upload_proof")]),
        "changes_add_ons": [item for item in grouped["changes"] if item.get("item_type") in {"change_order", "add_on"}],
        "activity": events,
        "documents": [item for item in grouped["documents"] if item.get("item_type") == "document"],
    }


def _item_counts(grouped):
    counts = {key: len(value) for key, value in grouped.items()}
    counts["total"] = sum(counts.values())
    return counts


def lifecycle_payload(agreement, user=None):
    contract = agreement.contract
    signed_version = agreement.signed_version
    overlays_by_item_id = {}
    if getattr(user, "is_authenticated", False):
        overlays_by_item_id = {
            str(state.lifecycle_item_id): state
            for state in LifecycleItemUserState.objects.filter(lifecycle_item__lifecycle_agreement=agreement, user=user)
        }
    grouped = _group_items(agreement, overlays_by_item_id, user)
    events = [_serialize_event(event) for event in agreement.events.all()]
    return {
        "contract": _contract_summary(contract),
        "signed_version": _signed_version_summary(signed_version),
        "lifecycle_agreement": _lifecycle_summary(agreement),
        "timeline": _lifecycle_summary(agreement),
        "parties": {
            "initiator": _party_summary(contract.initiator),
            "counterparty": {
                "name": contract.counterparty_name,
                "email": contract.counterparty_email,
            },
        },
        "items": grouped,
        "counts": _item_counts(grouped),
        "views": _grouped_views(grouped, events),
        "events": events,
    }


def performance_agreement_payload(agreement):
    grouped = _group_items(agreement)
    events = [_serialize_event(event) for event in agreement.events.all()]
    views = _grouped_views(grouped, events)
    payment_count = len([item for item in views["payments"] if item.get("item_type") == "payment"])
    work_item_count = len([item for item in views["work_services"] if item.get("item_type") in {"service", "service_work"}])
    due_date_count = len([item for item in views["due_dates"] if _is_open_timeline_status(item)])
    status_label = "Waiting for first performed obligation"
    if agreement.status == LifecycleAgreement.STATUS_ACTIVE:
        status_label = "In progress"
    elif agreement.status == LifecycleAgreement.STATUS_COMPLETED:
        status_label = "Completed"
    return {
        "id": str(agreement.id),
        "contract_id": str(agreement.contract_id),
        "lifecycle_id": str(agreement.id),
        "title": agreement.contract.title or "Untitled contract",
        "contract": _contract_summary(agreement.contract),
        "signed_version": _signed_version_summary(agreement.signed_version),
        "lifecycle_agreement": _lifecycle_summary(agreement),
        "counterparty": {
            "name": agreement.contract.counterparty_name,
            "email": agreement.contract.counterparty_email,
        },
        "status": status_label,
        "performance_ready": agreement.performance_ready,
        "payment_count": payment_count,
        "work_count": work_item_count,
        "work_item_count": work_item_count,
        "due_date_count": due_date_count,
        "activity_count": len(events),
        "items": grouped,
        "counts": _item_counts(grouped),
        "views": views,
        "events": events,
    }


class AgreementPerformanceListAPIView(APIView):
    def get(self, request):
        agreements = (
            LifecycleAgreement.objects
            .filter(performance_ready=True)
            .filter(Q(contract__initiator=request.user) | Q(contract__counterparty_email__iexact=request.user.email))
            .select_related("contract", "contract__initiator", "signed_version", "performance_ready_by")
            .prefetch_related("items", "events")
            .order_by("-performance_ready_at", "-updated_at")
        )
        return Response({"results": [performance_agreement_payload(agreement) for agreement in agreements]}, status=status.HTTP_200_OK)


class LifecycleReadyForPerformanceAPIView(APIView):
    def post(self, request, lifecycle_id):
        agreement = get_object_or_404(
            LifecycleAgreement.objects.select_related("contract", "contract__initiator", "signed_version", "source_exchange", "owner", "performance_ready_by"),
            pk=lifecycle_id,
        )
        if not is_party(request.user, agreement.contract):
            return contract_party_response()
        if agreement.signed_version.status != "signed":
            return Response({"detail": "Agreement Performance requires a signed agreement."}, status=status.HTTP_409_CONFLICT)

        owner_id = agreement.owner_id or agreement.contract.initiator_id
        if not agreement.performance_ready and request.user.id != owner_id and request.user.id != agreement.contract.initiator_id:
            return Response({"detail": "Only the lifecycle agreement owner can mark Timeline Setup ready for Agreement Performance."}, status=status.HTTP_403_FORBIDDEN)

        if not agreement.performance_ready:
            ready_at = timezone.now()
            active_item_ids = [
                str(item_id)
                for item_id in agreement.items.exclude(status__in=[LifecycleItem.STATUS_CANCELLED, LifecycleItem.STATUS_REJECTED]).values_list("id", flat=True)
            ]
            metadata = dict(agreement.metadata or {})
            metadata["performance_source"] = "timeline_setup_items"
            metadata["performance_source_activated_at"] = ready_at.isoformat()
            metadata["performance_source_activated_by"] = str(request.user.id)
            metadata["performance_source_item_ids"] = active_item_ids
            metadata["performance_source_excluded_statuses"] = [LifecycleItem.STATUS_CANCELLED, LifecycleItem.STATUS_REJECTED]
            agreement.performance_ready = True
            agreement.performance_ready_at = ready_at
            agreement.performance_ready_by = request.user
            agreement.metadata = metadata
            agreement.save(update_fields=["performance_ready", "performance_ready_at", "performance_ready_by", "metadata", "updated_at"])

        agreement = (
            LifecycleAgreement.objects
            .select_related("contract", "contract__initiator", "signed_version", "source_exchange", "owner", "performance_ready_by")
            .prefetch_related("items", "events")
            .get(pk=agreement.pk)
        )
        return Response(lifecycle_payload(agreement, request.user), status=status.HTTP_200_OK)


class LifecycleAgreementAPIView(APIView):
    def get(self, request):
        contract_id = request.query_params.get("contract")
        if not contract_id:
            return Response({"detail": "contract query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        try:
            agreement = get_or_create_lifecycle_for_signed_contract(contract, request.user)
        except LifecycleNotReadyError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        agreement = (
            agreement.__class__.objects
            .select_related("contract", "contract__initiator", "signed_version", "source_exchange", "owner")
            .prefetch_related("items", "events")
            .get(pk=agreement.pk)
        )
        return Response(lifecycle_payload(agreement, request.user), status=status.HTTP_200_OK)


class LifecycleChangeProposalAPIView(APIView):
    def _get_agreement(self, request, lifecycle_id):
        agreement = get_object_or_404(
            LifecycleAgreement.objects.select_related("contract", "contract__initiator"),
            pk=lifecycle_id,
        )
        if not is_party(request.user, agreement.contract):
            return None, contract_party_response()
        return agreement, None

    def get(self, request, lifecycle_id):
        agreement, error_response = self._get_agreement(request, lifecycle_id)
        if error_response is not None:
            return error_response
        proposals = (
            LifecycleChangeProposal.objects
            .filter(lifecycle_agreement=agreement)
            .select_related("lifecycle_agreement", "lifecycle_agreement__contract", "lifecycle_agreement__contract__initiator", "contract", "proposed_by", "affected_item", "decided_by")
            .order_by("-created_at", "-updated_at")
        )
        return Response({
            "results": [_change_proposal_summary(proposal, request.user) for proposal in proposals],
            "party_options": _proposal_party_options(agreement),
        }, status=status.HTTP_200_OK)

    def post(self, request, lifecycle_id):
        agreement, error_response = self._get_agreement(request, lifecycle_id)
        if error_response is not None:
            return error_response
        try:
            proposal = create_lifecycle_change_proposal(agreement, request.user, request.data)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        proposal = (
            LifecycleChangeProposal.objects
            .select_related("lifecycle_agreement", "lifecycle_agreement__contract", "lifecycle_agreement__contract__initiator", "contract", "proposed_by", "affected_item", "decided_by")
            .get(pk=proposal.pk)
        )
        return Response(_change_proposal_summary(proposal, request.user), status=status.HTTP_201_CREATED)


class LifecycleChangeProposalDetailAPIView(APIView):
    def get(self, request, proposal_id):
        proposal = get_object_or_404(
            LifecycleChangeProposal.objects.select_related(
                "lifecycle_agreement",
                "lifecycle_agreement__contract",
                "lifecycle_agreement__contract__initiator",
                "contract",
                "proposed_by",
                "affected_item",
                "decided_by",
            ),
            pk=proposal_id,
        )
        if not is_party(request.user, proposal.contract):
            return contract_party_response()
        return Response(_change_proposal_summary(proposal, request.user), status=status.HTTP_200_OK)


class LifecycleChangeProposalMessageAPIView(APIView):
    def _get_proposal(self, request, proposal_id):
        proposal = get_object_or_404(
            LifecycleChangeProposal.objects.select_related(
                "lifecycle_agreement",
                "lifecycle_agreement__contract",
                "lifecycle_agreement__contract__initiator",
                "contract",
                "proposed_by",
            ),
            pk=proposal_id,
        )
        if not is_party(request.user, proposal.contract):
            return None, contract_party_response()
        return proposal, None

    def get(self, request, proposal_id):
        proposal, error_response = self._get_proposal(request, proposal_id)
        if error_response is not None:
            return error_response
        messages = (
            LifecycleChangeProposalMessage.objects
            .filter(proposal=proposal)
            .select_related("sender")
            .order_by("created_at", "id")
        )
        return Response({"results": [_change_proposal_message_summary(message, request.user) for message in messages]}, status=status.HTTP_200_OK)

    def post(self, request, proposal_id):
        proposal, error_response = self._get_proposal(request, proposal_id)
        if error_response is not None:
            return error_response
        try:
            message = create_lifecycle_change_proposal_message(proposal, request.user, request.data.get("body"))
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_change_proposal_message_summary(message, request.user), status=status.HTTP_201_CREATED)


class LifecycleChangeProposalDecisionAPIView(APIView):
    def post(self, request, proposal_id):
        proposal = get_object_or_404(
            LifecycleChangeProposal.objects.select_related(
                "lifecycle_agreement",
                "lifecycle_agreement__contract",
                "lifecycle_agreement__contract__initiator",
                "contract",
                "proposed_by",
                "decided_by",
                "affected_item",
            ),
            pk=proposal_id,
        )
        if not is_party(request.user, proposal.contract):
            return contract_party_response()
        try:
            proposal = decide_lifecycle_change_proposal(
                proposal,
                request.user,
                request.data.get("decision"),
                request.data.get("note") or "",
                final_terms={
                    key: request.data[key]
                    for key in ("final_due_date", "final_amount", "final_responsible_party")
                    if key in request.data
                },
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        proposal = (
            LifecycleChangeProposal.objects
            .select_related("lifecycle_agreement", "lifecycle_agreement__contract", "lifecycle_agreement__contract__initiator", "contract", "proposed_by", "affected_item", "decided_by")
            .get(pk=proposal.pk)
        )
        return Response(_change_proposal_summary(proposal, request.user), status=status.HTTP_200_OK)



class LifecycleItemCreateAPIView(APIView):
    def post(self, request, lifecycle_id):
        from backend.contracts.models import LifecycleAgreement

        agreement = get_object_or_404(LifecycleAgreement, pk=lifecycle_id)
        if not is_party(request.user, agreement.contract):
            return contract_party_response()

        item_type = request.data.get("item_type")
        valid_types = {choice[0] for choice in LifecycleItem.ITEM_TYPE_CHOICES}
        if item_type not in valid_types:
            return Response({"detail": "Invalid lifecycle item type."}, status=status.HTTP_400_BAD_REQUEST)

        title = (request.data.get("title") or "").strip()
        if not title:
            return Response({"detail": "title is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = create_timeline_item(agreement, request.user, request.data)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_serialize_lifecycle_item(item, user=request.user), status=status.HTTP_201_CREATED)


class LifecycleItemDetailAPIView(APIView):
    def patch(self, request, item_id):
        item = get_object_or_404(LifecycleItem.objects.select_related("lifecycle_agreement", "lifecycle_agreement__contract"), pk=item_id)
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return contract_party_response()

        try:
            item = update_timeline_item(item, request.user, request.data)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        overlay = LifecycleItemUserState.objects.filter(lifecycle_item=item, user=request.user).first()
        return Response(_serialize_lifecycle_item(item, overlay, request.user), status=status.HTTP_200_OK)


class LifecycleItemAttachmentAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def _get_item(self, request, item_id):
        item = get_object_or_404(
            LifecycleItem.objects.select_related(
                "lifecycle_agreement",
                "lifecycle_agreement__contract",
                "lifecycle_agreement__contract__initiator",
            ),
            pk=item_id,
        )
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return None, contract_party_response()
        return item, None

    def get(self, request, item_id):
        item, error_response = self._get_item(request, item_id)
        if error_response is not None:
            return error_response
        attachments = item.attachments.select_related("uploaded_by").order_by("-created_at")
        return Response({"results": [_attachment_summary(attachment) for attachment in attachments]}, status=status.HTTP_200_OK)

    def post(self, request, item_id):
        item, error_response = self._get_item(request, item_id)
        if error_response is not None:
            return error_response
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "file is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            attachment = upload_lifecycle_item_attachment(item, request.user, uploaded_file, request.data.get("note") or "")
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_attachment_summary(attachment), status=status.HTTP_201_CREATED)


class LifecycleItemMessageAPIView(APIView):
    def _get_item(self, request, item_id):
        item = get_object_or_404(
            LifecycleItem.objects.select_related(
                "lifecycle_agreement",
                "lifecycle_agreement__contract",
                "lifecycle_agreement__contract__initiator",
            ),
            pk=item_id,
        )
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return None, contract_party_response()
        return item, None

    def get(self, request, item_id):
        item, error_response = self._get_item(request, item_id)
        if error_response is not None:
            return error_response
        messages = item.messages.select_related("sender").order_by("created_at", "id")
        return Response({"results": [_message_summary(message, request.user) for message in messages]}, status=status.HTTP_200_OK)

    def post(self, request, item_id):
        item, error_response = self._get_item(request, item_id)
        if error_response is not None:
            return error_response
        try:
            message = create_lifecycle_item_message(item, request.user, request.data.get("body"))
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_message_summary(message, request.user), status=status.HTTP_201_CREATED)


class LifecycleItemResponseAPIView(APIView):
    def _get_item(self, request, item_id):
        item = get_object_or_404(
            LifecycleItem.objects.select_related(
                "lifecycle_agreement",
                "lifecycle_agreement__contract",
                "lifecycle_agreement__contract__initiator",
            ),
            pk=item_id,
        )
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return None, contract_party_response()
        return item, None

    def get(self, request, item_id):
        item, error_response = self._get_item(request, item_id)
        if error_response is not None:
            return error_response
        responses = item.counterparty_responses.select_related("responder").order_by("-updated_at", "-created_at")
        return Response({"results": [_response_summary(response) for response in responses]}, status=status.HTTP_200_OK)

    def post(self, request, item_id):
        item, error_response = self._get_item(request, item_id)
        if error_response is not None:
            return error_response
        try:
            item_response = submit_lifecycle_item_response(
                item,
                request.user,
                request.data.get("response"),
                request.data.get("note") or "",
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_response_summary(item_response), status=status.HTTP_200_OK)


class LifecycleItemActionAPIView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, item_id):
        item = get_object_or_404(LifecycleItem.objects.select_related("lifecycle_agreement", "lifecycle_agreement__contract"), pk=item_id)
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return contract_party_response()

        action = request.data.get("action")
        try:
            item = perform_timeline_item_action(item, request.user, action, request.data)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize_lifecycle_item(item, user=request.user), status=status.HTTP_200_OK)
