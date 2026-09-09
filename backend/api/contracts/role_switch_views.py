# backend/api/contracts/role_switch_views.py

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.documents.services import delete_contracts
from backend.contracts.models import Contract, ContractRoleSwitchRequest
from backend.activity.log import log_activity

from .permissions import contract_party_response, is_party

User = get_user_model()

ROLE_SWITCH_TTL_DAYS = 7


class ContractRoleSwitchRequestAPIView(APIView):
    """
    POST /api/contracts/<contract_id>/request-role-switch/

    Counterparty only. Creates a request to swap roles with the initiator.

    Rules:
    - Caller must be the counterparty.
    - No signed version may exist (contract is locked after signing).
    - Only one pending request allowed per contract at a time.
    - Request expires after 7 days if not confirmed.
    """

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.counterparty_email != request.user.email:
            return Response(
                {"error": "Only the counterparty may request a role switch."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if contract.versions.filter(status="signed").exists():
            return Response(
                {"error": "Role switch is not allowed — this contract has a signed version."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Expire any stale pending requests before checking for duplicates.
        now = timezone.now()
        ContractRoleSwitchRequest.objects.filter(
            contract=contract,
            status="pending",
            expires_at__lt=now,
        ).update(status="expired")

        if ContractRoleSwitchRequest.objects.filter(
            contract=contract, status="pending"
        ).exists():
            return Response(
                {"error": "A pending role switch request already exists for this contract."},
                status=status.HTTP_409_CONFLICT,
            )

        switch_request = ContractRoleSwitchRequest.objects.create(
            contract=contract,
            requested_by=request.user,
            expires_at=now + timedelta(days=ROLE_SWITCH_TTL_DAYS),
        )

        log_activity(
            contract=contract,
            user=request.user,
            activity_type="role_switch_requested",
            description=f"Role switch requested by {request.user}.",
            metadata={"switch_request_id": str(switch_request.id)},
        )

        return Response(
            {
                "id": str(switch_request.id),
                "contract_id": str(contract.id),
                "requested_by": request.user.pk,
                "status": switch_request.status,
                "expires_at": switch_request.expires_at,
                "message": (
                    "Role switch requested. "
                    "The initiator must confirm via POST /confirm-role-switch/ "
                    f"within {ROLE_SWITCH_TTL_DAYS} days."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ContractRoleSwitchConfirmAPIView(APIView):
    """
    POST /api/contracts/<contract_id>/confirm-role-switch/

    Initiator only. Confirms a pending role switch request.

    On confirmation:
    - The original contract (and all its versions, obligations, payments) is deleted.
    - A new contract is created with roles swapped:
        new initiator  = original counterparty user
        new counterparty_email = original initiator's email
    - The new contract is a fresh start — no versions, no obligations, no content.
    - A new contract ID is issued.

    Rules:
    - Caller must be the current initiator.
    - A pending, non-expired role switch request must exist.
    - No signed version may exist.
    - The counterparty must have a registered user account (required to become initiator).
    """

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.initiator_id != request.user.pk:
            return Response(
                {"error": "Only the current initiator may confirm a role switch."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if contract.versions.filter(status="signed").exists():
            return Response(
                {"error": "Role switch is not allowed — this contract has a signed version."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            switch_request = ContractRoleSwitchRequest.objects.get(
                contract=contract, status="pending"
            )
        except ContractRoleSwitchRequest.DoesNotExist:
            return Response(
                {"error": "No pending role switch request found for this contract."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if switch_request.expires_at < timezone.now():
            switch_request.status = "expired"
            switch_request.save(update_fields=["status"])
            return Response(
                {"error": "The role switch request has expired."},
                status=status.HTTP_410_GONE,
            )

        # The new initiator must have a registered account.
        try:
            new_initiator = User.objects.get(email=contract.counterparty_email)
        except User.DoesNotExist:
            return Response(
                {
                    "error": (
                        "The counterparty does not have a registered account. "
                        "They must register before a role switch can be confirmed."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Capture everything needed before the original contract is deleted.
        new_counterparty_email = request.user.email
        structure_type = contract.structure_type
        max_versions = contract.max_versions

        with transaction.atomic():
            # Delete original contract — cascades to versions, obligations,
            # payments, role switch requests (including switch_request itself).
            delete_contracts([contract.pk], actor=request.user, initiator_only=True)

            new_contract = Contract.objects.create(
                initiator=new_initiator,
                counterparty_email=new_counterparty_email,
                structure_type=structure_type,
                max_versions=max_versions,
            )
            log_activity(
                contract=new_contract,
                user=request.user,
                activity_type="role_switch_confirmed",
                description=(
                    f"Roles switched. {new_initiator} is now the initiator; "
                    f"{new_counterparty_email} is the counterparty."
                ),
                metadata={
                    "new_initiator_id": new_initiator.pk,
                    "new_counterparty_email": new_counterparty_email,
                },
            )

        return Response(
            {
                "message": "Role switch confirmed. A new contract has been created.",
                "new_contract_id": str(new_contract.id),
                "new_initiator_id": new_initiator.pk,
                "new_counterparty_email": new_counterparty_email,
            },
            status=status.HTTP_201_CREATED,
        )
