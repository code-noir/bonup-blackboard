from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response

from backend.contracts.models import Contract
from backend.api.contracts.serializers import ContractSerializer


class ContractViewSet(viewsets.ModelViewSet):

    queryset = Contract.objects.all().order_by("-created_at")
    serializer_class = ContractSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):

        contract = self.get_object()

        return Response({
            "contract_id": contract.id,
            "state": contract.state,
            "is_active": contract.is_active
        })






