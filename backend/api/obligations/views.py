# backend/api/obligations/views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)
from backend.infrastructure.repositories.contract_value_adjustment_repository import (
    ContractValueAdjustmentRepository,
)
from backend.infrastructure.repositories.contract_obligation_promotion_repository import (
    ContractObligationPromotionRepository,
)


class ObligationDetailAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approval_repo = ContractApprovalRepository()
        self.adjustment_repo = ContractValueAdjustmentRepository()
        self.promotion_repo = ContractObligationPromotionRepository()

    def get(self, request, obligation_type, obligation_id):
        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all()
            approvals = self.approval_repo.list_for_payment_obligation(obligation.id)
            adjustments = self.adjustment_repo.list_for_payment_obligation(obligation.id)

            payload = {
                "obligation": {
                    "id": str(obligation.id),
                    "type": "payment",
                    "contract_id": str(obligation.contract_id),
                    "state": obligation.state,
                    "due_date": obligation.due_date,
                    "obligor_id": obligation.obligor_id,
                    "obligee_id": obligation.obligee_id,
                    "amount_due": str(obligation.amount_due),
                    "amount_paid": str(obligation.amount_paid),
                    "installment_number": obligation.installment_number,
                },
                "execution_summary": self._build_execution_summary(sessions),
                "approval_summary": self._build_approval_summary(approvals),
                "adjustment_summary": {
                    "total_adjustments": adjustments.count(),
                },
                "promotion_summary": {
                    "promoted_count": 0,
                },
            }
            return Response(payload, status=status.HTTP_200_OK)

        if obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all()
            approvals = self.approval_repo.list_for_service_obligation(obligation.id)
            adjustments = self.adjustment_repo.list_for_service_obligation(obligation.id)
            promotions = self.promotion_repo.list_for_parent_service_obligation(
                obligation.id
            )

            payload = {
                "obligation": {
                    "id": str(obligation.id),
                    "type": "service",
                    "contract_id": str(obligation.contract_id),
                    "state": obligation.state,
                    "due_date": obligation.due_date,
                    "description": obligation.description,
                    "obligor_id": obligation.obligor_id,
                    "obligee_id": obligation.obligee_id,
                    "completed_at": obligation.completed_at,
                },
                "execution_summary": self._build_execution_summary(sessions),
                "approval_summary": self._build_approval_summary(approvals),
                "adjustment_summary": {
                    "total_adjustments": adjustments.count(),
                },
                "promotion_summary": {
                    "promoted_count": promotions.count(),
                },
            }
            return Response(payload, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Invalid obligation type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _build_execution_summary(self, sessions):
        event_count = 0
        session_count = sessions.count()

        for session in sessions:
            event_count += session.events.count()

        return {
            "session_count": session_count,
            "event_count": event_count,
        }

    def _build_approval_summary(self, approvals):
        return {
            "pending": approvals.filter(status="pending").count(),
            "approved": approvals.filter(status="approved").count(),
            "rejected": approvals.filter(status="rejected").count(),
        }



































