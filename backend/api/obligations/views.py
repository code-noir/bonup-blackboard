
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


class ObligationTimelineAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/timeline/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approval_repo = ContractApprovalRepository()
        self.adjustment_repo = ContractValueAdjustmentRepository()
        self.promotion_repo = ContractObligationPromotionRepository()

    def get(self, request, obligation_type, obligation_id):
        timeline = []

        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all().order_by("started_at")
            approvals = self.approval_repo.list_for_payment_obligation(obligation.id)
            adjustments = self.adjustment_repo.list_for_payment_obligation(obligation.id)

            for session in sessions:
                timeline.append({
                    "entry_type": "execution_session",
                    "entry_id": str(session.id),
                    "status": session.status,
                    "summary": f"Execution session {session.status}",
                    "created_at": session.created_at,
                })

                for event in session.events.all().order_by("created_at"):
                    timeline.append({
                        "entry_type": "execution_event",
                        "entry_id": str(event.id),
                        "session_id": str(session.id),
                        "event_type": event.event_type,
                        "task": event.task,
                        "observation": event.observation,
                        "summary": event.summary,
                        "created_at": event.created_at,
                    })

            for approval in approvals:
                timeline.append({
                    "entry_type": "approval_request",
                    "entry_id": str(approval.id),
                    "status": approval.status,
                    "summary": approval.summary,
                    "execution_event_id": (
                        str(approval.execution_event_id)
                        if approval.execution_event_id else None
                    ),
                    "created_at": approval.requested_at,
                })

            for adjustment in adjustments:
                timeline.append({
                    "entry_type": "value_adjustment",
                    "entry_id": str(adjustment.id),
                    "adjustment_type": adjustment.adjustment_type,
                    "summary": adjustment.summary,
                    "amount": str(adjustment.amount),
                    "currency": adjustment.currency,
                    "execution_event_id": (
                        str(adjustment.execution_event_id)
                        if adjustment.execution_event_id else None
                    ),
                    "created_at": adjustment.created_at,
                })

            timeline.sort(key=lambda x: x["created_at"])
            return Response({"timeline": timeline}, status=status.HTTP_200_OK)

        if obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all().order_by("started_at")
            approvals = self.approval_repo.list_for_service_obligation(obligation.id)
            adjustments = self.adjustment_repo.list_for_service_obligation(obligation.id)
            promotions = self.promotion_repo.list_for_parent_service_obligation(
                obligation.id
            )

            for session in sessions:
                timeline.append({
                    "entry_type": "execution_session",
                    "entry_id": str(session.id),
                    "status": session.status,
                    "summary": f"Execution session {session.status}",
                    "created_at": session.created_at,
                })

                for event in session.events.all().order_by("created_at"):
                    timeline.append({
                        "entry_type": "execution_event",
                        "entry_id": str(event.id),
                        "session_id": str(session.id),
                        "event_type": event.event_type,
                        "task": event.task,
                        "observation": event.observation,
                        "summary": event.summary,
                        "created_at": event.created_at,
                    })

            for approval in approvals:
                timeline.append({
                    "entry_type": "approval_request",
                    "entry_id": str(approval.id),
                    "status": approval.status,
                    "summary": approval.summary,
                    "execution_event_id": (
                        str(approval.execution_event_id)
                        if approval.execution_event_id else None
                    ),
                    "created_at": approval.requested_at,
                })

            for adjustment in adjustments:
                timeline.append({
                    "entry_type": "value_adjustment",
                    "entry_id": str(adjustment.id),
                    "adjustment_type": adjustment.adjustment_type,
                    "summary": adjustment.summary,
                    "amount": str(adjustment.amount),
                    "currency": adjustment.currency,
                    "execution_event_id": (
                        str(adjustment.execution_event_id)
                        if adjustment.execution_event_id else None
                    ),
                    "created_at": adjustment.created_at,
                })

            for promotion in promotions:
                timeline.append({
                    "entry_type": "promotion",
                    "entry_id": str(promotion.id),
                    "promotion_type": promotion.promotion_type,
                    "summary": promotion.summary,
                    "source_execution_event_id": str(promotion.source_execution_event_id),
                    "promoted_service_obligation_id": (
                        str(promotion.promoted_service_obligation_id)
                        if promotion.promoted_service_obligation_id else None
                    ),
                    "created_at": promotion.created_at,
                })

            timeline.sort(key=lambda x: x["created_at"])
            return Response({"timeline": timeline}, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Invalid obligation type."},
            status=status.HTTP_400_BAD_REQUEST,
        )








































