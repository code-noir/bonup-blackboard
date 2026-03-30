# backend/api/contracts/approval_views.py

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestCreateSerializer,
    ApprovalRequestSerializer,
)
from backend.api.contracts.services.approval_service import ApprovalService
from backend.contracts.models import (
    ContractApprovalRequest,
    ContractObligation,
    ContractServiceObligation,
    ObligationExecutionEvent,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)
from .permissions import contract_party_response, is_party

User = get_user_model()


class ObligationApprovalRequestListCreateAPIView(APIView):
    """
    GET  /api/contracts/obligations/<obligation_type>/<obligation_id>/approval-requests/
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/approval-requests/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ApprovalService()
        self.repo = ContractApprovalRepository()

    def _get_obligation(self, obligation_type, obligation_id):
        if obligation_type == "payment":
            return get_object_or_404(ContractObligation, id=obligation_id)
        if obligation_type == "service":
            return get_object_or_404(ContractServiceObligation, id=obligation_id)
        return None

    def get(self, request, obligation_type, obligation_id):
        obligation = self._get_obligation(obligation_type, obligation_id)
        if obligation is None:
            return Response(
                {"error": "Invalid obligation type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        if obligation_type == "payment":
            approvals = self.repo.list_for_payment_obligation(obligation_id)
        else:
            approvals = self.repo.list_for_service_obligation(obligation_id)

        payload = [self._serialize_approval(a) for a in approvals]
        return Response(ApprovalRequestSerializer(payload, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        obligation = self._get_obligation(obligation_type, obligation_id)
        if obligation is None:
            return Response(
                {"error": "Invalid obligation type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        serializer = ApprovalRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        execution_event = get_object_or_404(
            ObligationExecutionEvent,
            id=serializer.validated_data["execution_event_id"],
        )

        requested_by = None
        requested_from = None

        requested_by_id = serializer.validated_data.get("requested_by_id")
        requested_from_id = serializer.validated_data.get("requested_from_id")

        if requested_by_id:
            requested_by = get_object_or_404(User, id=requested_by_id)
        if requested_from_id:
            requested_from = get_object_or_404(User, id=requested_from_id)

        approval = self.service.request_execution_item_approval(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
            execution_event=execution_event,
            requested_by=requested_by,
            requested_from=requested_from,
            summary=serializer.validated_data["summary"],
            metadata=serializer.validated_data.get("metadata"),
        )

        return Response(
            ApprovalRequestSerializer(self._serialize_approval(approval)).data,
            status=status.HTTP_201_CREATED,
        )

    def _serialize_approval(self, approval):
        return {
            "id": approval.id,
            "approval_type": approval.approval_type,
            "status": approval.status,
            "summary": approval.summary,
            "metadata": approval.metadata,
            "requested_at": approval.requested_at,
            "decided_at": approval.decided_at,
            "execution_event_id": approval.execution_event_id,
            "payment_obligation_id": approval.payment_obligation_id,
            "service_obligation_id": approval.service_obligation_id,
        }


class ApprovalRequestApproveAPIView(APIView):
    """
    POST /api/contracts/approval-requests/<approval_id>/approve/

    Only the user the approval was requested from may approve it.
    Any party may approve if requested_from is unset.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ApprovalService()

    def post(self, request, approval_id):
        approval_obj = get_object_or_404(ContractApprovalRequest, id=approval_id)

        if not is_party(request.user, approval_obj.contract):
            return contract_party_response()

        if (
            approval_obj.requested_from_id is not None
            and approval_obj.requested_from_id != request.user.pk
        ):
            return Response(
                {"error": "Only the user this approval was requested from may approve it."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approval = self.service.approve(approval_id=approval_id)

        return Response(
            ApprovalRequestSerializer({
                "id": approval.id,
                "approval_type": approval.approval_type,
                "status": approval.status,
                "summary": approval.summary,
                "metadata": approval.metadata,
                "requested_at": approval.requested_at,
                "decided_at": approval.decided_at,
                "execution_event_id": approval.execution_event_id,
                "payment_obligation_id": approval.payment_obligation_id,
                "service_obligation_id": approval.service_obligation_id,
            }).data,
            status=status.HTTP_200_OK,
        )


class ApprovalRequestRejectAPIView(APIView):
    """
    POST /api/contracts/approval-requests/<approval_id>/reject/

    Only the user the approval was requested from may reject it.
    Any party may reject if requested_from is unset.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ApprovalService()

    def post(self, request, approval_id):
        approval_obj = get_object_or_404(ContractApprovalRequest, id=approval_id)

        if not is_party(request.user, approval_obj.contract):
            return contract_party_response()

        if (
            approval_obj.requested_from_id is not None
            and approval_obj.requested_from_id != request.user.pk
        ):
            return Response(
                {"error": "Only the user this approval was requested from may reject it."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approval = self.service.reject(approval_id=approval_id)

        return Response(
            ApprovalRequestSerializer({
                "id": approval.id,
                "approval_type": approval.approval_type,
                "status": approval.status,
                "summary": approval.summary,
                "metadata": approval.metadata,
                "requested_at": approval.requested_at,
                "decided_at": approval.decided_at,
                "execution_event_id": approval.execution_event_id,
                "payment_obligation_id": approval.payment_obligation_id,
                "service_obligation_id": approval.service_obligation_id,
            }).data,
            status=status.HTTP_200_OK,
        )
