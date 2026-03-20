#backend/api/contracts/approval_views.py
from django.contrib.auth import get_user_model

from backend.api.contracts.serializers import (
    ApprovalRequestCreateSerializer,
    ApprovalRequestSerializer,
    ApprovalDecisionSerializer,
)
from backend.api.contracts.services.approval_service import ApprovalService
from backend.contracts.models import (
    ObligationExecutionEvent,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

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

    def get(self, request, obligation_type, obligation_id):
        if obligation_type == "payment":
            approvals = self.repo.list_for_payment_obligation(obligation_id)
        elif obligation_type == "service":
            approvals = self.repo.list_for_service_obligation(obligation_id)
        else:
            raise Exception("Invalid obligation type")

        payload = [self._serialize_approval(a) for a in approvals]
        serializer = ApprovalRequestSerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        serializer = ApprovalRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        execution_event = ObligationExecutionEvent.objects.get(
            id=serializer.validated_data["execution_event_id"]
        )

        requested_by = None
        requested_from = None

        requested_by_id = serializer.validated_data.get("requested_by_id")
        requested_from_id = serializer.validated_data.get("requested_from_id")

        if requested_by_id:
            requested_by = User.objects.get(id=requested_by_id)

        if requested_from_id:
            requested_from = User.objects.get(id=requested_from_id)

        approval = self.service.request_execution_item_approval(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
            execution_event=execution_event,
            requested_by=requested_by,
            requested_from=requested_from,
            summary=serializer.validated_data["summary"],
            metadata=serializer.validated_data.get("metadata"),
        )

        response_serializer = ApprovalRequestSerializer(self._serialize_approval(approval))
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

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
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ApprovalService()

    def post(self, request, approval_id):
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approval = self.service.approve(approval_id=approval_id)

        response_serializer = ApprovalRequestSerializer({
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
        })
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ApprovalRequestRejectAPIView(APIView):
    """
    POST /api/contracts/approval-requests/<approval_id>/reject/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ApprovalService()

    def post(self, request, approval_id):
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approval = self.service.reject(approval_id=approval_id)

        response_serializer = ApprovalRequestSerializer({
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
        })
        return Response(response_serializer.data, status=status.HTTP_200_OK)




















