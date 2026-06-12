import json

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.activity.log import log_activity
from backend.contract_pro.models import ContractProOversightEvent
from backend.contract_pro.services import ContractProEditingService, ContractProOversightService
from backend.contracts.models import Contract, ContractVersion

from .permissions import contract_party_response, is_party
from .serializers import ContractVersionSerializer


_ALLOWED_DRAFT_STATES = {"created", "draft", "drafting"}


def _normalize_state(value):
    return str(value or "").strip().lower()


def _parse_content_snapshot(raw_snapshot):
    if raw_snapshot in (None, ""):
        raise ValueError("content_snapshot is required.")

    if isinstance(raw_snapshot, dict):
        parsed = raw_snapshot
    else:
        try:
            parsed = json.loads(raw_snapshot)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("content_snapshot must be valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("content_snapshot must decode to a JSON object.")

    return parsed


class ContractDraftAutosaveAPIView(APIView):
    """
    PATCH /api/contracts/<contract_id>/draft/

    Persist the current editable draft snapshot without creating a new formal
    contract version on every keystroke.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)

        if not is_party(request.user, contract):
            return contract_party_response()

        if contract.initiator_id != request.user.pk:
            return Response(
                {"error": "Only the contract initiator may edit this draft."},
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

        contract_state = _normalize_state(contract.state)
        contract_status = _normalize_state(contract.status)
        if contract_state not in _ALLOWED_DRAFT_STATES or contract_status != "draft":
            return Response(
                {
                    "error": (
                        "Draft autosave is only available while the contract is in "
                        "created, draft, or drafting state."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        if contract.versions.filter(status="signed").exists():
            return Response(
                {"error": "This contract is locked — it has a signed version."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            snapshot = _parse_content_snapshot(request.data.get("content_snapshot"))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serialized_snapshot = json.dumps(snapshot)
        latest = contract.versions.filter(superseded=False).order_by("-version_number").first()
        created_version = False

        with transaction.atomic():
            if latest:
                if _normalize_state(latest.status) != "draft":
                    return Response(
                        {"error": "The current draft snapshot is no longer editable."},
                        status=status.HTTP_409_CONFLICT,
                    )
                ContractVersion.objects.filter(pk=latest.pk).update(content_snapshot=serialized_snapshot)
                latest.refresh_from_db()
                version = latest
            else:
                version = ContractVersion.objects.create(
                    contract=contract,
                    version_number=1,
                    created_by=request.user,
                    previous_version=None,
                    content_snapshot=serialized_snapshot,
                    status="draft",
                )
                created_version = True

            contract.state = "drafting"
            contract.status = "draft"
            contract.save(update_fields=["state", "status"])

            log_activity(
                contract=contract,
                user=request.user,
                activity_type="draft_autosaved",
                description="Contract draft autosaved.",
                metadata={
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "created_version": created_version,
                },
            )

        return Response(
            {
                "contract_id": str(contract.id),
                "state": contract.state,
                "status": contract.status,
                "version": ContractVersionSerializer(version).data,
                "latest_version": ContractVersionSerializer(version).data,
                "content_snapshot": version.content_snapshot,
            },
            status=status.HTTP_200_OK,
        )
