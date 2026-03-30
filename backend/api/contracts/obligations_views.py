# backend/api/contracts/obligations_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import Contract
from backend.contracts.mappers.obligation_response_mapper import (
    ObligationResponseMapper,
)
from backend.infrastructure.repositories.contract_obligation_repository import (
    ContractObligationRepository,
)
from backend.api.contracts.services.contract_lifecycle_service import (
    ContractLifecycleService,
)
from .permissions import contract_party_response, is_party


class ContractObligationsAPIView(APIView):
    """
    GET  /api/contracts/{contract_id}/obligations/
    POST /api/contracts/{contract_id}/obligations/
    """

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        obligation_repo = ContractObligationRepository()
        obligations = obligation_repo.filter_by_contract(contract_id)

        data = [ObligationResponseMapper.to_dict(o) for o in obligations]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        obligor_id = request.data.get("obligor_id")
        obligee_id = request.data.get("obligee_id")
        due_date = request.data.get("due_date")
        obligation_type = request.data.get("type")

        if not obligor_id or not obligee_id or not due_date:
            return Response(
                {"error": "Missing required fields"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if obligation_type not in ["payment", "service"]:
            return Response(
                {"error": "Invalid obligation type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = ContractLifecycleService()
        try:
            service.create_obligation(contract_id=contract.id, input_data=request.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"message": f"{obligation_type} obligation created"},
            status=status.HTTP_201_CREATED,
        )
