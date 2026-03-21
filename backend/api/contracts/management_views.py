#backend/api/contracts/management_views.py


from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.services.contract_management_service import (
    ContractManagementService,
)


class ContractManagementSummaryAPIView(APIView):
    """
    GET /api/contracts/<contract_id>/management-summary/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ContractManagementService()

    def get(self, request, contract_id):
        payload = self.service.build_summary(contract_id=contract_id)
        return Response(payload, status=status.HTTP_200_OK)