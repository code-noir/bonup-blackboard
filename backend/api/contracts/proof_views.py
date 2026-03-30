# backend/api/contracts/proof_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import ContractObligation, ContractServiceObligation
from backend.api.contracts.services.proof_of_work_service import ProofOfWorkService
from backend.api.contracts.services.payment_resolution_service import (
    PaymentResolutionService,
)
from .permissions import contract_party_response, is_party


class ObligationProofOfWorkAPIView(APIView):
    """
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/proof/
    """

    def get(self, request, obligation_type, obligation_id):
        if obligation_type == "payment":
            obligation = get_object_or_404(ContractObligation, id=obligation_id)
        elif obligation_type == "service":
            obligation = get_object_or_404(ContractServiceObligation, id=obligation_id)
        else:
            return Response(
                {"error": "Invalid obligation type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        try:
            proof = ProofOfWorkService().build_for_obligation(
                obligation_type=obligation_type,
                obligation_id=obligation_id,
            )
            return Response(proof, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



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
                {"detail": "Use /api/contracts/obligations/payment/<obligation_id>/resolve/ instead."},
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
