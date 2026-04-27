# backend/api/contracts/version_views.py

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import Contract, ContractVersion
from backend.contract_pro.models import ContractProOversightEvent
from backend.contract_pro.services import ContractProEditingService, ContractProOversightService
from backend.activity.log import log_activity

from .permissions import contract_party_response, is_party
from .serializers import ContractVersionSerializer

# Statuses that indicate a version is still open (can be signed or rejected).
_OPEN_STATUSES = {"draft", "sent", "negotiating"}

# Statuses that mean the version is already decided (terminal).
_TERMINAL_STATUSES = {"signed", "rejected", "superseded", "archived"}


class ContractVersionCreateAPIView(APIView):
    """
    POST /api/contracts/<contract_id>/versions/

    Initiator only. Creates the next version in the negotiation sequence.

    Rules:
    - Caller must be the initiator (not the counterparty).
    - No signed version may exist (contract is locked after signing).
    - Version count must be below max_versions (default 3).
    - The previous latest version is marked superseded.
    - A warning is included when creating version max_versions - 1
      (the second-to-last allowed), so both parties know one attempt remains.
    """

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.initiator_id != request.user.pk:
            return Response(
                {"error": "Only the contract initiator may create new versions."},
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

        existing_count = contract.versions.count()
        if existing_count >= contract.max_versions:
            return Response(
                {
                    "error": (
                        f"Maximum version limit reached ({contract.max_versions}). "
                        "No further versions can be created on this contract."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        content_snapshot = request.data.get("content_snapshot", "")
        if not content_snapshot:
            return Response(
                {"error": "content_snapshot is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Supersede the current latest version (if one exists).
            previous = (
                contract.versions
                .filter(superseded=False)
                .exclude(status__in=list(_TERMINAL_STATUSES))
                .order_by("-version_number")
                .first()
            )

            if previous:
                previous.superseded = True
                previous.status = "superseded"
                previous.save(update_fields=["superseded", "status"])

            new_version_number = existing_count + 1

            new_version = ContractVersion.objects.create(
                contract=contract,
                version_number=new_version_number,
                created_by=request.user,
                previous_version=previous,
                content_snapshot=content_snapshot,
                status="draft",
            )
            log_activity(
                contract=contract,
                user=request.user,
                activity_type="version_created",
                description=f"Version {new_version_number} created.",
                metadata={"version_id": str(new_version.id), "version_number": new_version_number},
            )

        response_data = ContractVersionSerializer(new_version).data

        # Warn when this version is the second-to-last allowed (e.g., v2 of 3).
        # After a rejection, only one more version can be created.
        warning = None
        if new_version_number == contract.max_versions - 1:
            warning = (
                f"Warning: this is version {new_version_number} of {contract.max_versions} "
                f"maximum. If rejected, only one final version can be created."
            )
        elif new_version_number == contract.max_versions:
            warning = (
                f"Warning: this is the final version allowed ({contract.max_versions} of "
                f"{contract.max_versions}). The contract cannot proceed if this is rejected."
            )

        payload = {"version": response_data}
        if warning:
            payload["warning"] = warning

        return Response(payload, status=status.HTTP_201_CREATED)


class ContractVersionSignAPIView(APIView):
    """
    POST /api/contracts/<contract_id>/versions/<version_id>/sign/

    Counterparty only. Signs the specified version, locking the contract.

    Rules:
    - Caller must be the counterparty (not the initiator).
    - Version must belong to the specified contract.
    - Version must be in an open status (draft / sent / negotiating).
    """

    def post(self, request, contract_id, version_id):
        contract = get_object_or_404(Contract, pk=contract_id)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.counterparty_email != request.user.email:
            return Response(
                {"error": "Only the counterparty may sign a contract version."},
                status=status.HTTP_403_FORBIDDEN,
            )

        version = get_object_or_404(ContractVersion, pk=version_id, contract=contract)

        if version.status in _TERMINAL_STATUSES:
            return Response(
                {"error": f"This version is already in a terminal state: '{version.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        version.status = "signed"
        version.save(update_fields=["status"])

        log_activity(
            contract=contract,
            user=request.user,
            activity_type="version_signed",
            description=f"Version {version.version_number} signed by {request.user}. Contract is now locked.",
            metadata={"version_id": str(version.id), "version_number": version.version_number},
        )

        return Response(
            {
                "message": "Contract version signed. The contract is now locked.",
                "version": ContractVersionSerializer(version).data,
            },
            status=status.HTTP_200_OK,
        )


class ContractVersionRejectAPIView(APIView):
    """
    POST /api/contracts/<contract_id>/versions/<version_id>/reject/

    Counterparty only. Rejects the specified version.

    Rules:
    - Caller must be the counterparty (not the initiator).
    - Version must belong to the specified contract.
    - Version must be in an open status.
    - If this was the last allowed version (version_number == max_versions),
      a warning is included: no further versions can be created.
    - If this was version max_versions - 1, a warning is included:
      the initiator has one final attempt.
    """

    def post(self, request, contract_id, version_id):
        contract = get_object_or_404(Contract, pk=contract_id)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.counterparty_email != request.user.email:
            return Response(
                {"error": "Only the counterparty may reject a contract version."},
                status=status.HTTP_403_FORBIDDEN,
            )

        version = get_object_or_404(ContractVersion, pk=version_id, contract=contract)

        if version.status in _TERMINAL_STATUSES:
            return Response(
                {"error": f"This version is already in a terminal state: '{version.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        version.status = "rejected"
        version.save(update_fields=["status"])

        log_activity(
            contract=contract,
            user=request.user,
            activity_type="version_rejected",
            description=f"Version {version.version_number} rejected by {request.user}.",
            metadata={"version_id": str(version.id), "version_number": version.version_number},
        )

        warning = None
        if version.version_number >= contract.max_versions:
            warning = (
                f"This was version {version.version_number} of {contract.max_versions} maximum. "
                "No further versions can be created — the contract cannot proceed."
            )
        elif version.version_number == contract.max_versions - 1:
            warning = (
                f"This was version {version.version_number} of {contract.max_versions} maximum. "
                "The initiator has one final attempt to submit an acceptable version."
            )

        payload = {
            "message": "Contract version rejected.",
            "version": ContractVersionSerializer(version).data,
        }
        if warning:
            payload["warning"] = warning

        return Response(payload, status=status.HTTP_200_OK)
