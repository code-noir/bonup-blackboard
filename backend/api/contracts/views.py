# backend/api/contracts/views.py

from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from backend.engine.contracts.services.contract_service import ContractService
from backend.infrastructure.repositories.contract_repository import ContractRepository
from backend.infrastructure.repositories.contract_version_repository import ContractVersionRepository


class CreateContractAPIView(APIView):
    """
    POST /api/contracts/

    Creates a new contract and its initial version.
    """

    def post(self, request):
        counterparty_email = request.data.get("counterparty_email")
        structure_type = request.data.get("structure_type", "ONE_TIME")
        content = request.data.get("content", {})

        if not counterparty_email:
            return Response(
                {"error": "counterparty_email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get a real user (for testing without authentication)
        User = get_user_model()
        user = User.objects.first()

        if not user:
            return Response(
                {"error": "No users exist in the system."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Setup repos + service
        contract_repo = ContractRepository()
        version_repo = ContractVersionRepository()
        service = ContractService(
            contract_repo=contract_repo,
            version_repo=version_repo,
        )

        # Create contract
        contract = contract_repo.create(
            initiator=user,
            counterparty_email=counterparty_email,
            structure_type=structure_type,
        )

        # Create initial version
        version = service.create_initial_version(
            contract_id=contract.id,
            content=content,
            user=user,
        )

        return Response(
            {
                "contract_id": str(contract.id),
                "version_id": str(version.id),
                "status": "CREATED",
            },
            status=status.HTTP_201_CREATED,
        )

