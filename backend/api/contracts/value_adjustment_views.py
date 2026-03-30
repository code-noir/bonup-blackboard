# backend/api/contracts/value_adjustment_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.serializers import (
    ValueAdjustmentCreateSerializer,
    ValueAdjustmentSerializer,
)
from backend.api.contracts.services.value_adjustment_service import (
    ValueAdjustmentService,
)
from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
    ObligationExecutionEvent,
)
from .permissions import contract_party_response, is_party


class ObligationValueAdjustmentListCreateAPIView(APIView):
    """
    GET  /api/contracts/obligations/<obligation_type>/<obligation_id>/value-adjustments/
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/value-adjustments/

    V1 write support is manual additional_charge only.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ValueAdjustmentService()

    def _get_obligation(self, obligation_type, obligation_id):
        if obligation_type == "payment":
            return get_object_or_404(ContractObligation, id=obligation_id)
        if obligation_type == "service":
            return get_object_or_404(ContractServiceObligation, id=obligation_id)
        return None

    def get(self, request, obligation_type, obligation_id):
        obligation = self._get_obligation(obligation_type, obligation_id)
        if obligation is None:
            return Response(
                {"detail": "Invalid obligation type."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        adjustments = obligation.value_adjustments.all().order_by("created_at")

        payload = [
            {
                "adjustment_id": adj.id,
                "event_id": adj.execution_event_id,
                "payment_obligation_id": adj.payment_obligation_id,
                "service_obligation_id": adj.service_obligation_id,
                "adjustment_type": adj.adjustment_type,
                "mode": adj.mode,
                "amount": adj.amount,
                "currency": adj.currency,
                "summary": adj.summary,
                "created_at": adj.created_at,
            }
            for adj in adjustments
        ]

        return Response(ValueAdjustmentSerializer(payload, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        obligation = self._get_obligation(obligation_type, obligation_id)
        if obligation is None:
            return Response(
                {"detail": "Invalid obligation type."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        serializer = ValueAdjustmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        execution_event = None
        execution_event_id = serializer.validated_data.get("execution_event_id")
        if execution_event_id:
            execution_event = get_object_or_404(ObligationExecutionEvent, id=execution_event_id)

        if obligation_type == "payment":
            adjustment = self.service.store_additional_charge(
                contract=obligation.contract,
                payment_obligation=obligation,
                execution_event=execution_event,
                amount=serializer.validated_data["amount"],
                currency=serializer.validated_data["currency"],
                summary=serializer.validated_data["summary"],
            )
        else:
            adjustment = self.service.store_additional_charge(
                contract=obligation.contract,
                service_obligation=obligation,
                execution_event=execution_event,
                amount=serializer.validated_data["amount"],
                currency=serializer.validated_data["currency"],
                summary=serializer.validated_data["summary"],
            )

        response_payload = {
            "adjustment_id": adjustment.id,
            "event_id": adjustment.execution_event_id,
            "payment_obligation_id": adjustment.payment_obligation_id,
            "service_obligation_id": adjustment.service_obligation_id,
            "adjustment_type": adjustment.adjustment_type,
            "mode": adjustment.mode,
            "amount": adjustment.amount,
            "currency": adjustment.currency,
            "summary": adjustment.summary,
            "created_at": adjustment.created_at,
        }
        return Response(ValueAdjustmentSerializer(response_payload).data, status=status.HTTP_201_CREATED)
