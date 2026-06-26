from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.permissions import contract_party_response, is_party
from backend.contracts.models import (
    Contract,
    ContractObligation,
    ContractServiceObligation,
    LifecycleAgreement,
    LifecycleItem,
    LifecycleItemUserState,
)
from backend.lifecycle.services import (
    LifecycleNotReadyError,
    create_timeline_item,
    get_or_create_lifecycle_for_signed_contract,
    perform_timeline_item_action,
    update_timeline_item,
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



def _timeline_item_overlay_state(item, overlay):
    baseline = _timeline_item_baseline_values(item)
    if overlay is None:
        return baseline
    return {
        "title": overlay.title_override if overlay.title_override is not None else baseline["title"],
        "description": overlay.description_override if overlay.description_override is not None else baseline["description"],
        "due_date": _iso(overlay.due_date_override) if overlay.due_date_override else baseline["due_date"],
        "amount": _money(overlay.amount_override) if overlay.amount_override is not None else baseline["amount"],
        "responsible_party": overlay.responsible_party_override if overlay.responsible_party_override is not None else baseline["responsible_party"],
        "payment_method": overlay.payment_method_override if overlay.payment_method_override is not None else baseline["payment_method"],
        "status": overlay.status_override if overlay.status_override is not None else baseline["status"],
    }



def _serialize_lifecycle_item(item, overlay=None):
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
        "baseline_values": baseline_values,
        "has_personal_overrides": has_personal_overrides,
        "created_by": str(item.created_by_id) if getattr(item, "created_by_id", None) else None,
        "visibility": getattr(item, "visibility", "parties"),
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


def _group_items(agreement, overlays_by_item_id=None):
    grouped = _empty_groups()
    overlays_by_item_id = overlays_by_item_id or {}
    for item in agreement.items.all():
        if _is_signed_contract_document(item):
            continue
        overlay = overlays_by_item_id.get(str(item.id))
        _append_timeline_item(grouped, _GROUPS[item.item_type], _serialize_lifecycle_item(item, overlay))

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


def _without_legacy_generated_payment_sources(items, has_generated_repayment_schedule):
    if not has_generated_repayment_schedule:
        return items
    return [
        item for item in items
        if item.get("source") not in {"contract_payment_obligation", "payment_record"}
    ]


def _grouped_views(grouped, events):
    all_items = [item for values in grouped.values() for item in values]
    has_generated_repayment_schedule = any(_is_generated_repayment_schedule_item(item) for item in grouped["payments"])
    action_items = _without_legacy_generated_payment_sources(all_items, has_generated_repayment_schedule)
    due_dated_action_items = [
        item for item in action_items
        if item.get("due_date")
        and _is_open_timeline_status(item)
        and not _is_loan_delivery_work_item(item)
        and item.get("item_type") in {"payment", "service", "service_work", "responsibility", "obligation", "due_date", "deadline"}
    ]
    upcoming = sorted(due_dated_action_items, key=lambda item: item.get("due_date") or "")[:10]
    payment_items = _without_legacy_generated_payment_sources(grouped["payments"], has_generated_repayment_schedule)
    return {
        "upcoming": upcoming,
        "to_dos": [item for item in grouped["obligations"] if item.get("item_type") in {"responsibility", "obligation"}],
        "payments": [item for item in payment_items if item.get("item_type") == "payment"],
        "due_dates": sorted(due_dated_action_items, key=lambda item: item.get("due_date") or ""),
        "work_services": [item for item in grouped["services"] if item.get("item_type") in {"service", "service_work"}],
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
    grouped = _group_items(agreement, overlays_by_item_id)
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
    due_date_count = len(views["due_dates"])
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
        "status": "Waiting for first performed obligation",
        "performance_ready": agreement.performance_ready,
        "payment_count": payment_count,
        "work_count": work_item_count,
        "work_item_count": work_item_count,
        "due_date_count": due_date_count,
        "activity_count": len(events),
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

        if not agreement.performance_ready:
            agreement.performance_ready = True
            agreement.performance_ready_at = timezone.now()
            agreement.performance_ready_by = request.user
            agreement.save(update_fields=["performance_ready", "performance_ready_at", "performance_ready_by", "updated_at"])

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
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_serialize_lifecycle_item(item), status=status.HTTP_201_CREATED)


class LifecycleItemDetailAPIView(APIView):
    def patch(self, request, item_id):
        item = get_object_or_404(LifecycleItem.objects.select_related("lifecycle_agreement", "lifecycle_agreement__contract"), pk=item_id)
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return contract_party_response()

        try:
            item = update_timeline_item(item, request.user, request.data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        overlay = LifecycleItemUserState.objects.filter(lifecycle_item=item, user=request.user).first()
        return Response(_serialize_lifecycle_item(item, overlay), status=status.HTTP_200_OK)


class LifecycleItemActionAPIView(APIView):
    def post(self, request, item_id):
        item = get_object_or_404(LifecycleItem.objects.select_related("lifecycle_agreement", "lifecycle_agreement__contract"), pk=item_id)
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return contract_party_response()

        action = request.data.get("action")
        try:
            item = perform_timeline_item_action(item, request.user, action, request.data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize_lifecycle_item(item), status=status.HTTP_200_OK)
