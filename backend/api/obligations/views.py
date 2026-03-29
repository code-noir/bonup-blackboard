# backend/api/obligations/views.py
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
User = get_user_model()

from backend.api.contracts.serializers import (
    ObligationExecutionSessionSerializer,
    ObligationExecutionEventSerializer,
    OpenExecutionSessionSerializer,
    ApprovalRequestSerializer,
    ApprovalDecisionSerializer,
    ApprovalRequestCreateSerializer,
    PromoteExecutionEventSerializer,
    ObligationPromotionSerializer,
    PromotedServiceObligationSerializer,
    ValueAdjustmentCreateSerializer,
    ValueAdjustmentSerializer,

)


from backend.api.contracts.services.obligation_promotion_service import (
    ObligationPromotionService,
)

from backend.api.contracts.services.approval_service import ApprovalService


from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
    ObligationExecutionSession,
    ObligationExecutionEvent,
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
from backend.api.contracts.services.obligation_execution_service import (
    ObligationExecutionService,
)

from backend.api.contracts.services.value_adjustment_service import (
    ValueAdjustmentService,
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
            obligation = get_object_or_404(ContractObligation, id=obligation_id)
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
            obligation = get_object_or_404(ContractServiceObligation, id=obligation_id)
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
            obligation = get_object_or_404(ContractObligation, id=obligation_id)
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
            obligation = get_object_or_404(ContractServiceObligation, id=obligation_id)
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
            obligation = get_object_or_404(ContractObligation, id=obligation_id)

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
            obligation = get_object_or_404(ContractServiceObligation, id=obligation_id)
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
    POST /api/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_service = ObligationExecutionService()

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

    def post(self, request, obligation_type, obligation_id):
        serializer = OpenExecutionSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = self.execution_service.open_session(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
            started_at=serializer.validated_data.get("started_at"),
        )

        output = ObligationExecutionSessionSerializer(session)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def _get_obligation(self, *, obligation_type, obligation_id):
        if obligation_type == "payment":
            return get_object_or_404(ContractObligation, id=obligation_id)

        if obligation_type == "service":
            return get_object_or_404(ContractServiceObligation, id=obligation_id)

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
            return get_object_or_404(ContractObligation, id=obligation_id)

        if obligation_type == "service":
            return get_object_or_404(ContractServiceObligation, id=obligation_id)

        raise Exception("Invalid obligation type")


class ObligationApprovalRequestListAPIView(APIView):
    """
    GET  /api/obligations/<obligation_type>/<obligation_id>/approval-requests/
    POST /api/obligations/<obligation_type>/<obligation_id>/approval-requests/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approval_repo = ContractApprovalRepository()
        self.service = ApprovalService()

    def get(self, request, obligation_type, obligation_id):
        if obligation_type == "payment":
            approvals = self.approval_repo.list_for_payment_obligation(obligation_id)
        elif obligation_type == "service":
            approvals = self.approval_repo.list_for_service_obligation(obligation_id)
        else:
            return Response(
                {"detail": "Invalid obligation type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = [
            {
                "approval_id": str(approval.id),
                "approval_type": approval.approval_type,
                "status": approval.status,
                "summary": approval.summary,
                "metadata": approval.metadata,
                "requested_at": approval.requested_at,
                "decided_at": approval.decided_at,
                "execution_event_id": (
                    str(approval.execution_event_id)
                    if approval.execution_event_id else None
                ),
                "payment_obligation_id": (
                    str(approval.payment_obligation_id)
                    if approval.payment_obligation_id else None
                ),
                "service_obligation_id": (
                    str(approval.service_obligation_id)
                    if approval.service_obligation_id else None
                ),
            }
            for approval in approvals.order_by("requested_at")
        ]

        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
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
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ObligationValueAdjustmentListCreateAPIView(APIView):
    """
    GET  /api/obligations/<obligation_type>/<obligation_id>/value-adjustments/
    POST /api/obligations/<obligation_type>/<obligation_id>/value-adjustments/

    V1 write support is manual additional_charge only.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ValueAdjustmentService()
        self.adjustment_repo = ContractValueAdjustmentRepository()

    def get(self, request, obligation_type, obligation_id):
        if obligation_type == "payment":
            adjustments = self.adjustment_repo.list_for_payment_obligation(obligation_id)
        elif obligation_type == "service":
            adjustments = self.adjustment_repo.list_for_service_obligation(obligation_id)
        else:
            return Response(
                {"detail": "Invalid obligation type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = [
            {
                "adjustment_id": str(adjustment.id),
                "event_id": (
                    str(adjustment.execution_event_id)
                    if adjustment.execution_event_id else None
                ),
                "session_id": (
                    str(adjustment.execution_event.session_id)
                    if adjustment.execution_event_id and adjustment.execution_event
                    else None
                ),
                "adjustment_type": adjustment.adjustment_type,
                "mode": adjustment.mode,
                "amount": str(adjustment.amount),
                "currency": adjustment.currency,
                "summary": adjustment.summary,
                "created_at": adjustment.created_at,
            }
            for adjustment in adjustments.order_by("created_at")
        ]

        serializer = ValueAdjustmentSerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        serializer = ValueAdjustmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        execution_event = None
        execution_event_id = serializer.validated_data.get("execution_event_id")
        if execution_event_id:
            execution_event = get_object_or_404(ObligationExecutionEvent, id=execution_event_id)

        if obligation_type == "payment":
            obligation = get_object_or_404(ContractObligation, id=obligation_id)
            adjustment = self.service.store_additional_charge(
                contract=obligation.contract,
                payment_obligation=obligation,
                execution_event=execution_event,
                amount=serializer.validated_data["amount"],
                currency=serializer.validated_data["currency"],
                summary=serializer.validated_data["summary"],
            )
        elif obligation_type == "service":
            obligation = get_object_or_404(ContractServiceObligation, id=obligation_id)
            adjustment = self.service.store_additional_charge(
                contract=obligation.contract,
                service_obligation=obligation,
                execution_event=execution_event,
                amount=serializer.validated_data["amount"],
                currency=serializer.validated_data["currency"],
                summary=serializer.validated_data["summary"],
            )
        else:
            return Response(
                {"detail": "Invalid obligation type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = ValueAdjustmentSerializer({
            "adjustment_id": adjustment.id,
            "event_id": adjustment.execution_event_id,
            "payment_obligation_id": adjustment.payment_obligation_id,
            "service_obligation_id": adjustment.service_obligation_id,
            "adjustment_type": adjustment.adjustment_type,
            "mode": adjustment.mode,
            "amount": adjustment.amount,
            "currency": adjustment.currency,
            "summary": adjustment.summary,
            "created_at": adjustment.created_at,
        })
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)








class ObligationPromotionListAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/promotions/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.promotion_repo = ContractObligationPromotionRepository()

    def get(self, request, obligation_type, obligation_id):
        if obligation_type != "service":
            return Response([], status=status.HTTP_200_OK)

        promotions = self.promotion_repo.list_for_parent_service_obligation(obligation_id)

        payload = [
            {
                "promotion_id": str(promotion.id),
                "promotion_type": promotion.promotion_type,
                "summary": promotion.summary,
                "source_execution_event_id": str(promotion.source_execution_event_id),
                "parent_service_obligation_id": (
                    str(promotion.parent_service_obligation_id)
                    if promotion.parent_service_obligation_id else None
                ),
                "promoted_service_obligation_id": (
                    str(promotion.promoted_service_obligation_id)
                    if promotion.promoted_service_obligation_id else None
                ),
                "created_at": promotion.created_at,
            }
            for promotion in promotions.order_by("created_at")
        ]

        return Response(payload, status=status.HTTP_200_OK)


class ObligationPromotedSideObligationListAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/promoted-side-obligations/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.promotion_repo = ContractObligationPromotionRepository()

    def get(self, request, obligation_type, obligation_id):
        if obligation_type != "service":
            return Response([], status=status.HTTP_200_OK)

        promotions = self.promotion_repo.list_for_parent_service_obligation(obligation_id)

        payload = []

        for promotion in promotions.order_by("created_at"):
            promoted = promotion.promoted_service_obligation
            if not promoted:
                continue

            payload.append({
                "obligation_id": str(promoted.id),
                "contract_id": str(promoted.contract_id),
                "description": promoted.description,
                "due_date": promoted.due_date,
                "state": promoted.state,
                "obligor_id": promoted.obligor_id,
                "obligee_id": promoted.obligee_id,
            })

        return Response(payload, status=status.HTTP_200_OK)

class ObligationExecutionSessionCloseAPIView(APIView):
    """
    POST /api/obligations/execution-sessions/<session_id>/close/
    """

    def post(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)

        if session.status == "closed":
            payload = {
                "id": session.id,
                "status": session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            }
            serializer = ObligationExecutionSessionSerializer(payload)
            return Response(serializer.data, status=status.HTTP_200_OK)

        session.status = "closed"

        if session.ended_at is None:
            session.ended_at = timezone.now()

        session.save(update_fields=["status", "ended_at"])

        payload = {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
        }

        serializer = ObligationExecutionSessionSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)
        

