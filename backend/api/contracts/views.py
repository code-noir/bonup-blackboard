#backend/api/contracts/views.py

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from backend.contracts.models import Contract
from .serializers import ContractSerializer


class ContractsViewSet(ViewSet):

    def list(self, request):
        contracts = Contract.objects.all()
        serializer = ContractSerializer(contracts, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = ContractSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)

    def retrieve(self, request, pk=None):
        contract = Contract.objects.get(pk=pk)
        serializer = ContractSerializer(contract)
        return Response(serializer.data)

    def update(self, request, pk=None):
        contract = Contract.objects.get(pk=pk)
        serializer = ContractSerializer(contract, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)

    def destroy(self, request, pk=None):
        contract = Contract.objects.get(pk=pk)
        contract.delete()
        return Response({"message": "contract deleted"})


