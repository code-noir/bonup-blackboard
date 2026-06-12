# backend/api/contracts/viewsets/contract_viewset.py

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.billing.gates import can_create_contract, consume_trial_contract, increment_contracts_used
from backend.contracts.models import Contract, ContractVersion
from backend.contract_pro.models import ContractProOversightEvent
from backend.contract_pro.services import ContractProEditingService, ContractProOversightService

from backend.api.contracts.permissions import contract_party_response, is_party
from backend.api.contracts.serializers import ContractSerializer, ContractVersionSerializer
from backend.api.contracts.services.visibility_service import can_user_see_contract_on_dashboard
from backend.activity.log import log_activity


class ContractViewSet(ViewSet):

    def list(self, request):
        """
        Return only contracts where the authenticated user is a party
        (initiator or counterparty).
        """
        candidate_contracts = Contract.objects.filter(
            Q(initiator=request.user)
            | Q(counterparty_email=request.user.email)
        ).prefetch_related("agreement_exchanges").order_by("-created_at")
        contracts = [
            contract
            for contract in candidate_contracts
            if can_user_see_contract_on_dashboard(contract, request.user)
        ]
        serializer = ContractSerializer(contracts, many=True)
        data = list(serializer.data)
        latest_versions = {}
        for version in (
            ContractVersion.objects
            .filter(contract__in=contracts, superseded=False)
            .order_by("contract_id", "-version_number")
        ):
            latest_versions.setdefault(str(version.contract_id), version)
        for item in data:
            latest = latest_versions.get(str(item["id"]))
            item["latest_version"] = ContractVersionSerializer(latest).data if latest else None
        return Response(data)

    def create(self, request):
        """
        Create a contract. The initiator is always the authenticated user —
        callers cannot set or override this field.
        """
        allowed, message = can_create_contract(request.user)
        if not allowed:
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data.pop("initiator", None)
        serializer = ContractSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            contract = serializer.save(initiator=request.user)
            increment_contracts_used(request.user)
            consume_trial_contract(request.user)
            log_activity(
                contract=contract,
                user=request.user,
                activity_type="contract_created",
                description=f"Contract created by {request.user}.",
                metadata={"structure_type": contract.structure_type},
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        """
        Return the contract. Requires the caller to be a party.
        """
        contract = get_object_or_404(Contract, pk=pk)
        if not is_party(request.user, contract):
            return contract_party_response()
        data = ContractSerializer(contract).data
        latest_version = (
            contract.versions
            .filter(superseded=False)
            .order_by("-version_number")
            .first()
        )
        data["latest_version"] = (
            ContractVersionSerializer(latest_version).data
            if latest_version else None
        )
        return Response(data)

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

        if not ContractProEditingService.owner_editing_allowed(contract, request.user):
            if contract.entity_id is not None:
                ContractProOversightService.record(
                    event_type=ContractProOversightEvent.EVENT_OWNER_EDIT_BLOCKED,
                    business=contract.entity,
                    contract=contract,
                    actor=request.user,
                )
            return Response(
                {
                    "error": (
                        "Direct editing is not allowed while an active "
                        "Contract Pro delegation controls this contract."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if contract.versions.filter(status="signed").exists():
            return Response(
                {"error": "This contract is locked — it has a signed version."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data.pop("initiator", None)

        serializer = ContractSerializer(contract, data=data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        """PATCH — delegates to update (which already applies partial serialization)."""
        return self.update(request, pk=pk)

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
