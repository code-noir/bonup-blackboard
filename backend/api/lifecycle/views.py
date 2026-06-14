from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.permissions import contract_party_response, is_party
from backend.contracts.models import (
    Contract,
    ContractObligation,
    ContractServiceObligation,
    LifecycleItem,
)
from backend.lifecycle.services import (
    LifecycleNotReadyError,
    get_or_create_lifecycle_for_signed_contract,
)
from backend.payments.models import Payment


_GROUPS = {
    LifecycleItem.TYPE_OBLIGATION: "obligations",
    LifecycleItem.TYPE_PAYMENT: "payments",
    LifecycleItem.TYPE_DEADLINE: "deadlines",
    LifecycleItem.TYPE_SERVICE: "services",
    LifecycleItem.TYPE_RISK: "risks",
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
        "metadata": agreement.metadata or {},
    }


def _serialize_lifecycle_item(item):
    return {
        "id": str(item.id),
        "source": "manual",
        "item_type": item.item_type,
        "title": item.title,
        "description": item.description,
        "responsible_party": item.responsible_party,
        "beneficiary_party": item.beneficiary_party,
        "due_date": _iso(item.due_date),
        "amount": _money(item.amount),
        "recurrence": item.recurrence,
        "status": item.status,
        "source_clause": item.source_clause,
        "metadata": item.metadata or {},
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
    return {"obligations": [], "payments": [], "deadlines": [], "services": [], "risks": [], "notes": []}


def _group_items(agreement):
    grouped = _empty_groups()
    for item in agreement.items.all():
        grouped[_GROUPS[item.item_type]].append(_serialize_lifecycle_item(item))

    for obligation in ContractObligation.objects.filter(contract=agreement.contract).order_by("due_date"):
        grouped["payments"].append(_serialize_payment_obligation(obligation))

    for obligation in ContractServiceObligation.objects.filter(contract=agreement.contract).order_by("due_date"):
        grouped["services"].append(_serialize_service_obligation(obligation))

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


def lifecycle_payload(agreement):
    contract = agreement.contract
    signed_version = agreement.signed_version
    return {
        "contract": _contract_summary(contract),
        "signed_version": _signed_version_summary(signed_version),
        "lifecycle_agreement": _lifecycle_summary(agreement),
        "parties": {
            "initiator": _party_summary(contract.initiator),
            "counterparty": {
                "name": contract.counterparty_name,
                "email": contract.counterparty_email,
            },
        },
        "items": _group_items(agreement),
        "events": [_serialize_event(event) for event in agreement.events.all()],
    }


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
        return Response(lifecycle_payload(agreement), status=status.HTTP_200_OK)


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

        amount = request.data.get("amount")
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=item_type,
            title=title,
            description=request.data.get("description") or "",
            responsible_party=request.data.get("responsible_party") or "",
            beneficiary_party=request.data.get("beneficiary_party") or "",
            due_date=request.data.get("due_date") or None,
            amount=Decimal(str(amount)) if amount not in (None, "") else None,
            recurrence=request.data.get("recurrence") or None,
            status=request.data.get("status") or LifecycleItem.STATUS_PENDING,
            source_clause=request.data.get("source_clause") or None,
            metadata=request.data.get("metadata") or {},
        )
        return Response(_serialize_lifecycle_item(item), status=status.HTTP_201_CREATED)


class LifecycleItemDetailAPIView(APIView):
    def patch(self, request, item_id):
        item = get_object_or_404(LifecycleItem.objects.select_related("lifecycle_agreement", "lifecycle_agreement__contract"), pk=item_id)
        if not is_party(request.user, item.lifecycle_agreement.contract):
            return contract_party_response()

        allowed = {
            "title",
            "description",
            "responsible_party",
            "beneficiary_party",
            "due_date",
            "amount",
            "recurrence",
            "status",
            "source_clause",
            "metadata",
        }
        update_fields = []
        for field in allowed:
            if field not in request.data:
                continue
            value = request.data[field]
            if field == "amount":
                value = Decimal(str(value)) if value not in (None, "") else None
            elif field == "due_date":
                value = value or None
            setattr(item, field, value)
            update_fields.append(field)

        if update_fields:
            update_fields.append("updated_at")
            item.save(update_fields=update_fields)

        return Response(_serialize_lifecycle_item(item), status=status.HTTP_200_OK)
