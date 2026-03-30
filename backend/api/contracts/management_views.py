# backend/api/contracts/management_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import Contract
from backend.api.contracts.services.contract_management_service import (
    ContractManagementService,
)
from .permissions import contract_party_response, is_party


class ContractManagementSummaryAPIView(APIView):
    """
    GET /api/contracts/<contract_id>/management-summary/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ContractManagementService()

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        payload = self.service.build_summary(contract_id=contract_id)
        return Response(payload, status=status.HTTP_200_OK)
