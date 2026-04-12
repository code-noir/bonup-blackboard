# backend/api/contracts/views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.billing.gates import can_create_contract, increment_contracts_used
from backend.contracts.models import Contract
from backend.activity.log import log_activity

from .permissions import contract_party_response, is_party
from .serializers import ContractSerializer


class ContractViewSet(ViewSet):
    permission_classes = [IsAuthenticated]


    def list(self, request):
        """
        Return contracts where the authenticated user is a party, filtered
        strictly by entity so contracts never bleed across identity contexts.

        ?entity=personal  → only personal-type contracts for this user
        ?entity=<uuid>    → only contracts under that specific business entity
                            (entity must be owned by the requesting user)
        (no param)        → defaults to personal; never returns all contracts
        """
        from django.db.models import Q
        from backend.users.models import BusinessEntity

        entity_param = request.query_params.get('entity', 'personal')

        qs = Contract.objects.filter(
            Q(initiator=request.user)
            | Q(counterparty_email=request.user.email)
        )

        if entity_param == 'personal':
            qs = qs.filter(entity_type='personal')
        else:
            # Verify the requested entity is owned by this user before filtering.
            # Return empty if the entity doesn't exist or belongs to someone else.
            if not BusinessEntity.objects.filter(pk=entity_param, owner=request.user).exists():
                return Response([])
            qs = qs.filter(entity_type='business', entity_id=entity_param)

        serializer = ContractSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request):
        """
        Create a contract. The initiator is always the authenticated user —
        callers cannot set or override this field.

        Accepted entity fields (not validated by serializer — handled here):
          entity_type: 'personal' | 'business'  (default: 'personal')
          entity:      business entity UUID       (required when entity_type='business')
        """
        allowed, message = can_create_contract(request.user)
        if not allowed:
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        entity_type = request.data.get('entity_type', 'personal')
        entity_id = request.data.get('entity')

        # Strip fields we set explicitly so the serializer never sees them.
        data = {k: v for k, v in request.data.items()
                if k not in ('entity', 'initiator')}

        serializer = ContractSerializer(data=data)
        if serializer.is_valid():
            save_kwargs = {'initiator': request.user}
            if entity_type == 'business' and entity_id:
                from backend.users.models import BusinessEntity
                try:
                    biz = BusinessEntity.objects.get(pk=entity_id, owner=request.user)
                    save_kwargs['entity'] = biz
                except (BusinessEntity.DoesNotExist, Exception):
                    pass

            contract = serializer.save(**save_kwargs)
            increment_contracts_used(request.user)
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