class ObligationExecutionSessionDetailAPIView(APIView):
    """
    GET /api/obligations/execution-sessions/<session_id>/
    """

    def get(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)

        payload = {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
        }

        serializer = ObligationExecutionSessionSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)      

class ObligationExecutionEventCreateAPIView(APIView):
    """
    POST /api/obligations/execution-sessions/<session_id>/execution-events/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_service = ObligationExecutionService()

    def post(self, request, session_id):
        event_type = request.data.get("event_type")
        task = request.data.get("task")
        observation = request.data.get("observation")
        summary = request.data.get("summary")
        estimated_duration_minutes = request.data.get("estimated_duration_minutes")
        estimated_cost_amount = request.data.get("estimated_cost_amount")
        estimated_cost_currency = request.data.get("estimated_cost_currency")

        if event_type != "execution_item_recorded":
            return Response(
                {
                    "event_type": [
                        "Only 'execution_item_recorded' is supported by this endpoint."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        required_errors = {}

        if not task:
            required_errors["task"] = ["This field is required."]
        if not observation:
            required_errors["observation"] = ["This field is required."]
        if not summary:
            required_errors["summary"] = ["This field is required."]
        if estimated_duration_minutes is None:
            required_errors["estimated_duration_minutes"] = ["This field is required."]
        if estimated_cost_amount is None:
            required_errors["estimated_cost_amount"] = ["This field is required."]
        if not estimated_cost_currency:
            required_errors["estimated_cost_currency"] = ["This field is required."]

        if required_errors:
            return Response(required_errors, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(ObligationExecutionSession, id=session_id)

        result = self.execution_service.record_execution_item(
            session=session,
            task=task,
            observation=observation,
            summary=summary,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_cost_amount=estimated_cost_amount,
            estimated_cost_currency=estimated_cost_currency,
            planned_execution_time=request.data.get("planned_execution_time"),
            metadata=request.data.get("metadata", {}),
            requested_by=request.data.get("requested_by"),
            requested_from=request.data.get("requested_from"),
        )

        event = result["event"]

        payload = {
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
        }

        output = ObligationExecutionEventSerializer(payload)
        return Response(output.data, status=status.HTTP_201_CREATED)


class ObligationApprovalRequestApproveAPIView(APIView):
    """
    POST /api/obligations/approval-requests/<approval_id>/approve/
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


