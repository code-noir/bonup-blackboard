# backend/api/contracts/resolve_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import ContractObligation, ContractServiceObligation
from backend.api.contracts.services.payment_resolution_service import (
    PaymentResolutionService,
)
from backend.activity.log import log_activity
from .permissions import contract_party_response, is_party


class ObligationResolveAPIView(APIView):
    """
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/resolve/
    """

    def post(self, request, obligation_type, obligation_id):
        if obligation_type == "service":
            obligation = get_object_or_404(ContractServiceObligation, id=obligation_id)
            if not is_party(request.user, obligation.contract):
                return contract_party_response()

            if obligation.state == "resolved":
                payload = {
                    "id": str(obligation.id),
                    "type": "service",
                    "contract_id": str(obligation.contract_id),
                    "state": obligation.state,
                    "due_date": obligation.due_date,
                    "description": obligation.description,
                    "obligor_id": obligation.obligor_id,
                    "obligee_id": obligation.obligee_id,
                    "completed_at": obligation.completed_at,
                }
                return Response(payload, status=status.HTTP_200_OK)

            obligation.mark_completed()
            log_activity(
                contract=obligation.contract,
                user=request.user,
                activity_type="obligation_resolved",
                description=f"Service obligation resolved: {obligation.description}",
                metadata={"obligation_id": str(obligation.id)},
            )

            payload = {
                "id": str(obligation.id),
                "type": "service",
                "contract_id": str(obligation.contract_id),
                "state": obligation.state,
                "due_date": obligation.due_date,
                "description": obligation.description,
                "obligor_id": obligation.obligor_id,
                "obligee_id": obligation.obligee_id,
                "completed_at": obligation.completed_at,
            }
            return Response(payload, status=status.HTTP_200_OK)

        if obligation_type == "payment":
            return Response(
                {"detail": "Payment obligation resolve is not supported yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Invalid obligation type."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ContractPaymentResolveAPIView(APIView):
    """
    POST /api/contracts/obligations/payment/<obligation_id>/resolve/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = PaymentResolutionService()

    def post(self, request, obligation_id):
        # Check party membership before the service mutates anything.
        obligation = get_object_or_404(ContractObligation, id=obligation_id)
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        try:
            obligation = self.service.resolve(obligation_id=obligation_id)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        log_activity(
            contract=obligation.contract,
            user=request.user,
            activity_type="payment_obligation_resolved",
            description=f"Payment obligation #{obligation.installment_number} resolved.",
            metadata={
                "obligation_id": str(obligation.id),
                "amount_due": str(obligation.amount_due),
                "amount_paid": str(obligation.amount_paid),
            },
        )

        payload = {
            "id": str(obligation.id),
            "type": "payment",
            "contract_id": str(obligation.contract_id),
            "state": obligation.state,
            "obligor_id": obligation.obligor_id,
            "obligee_id": obligation.obligee_id,
            "amount_due": str(obligation.amount_due),
            "amount_paid": str(obligation.amount_paid),
            "installment_number": obligation.installment_number,
            "due_date": obligation.due_date,
        }
        return Response(payload, status=status.HTTP_200_OK)
