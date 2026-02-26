from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from backend.infrastructure.repositories.contract_repository import (
    DjangoContractRepository,
)

from backend.infrastructure.repositories.contract_version_repository import (
    DjangoContractVersionRepository,
)



class CreateContractAPIView(APIView):
    """
    POST /api/contracts/

    Creates a new contract using engine layer.
    """

    def post(self, request):

        name = request.data.get("name")
        content = request.data.get("content", {})

        if not name:
            return Response(
                {"error": "Contract name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract_repo = DjangoContractRepository()
        version_repo = DjangoContractVersionRepository()

        service = ContractService(
        contract_repo=contract_repo,
        version_repo=version_repo,
)

        contract = contract_repo.create(name=name)

        version = service.create_initial_version(
            contract_id=contract.id,
            content=content,
        )

        return Response(
            {
                "contract_id": contract.id,
                "version_id": version.id,
                "status": version.status,
            },
            status=status.HTTP_201_CREATED,
        )