class ObligationApprovalRequestRejectAPIView(APIView):
    """
    POST /api/obligations/approval-requests/<approval_id>/reject/
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

class ObligationExecutionEventPromotionAPIView(APIView):
    """
    POST /api/obligations/execution-events/<execution_event_id>/promote/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationPromotionService()

    def post(self, request, execution_event_id):
        serializer = PromoteExecutionEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        promotion = self.service.promote_execution_event_to_service_obligation(
            execution_event_id=execution_event_id,
            summary=serializer.validated_data.get("summary") or None,
            due_date=serializer.validated_data.get("due_date"),
        )

        promotion_payload = {
            "promotion_id": promotion.id,
            "promotion_type": promotion.promotion_type,
            "summary": promotion.summary,
            "source_execution_event_id": promotion.source_execution_event_id,
            "parent_service_obligation_id": promotion.parent_service_obligation_id,
            "promoted_service_obligation_id": promotion.promoted_service_obligation_id,
            "created_at": promotion.created_at,
        }

        promoted = promotion.promoted_service_obligation
        promoted_payload = {
            "obligation_id": promoted.id,
            "contract_id": promoted.contract_id,
            "description": promoted.description,
            "due_date": promoted.due_date,
            "state": promoted.state,
            "obligor_id": promoted.obligor_id,
            "obligee_id": promoted.obligee_id,
        }

        return Response(
            {
                "promotion": ObligationPromotionSerializer(promotion_payload).data,
                "promoted_service_obligation": PromotedServiceObligationSerializer(
                    promoted_payload
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

class ObligationApprovalRequestCreateAPIView(APIView):
    """
    POST /api/obligations/<obligation_type>/<obligation_id>/approval-requests/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ApprovalService()

    def post(self, request, obligation_type, obligation_id):
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
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class ObligationResolveAPIView(APIView):
    """
    POST /api/obligations/<obligation_type>/<obligation_id>/resolve/
    """

    def post(self, request, obligation_type, obligation_id):
        if obligation_type == "service":
            try:
                obligation = ContractServiceObligation.objects.get(id=obligation_id)
            except ContractServiceObligation.DoesNotExist:
                return Response(
                    {"detail": "Service obligation not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if obligation.state == "resolved":
                return Response(
                    {"detail": "Cannot resolve: obligation is already resolved."},
                    status=status.HTTP_409_CONFLICT,
                )

            if obligation.state == "breached":
                return Response(
                    {"detail": "Cannot resolve: obligation has been breached."},
                    status=status.HTTP_409_CONFLICT,
                )

            obligation.mark_completed()

            payload = {
                "id": str(obligation.id),
                "type": "service",
                "contract_id": str(obligation.contract_id),
                "state": obligation.state,
                "due_date": obligation.due_date,
                "description": obligation.description,
                "obligor_id": obligation.obligor_id,
                "obligee_id": obligation.obligee_id,
                "completed_at": obligation.completed_at,
            }
            return Response(payload, status=status.HTTP_200_OK)

        if obligation_type == "payment":
            return Response(
                {"detail": "Payment obligation resolve is not supported yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Invalid obligation type."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ObligationPaymentResolveAPIView(APIView):
    """
    POST /api/obligations/payment/<obligation_id>/resolve/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from backend.api.contracts.services.payment_resolution_service import (
            PaymentResolutionService,
        )
        self.service = PaymentResolutionService()

    def post(self, request, obligation_id):
        try:
            obligation = self.service.resolve(obligation_id=obligation_id)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "id": str(obligation.id),
            "state": obligation.state,
            "amount_due": str(obligation.amount_due),
            "amount_paid": str(obligation.amount_paid),
        }

        return Response(payload, status=status.HTTP_200_OK)


class ObligationExecutionEventDetailAPIView(APIView):
    """
    GET /api/obligations/execution-events/<event_id>/
    """

    def get(self, request, event_id):
        try:
            event = ObligationExecutionEvent.objects.get(id=event_id)
        except ObligationExecutionEvent.DoesNotExist:
            return Response(
                {"error": "Execution event not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = {
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
        }

        serializer = ObligationExecutionEventSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ObligationExecutionEventDeleteAPIView(APIView):
    """
    DELETE /api/obligations/execution-events/<event_id>/delete/
    """

    def delete(self, request, event_id):
        try:
            event = ObligationExecutionEvent.objects.get(id=event_id)
        except ObligationExecutionEvent.DoesNotExist:
            return Response(
                {"error": "Execution event not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


