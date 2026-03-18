#backend/api/contracts/viewsets/contract_viewset.py

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from backend.contracts.models import Contract
from backend.api.contracts.serializers import ContractSerializer


class ContractViewSet(viewsets.ModelViewSet):

    queryset = Contract.objects.all().order_by("-created_at")
    serializer_class = ContractSerializer

   

    @action(detail=True, methods=["post"])
    def payment(self, request, pk=None):
        return Response({"message": "apply payment"})

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        return Response({"message": "contract timeline"})

    @action(detail=True, methods=["get"])
    def state(self, request, pk=None):
        return Response({"message": "contract state"})

