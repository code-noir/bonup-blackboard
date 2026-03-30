# backend/api/contracts/views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.contracts.models import Contract

from .permissions import contract_party_response, is_party
from .serializers import ContractSerializer


class ContractViewSet(ViewSet):

    def list(self, request):
        """
        Return only contracts where the authenticated user is a party
        (initiator or counterparty).
        """
        from django.db.models import Q
        contracts = Contract.objects.filter(
            Q(initiator=request.user)
            | Q(counterparty_email=request.user.email)
        )
        serializer = ContractSerializer(contracts, many=True)
        return Response(serializer.data)

    def create(self, request):
        """
        Create a contract. The initiator is always the authenticated user —
        callers cannot set or override this field.
        """
        serializer = ContractSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(initiator=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        """
        Return the contract. Requires the caller to be a party.
        """
        contract = get_object_or_404(Contract, pk=pk)
        if not is_party(request.user, contract):
            return contract_party_response()
        serializer = ContractSerializer(contract)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """
        Partial update (PATCH) on a contract.

        Rules enforced:
          - Caller must be a party.
          - Only the initiator may write changes.
          - Contract is locked once any version is signed.
          - initiator field cannot be reassigned.
        """
        contract = get_object_or_404(Contract, pk=pk)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.initiator_id != request.user.pk:
            return Response(
                {"error": "Only the contract initiator may modify the contract."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if contract.versions.filter(status="signed").exists():
            return Response(
                {"error": "This contract is locked — it has a signed version."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Prevent callers from reassigning the initiator field.
        data = request.data.copy()
        data.pop("initiator", None)

        serializer = ContractSerializer(contract, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """
        Delete a contract. Only the initiator may do this.
        """
        contract = get_object_or_404(Contract, pk=pk)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.initiator_id != request.user.pk:
            return Response(
                {"error": "Only the contract initiator may delete the contract."},
                status=status.HTTP_403_FORBIDDEN,
            )

        contract.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
