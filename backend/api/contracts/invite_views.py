from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.activity.log import log_activity
from backend.ai.models import WorkflowState
from backend.contracts.models import Contract

from .permissions import contract_party_response, is_party
from backend.api.ai.workflow_utils import (
    create_share_link_and_send_email,
    ensure_workflow_for_contract,
    prime_workflow_for_invite,
    serialize_share_link_result,
)

_ALLOWED_CONTRACT_STATES = {"prepared", "ready", "ready_for_negotiation", "sent", "negotiating"}


def _normalize(value):
    return str(value or "").strip().lower()


class ContractInviteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)

        if not is_party(request.user, contract):
            return contract_party_response()
        if contract.initiator_id != request.user.pk:
            return Response({"error": "Only the contract initiator may send an invite."}, status=status.HTTP_403_FORBIDDEN)

        contract_state = _normalize(contract.state)
        if contract_state not in _ALLOWED_CONTRACT_STATES:
            return Response(
                {"error": "Prepare the contract before sending an invite."},
                status=status.HTTP_409_CONFLICT,
            )

        counterparty_email = (request.data.get("counterparty_email") or contract.counterparty_email or "").strip()
        if not counterparty_email:
            return Response({"error": "counterparty_email is required."}, status=status.HTTP_400_BAD_REQUEST)

        latest_version = contract.versions.order_by("-version_number").first()
        if latest_version is None:
            return Response({"error": "A prepared contract version is required before inviting a counterparty."}, status=status.HTTP_409_CONFLICT)

        try:
            with transaction.atomic():
                workflow, _created = ensure_workflow_for_contract(
                    contract,
                    request.user,
                    source_label=contract.title or "Prepared contract",
                )
                workflow.created_version = latest_version
                workflow.counterparty_email = counterparty_email
                workflow.save(update_fields=["created_version", "counterparty_email", "updated_at"])

                share_link, payload = create_share_link_and_send_email(
                    workflow=workflow,
                    counterparty_email=counterparty_email,
                    created_by=request.user,
                )

                prime_workflow_for_invite(workflow, counterparty_email)
                workflow.save(update_fields=["counterparty_email", "sent_to_counterparty_email", "current_state", "completed_states", "pending_states", "state_timestamps", "updated_at"])

                contract.counterparty_email = counterparty_email
                contract.state = "sent"
                contract.status = "sent"
                contract.save(update_fields=["counterparty_email", "state", "status"])

                log_activity(
                    contract=contract,
                    user=request.user,
                    activity_type="contract_updated",
                    description="Contract invite sent.",
                    metadata={
                        "workflow_id": str(workflow.id),
                        "counterparty_email": counterparty_email,
                        "email_sent": payload.get("email_sent", False),
                        "invite_token": str(share_link.token),
                    },
                )
        except Exception:
            return Response({"error": "Invite email could not be sent."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        payload = {
            **payload,
            "contract_id": str(contract.id),
            "state": contract.state,
            "status": contract.status,
        }
        return Response(payload, status=status.HTTP_201_CREATED)
