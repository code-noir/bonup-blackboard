#backend/api/contracts/value_adjustment_views.py

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


class ObligationValueAdjustmentListCreateAPIView(APIView):
    """
    GET  /api/contracts/obligations/<obligation_type>/<obligation_id>/value-adjustments/
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/value-adjustments/

    V1 write support is manual additional_charge only.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ValueAdjustmentService()

    def get(self, request, obligation_type, obligation_id):
        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)
            adjustments = obligation.value_adjustments.all().order_by("created_at")
        elif obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            adjustments = obligation.value_adjustments.all().order_by("created_at")
        else:
            return Response(
                {"detail": "Invalid obligation type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = [
            {
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
            for adjustment in adjustments
        ]

        serializer = ValueAdjustmentSerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        serializer = ValueAdjustmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        execution_event = None
        execution_event_id = serializer.validated_data.get("execution_event_id")
        if execution_event_id:
            execution_event = ObligationExecutionEvent.objects.get(id=execution_event_id)

        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)
            adjustment = self.service.store_additional_charge(
                contract=obligation.contract,
                payment_obligation=obligation,
                execution_event=execution_event,
                amount=serializer.validated_data["amount"],
                currency=serializer.validated_data["currency"],
                summary=serializer.validated_data["summary"],
            )
        elif obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            adjustment = self.service.store_additional_charge(
                contract=obligation.contract,
                service_obligation=obligation,
                execution_event=execution_event,
                amount=serializer.validated_data["amount"],
                currency=serializer.validated_data["currency"],
                summary=serializer.validated_data["summary"],
            )
        else:
            return Response(
                {"detail": "Invalid obligation type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = ValueAdjustmentSerializer({
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
        })
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)



