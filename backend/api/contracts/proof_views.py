#backend/api/contracts/proof_view.py


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from backend.api.contracts.services.proof_of_work_service import ProofOfWorkService


class ObligationProofOfWorkAPIView(APIView):
    """
    GET /api/contracts/obligations/<obligation_type>/<obligation_id>/proof/
    """

    def get(self, request, obligation_type, obligation_id):
        try:
            proof = ProofOfWorkService().build_for_obligation(
                obligation_type=obligation_type,
                obligation_id=obligation_id,
            )
            return Response(proof, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


