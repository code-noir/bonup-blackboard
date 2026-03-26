#backend/api/contracts/resolve_views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import ContractServiceObligation
from backend.api.contracts.services.payment_resolution_service import (
    PaymentResolutionService,
)


class ObligationResolveAPIView(APIView):
    """
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/resolve/
    """

    def post(self, request, obligation_type, obligation_id):
        if obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)

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
        try:
            obligation = self.service.resolve(obligation_id=obligation_id)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
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