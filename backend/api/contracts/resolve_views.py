#backend/api/contracts/resolve_views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import ContractServiceObligation


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
