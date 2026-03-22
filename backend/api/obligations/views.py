# backend/api/obligations/views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from backend.api.contracts.serializers import (ObligationExecutionSessionSerializer, ObligationExecutionEventSerializer)
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


class ObligationListAPIView(APIView):
    """
    GET /api/obligations/

    Query params:
    - type=payment|service
    - state=<state>
    - role=obligor|obligee
    - user_id=<int>
    """

    def get(self, request):
        obligation_type = request.query_params.get("type")
        state = request.query_params.get("state")
        role = request.query_params.get("role")
        user_id = request.query_params.get("user_id")

        results = []

        include_payment = obligation_type in (None, "", "payment")
        include_service = obligation_type in (None, "", "service")

        if include_payment:
            payment_qs = ContractObligation.objects.all().order_by("due_date")

            if state:
                payment_qs = payment_qs.filter(state=state)

            if role == "obligor" and user_id:
                payment_qs = payment_qs.filter(obligor_id=user_id)

            if role == "obligee" and user_id:
                payment_qs = payment_qs.filter(obligee_id=user_id)

            for ob in payment_qs:
                results.append({
                    "id": str(ob.id),
                    "type": "payment",
                    "contract_id": str(ob.contract_id),
                    "state": ob.state,
                    "due_date": ob.due_date,
                    "obligor_id": ob.obligor_id,
                    "obligee_id": ob.obligee_id,
                    "amount_due": str(ob.amount_due),
                    "amount_paid": str(ob.amount_paid),
                    "installment_number": ob.installment_number,
                })

        if include_service:
            service_qs = ContractServiceObligation.objects.all().order_by("due_date")

            if state:
                service_qs = service_qs.filter(state=state)

            if role == "obligor" and user_id:
                service_qs = service_qs.filter(obligor_id=user_id)

            if role == "obligee" and user_id:
                service_qs = service_qs.filter(obligee_id=user_id)

            for ob in service_qs:
                results.append({
                    "id": str(ob.id),
                    "type": "service",
                    "contract_id": str(ob.contract_id),
                    "state": ob.state,
                    "due_date": ob.due_date,
                    "obligor_id": ob.obligor_id,
                    "obligee_id": ob.obligee_id,
                    "description": ob.description,
                    "completed_at": ob.completed_at,
                })

        results.sort(key=lambda x: (x["due_date"] is None, x["due_date"]))

        return Response(
            {
                "count": len(results),
                "results": results,
            },
            status=status.HTTP_200_OK,
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


class ObligationNextActionsAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/next-actions/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approval_repo = ContractApprovalRepository()
        self.adjustment_repo = ContractValueAdjustmentRepository()
        self.promotion_repo = ContractObligationPromotionRepository()

    def get(self, request, obligation_type, obligation_id):
        actions = []

        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)

            if obligation.state in ("due", "overdue", "grace", "defaulted") and (
                obligation.amount_paid < obligation.amount_due
            ):
                actions.append({
                    "action_type": "payment_required",
                    "priority": "high",
                    "summary": "Payment is still required for this obligation.",
                })

            if obligation.state == "resolved":
                actions.append({
                    "action_type": "no_action",
                    "priority": "low",
                    "summary": "No action needed. Payment obligation is resolved.",
                })

            return Response({"next_actions": actions}, status=status.HTTP_200_OK)

        if obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all()
            pending_approvals = self.approval_repo.list_for_service_obligation(
                obligation.id
            ).filter(status="pending")
            adjustments = self.adjustment_repo.list_for_service_obligation(obligation.id)
            promotions = self.promotion_repo.list_for_parent_service_obligation(
                obligation.id
            )

            if obligation.state == "active" and not sessions.exists():
                actions.append({
                    "action_type": "open_execution_session",
                    "priority": "medium",
                    "summary": "Open an execution session for this service obligation.",
                })

            if pending_approvals.exists():
                actions.append({
                    "action_type": "review_pending_approvals",
                    "priority": "high",
                    "summary": "Review pending approval requests for this obligation.",
                    "count": pending_approvals.count(),
                })

            if adjustments.exists():
                actions.append({
                    "action_type": "review_value_adjustments",
                    "priority": "medium",
                    "summary": "Review stored value adjustments for this obligation.",
                    "count": adjustments.count(),
                })

            if promotions.exists():
                actions.append({
                    "action_type": "review_promoted_side_obligations",
                    "priority": "medium",
                    "summary": "Review promoted side obligations linked to this obligation.",
                    "count": promotions.count(),
                })

            if obligation.state == "resolved":
                actions.append({
                    "action_type": "no_action",
                    "priority": "low",
                    "summary": "No action needed. Service obligation is resolved.",
                })

            return Response({"next_actions": actions}, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Invalid obligation type."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ObligationDashboardSummaryAPIView(APIView):
    """
    GET /api/obligations/dashboard-summary/

    Lightweight obligation-domain overview for the obligations area.
    Reuses the same filter semantics as ObligationListAPIView.

    Query params:
    - type=payment|service
    - state=<state>
    - role=obligor|obligee
    - user_id=<int>
    """

    def get(self, request):
        obligation_type = request.query_params.get("type")
        state = request.query_params.get("state")
        role = request.query_params.get("role")
        user_id = request.query_params.get("user_id")

        include_payment = obligation_type in (None, "", "payment")
        include_service = obligation_type in (None, "", "service")

        payment_qs = ContractObligation.objects.none()
        service_qs = ContractServiceObligation.objects.none()

        if include_payment:
            payment_qs = ContractObligation.objects.all()

            if state:
                payment_qs = payment_qs.filter(state=state)

            if role == "obligor" and user_id:
                payment_qs = payment_qs.filter(obligor_id=user_id)

            if role == "obligee" and user_id:
                payment_qs = payment_qs.filter(obligee_id=user_id)

        if include_service:
            service_qs = ContractServiceObligation.objects.all()

            if state:
                service_qs = service_qs.filter(state=state)

            if role == "obligor" and user_id:
                service_qs = service_qs.filter(obligor_id=user_id)

            if role == "obligee" and user_id:
                service_qs = service_qs.filter(obligee_id=user_id)

        payment_count = payment_qs.count()
        service_count = service_qs.count()

        payment_state_counts = {
            "active": 0,
            "due": 0,
            "grace": 0,
            "overdue": 0,
            "defaulted": 0,
            "resolved": 0,
        }

        for ob in payment_qs:
            payment_state_counts[ob.state] = payment_state_counts.get(ob.state, 0) + 1

        service_state_counts = {
            "active": 0,
            "due": 0,
            "overdue": 0,
            "resolved": 0,
        }

        for ob in service_qs:
            service_state_counts[ob.state] = service_state_counts.get(ob.state, 0) + 1

        payment_due_or_unpaid_ids = set()
        payment_overdue_ids = set()
        payment_defaulted_ids = set()

        for ob in payment_qs:
            if ob.state in ("due", "grace", "overdue", "defaulted") and (
                ob.amount_paid < ob.amount_due
            ):
                payment_due_or_unpaid_ids.add(str(ob.id))

            if ob.state == "overdue":
                payment_overdue_ids.add(str(ob.id))

            if ob.state == "defaulted":
                payment_defaulted_ids.add(str(ob.id))

        service_active_without_execution_ids = set()
        service_overdue_ids = set()

        for ob in service_qs:
            if ob.state == "active" and not ob.execution_sessions.exists():
                service_active_without_execution_ids.add(str(ob.id))

            if ob.state == "overdue":
                service_overdue_ids.add(str(ob.id))

        total_attention_ids = (
            payment_due_or_unpaid_ids
            .union(payment_overdue_ids)
            .union(payment_defaulted_ids)
            .union(service_active_without_execution_ids)
            .union(service_overdue_ids)
        )

        payload = {
            "filters": {
                "type": obligation_type,
                "state": state,
                "role": role,
                "user_id": user_id,
            },
            "counts": {
                "total": payment_count + service_count,
                "payment": payment_count,
                "service": service_count,
            },
            "by_state": {
                "payment": payment_state_counts,
                "service": service_state_counts,
            },
            "attention": {
                "total_requiring_attention": len(total_attention_ids),
                "payment": {
                    "due_or_unpaid": len(payment_due_or_unpaid_ids),
                    "overdue": len(payment_overdue_ids),
                    "defaulted": len(payment_defaulted_ids),
                },
                "service": {
                    "active_without_execution": len(service_active_without_execution_ids),
                    "overdue": len(service_overdue_ids),
                },
            },
        }

        return Response(payload, status=status.HTTP_200_OK)


class ObligationExecutionSessionListAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    """

    def get(self, request, obligation_type, obligation_id):
        obligation = self._get_obligation(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
        )

        sessions = obligation.execution_sessions.all().order_by("started_at")

        payload = [
            {
                "id": session.id,
                "status": session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            }
            for session in sessions
        ]

        serializer = ObligationExecutionSessionSerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_obligation(self, *, obligation_type, obligation_id):
        if obligation_type == "payment":
            return ContractObligation.objects.get(id=obligation_id)

        if obligation_type == "service":
            return ContractServiceObligation.objects.get(id=obligation_id)

        raise Exception("Invalid obligation type")


class ObligationExecutionEventListAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/execution-events/
    """

    def get(self, request, obligation_type, obligation_id):
        obligation = self._get_obligation(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
        )

        payload = []

        sessions = obligation.execution_sessions.all().order_by("started_at")

        for session in sessions:
            events = session.events.all().order_by("created_at")

            for event in events:
                payload.append({
                    "id": event.id,
                    "event_type": event.event_type,
                    "task": event.task,
                    "observation": event.observation,
                    "summary": event.summary,
                    "estimated_duration_minutes": event.estimated_duration_minutes,
                    "estimated_cost_amount": event.estimated_cost_amount,
                    "estimated_cost_currency": event.estimated_cost_currency,
                    "planned_execution_time": event.planned_execution_time,
                    "metadata": event.metadata,
                    "created_at": event.created_at,
                })

        serializer = ObligationExecutionEventSerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_obligation(self, *, obligation_type, obligation_id):
        if obligation_type == "payment":
            return ContractObligation.objects.get(id=obligation_id)

        if obligation_type == "service":
            return ContractServiceObligation.objects.get(id=obligation_id)

        raise Exception("Invalid obligation type")


































































