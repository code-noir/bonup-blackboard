# backend/api/obligations/views.py

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestCreateSerializer,
    ApprovalRequestSerializer,
    ObligationExecutionEventSerializer,
    ObligationExecutionSessionSerializer,
    ObligationPromotionSerializer,
    OpenExecutionSessionSerializer,
    PromotedServiceObligationSerializer,
    PromoteExecutionEventSerializer,
    ValueAdjustmentCreateSerializer,
    ValueAdjustmentSerializer,
)
from backend.api.contracts.permissions import (
    contract_party_response,
    get_contract_for_object,
    is_party,
)
from backend.api.contracts.services.approval_service import ApprovalService
from backend.api.contracts.services.obligation_execution_service import (
    ObligationExecutionService,
)
from backend.api.contracts.services.obligation_promotion_service import (
    ObligationPromotionService,
)
from backend.api.contracts.services.value_adjustment_service import ValueAdjustmentService
from backend.contracts.models import (
    ContractApprovalRequest,
    ContractObligation,
    ContractServiceObligation,
    ObligationExecutionEvent,
    ObligationExecutionSession,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)
from backend.infrastructure.repositories.contract_obligation_promotion_repository import (
    ContractObligationPromotionRepository,
)
from backend.infrastructure.repositories.contract_value_adjustment_repository import (
    ContractValueAdjustmentRepository,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _party_q(user):
    """Q filter: obligations whose contract lists this user as a party."""
    return (
        Q(contract__initiator=user)
        | Q(contract__counterparty_email=user.email)
    )


def _get_obligation_or_404(obligation_type, obligation_id):
    """
    Look up a ContractObligation or ContractServiceObligation.
    Returns None if obligation_type is invalid (caller must handle).
    """
    if obligation_type == "payment":
        return get_object_or_404(ContractObligation, id=obligation_id)
    if obligation_type == "service":
        return get_object_or_404(ContractServiceObligation, id=obligation_id)
    return None


def _invalid_type_response():
    return Response(
        {"detail": "Invalid obligation type."},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ---------------------------------------------------------------------------
# List + Dashboard
# ---------------------------------------------------------------------------

class ObligationListAPIView(APIView):
    """
    GET /api/obligations/

    Returns only obligations that belong to contracts where the authenticated
    user is the initiator or counterparty.

    Query params:
    - type=payment|service
    - state=<state>
    - role=obligor|obligee  (filters to obligations where the caller holds that role)
    """

    def get(self, request):
        obligation_type = request.query_params.get("type")
        state = request.query_params.get("state")
        role = request.query_params.get("role")

        results = []

        include_payment = obligation_type in (None, "", "payment")
        include_service = obligation_type in (None, "", "service")

        if include_payment:
            payment_qs = (
                ContractObligation.objects
                .filter(_party_q(request.user))
                .order_by("due_date")
            )
            if state:
                payment_qs = payment_qs.filter(state=state)
            if role == "obligor":
                payment_qs = payment_qs.filter(obligor=request.user)
            elif role == "obligee":
                payment_qs = payment_qs.filter(obligee=request.user)

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
            service_qs = (
                ContractServiceObligation.objects
                .filter(_party_q(request.user))
                .order_by("due_date")
            )
            if state:
                service_qs = service_qs.filter(state=state)
            if role == "obligor":
                service_qs = service_qs.filter(obligor=request.user)
            elif role == "obligee":
                service_qs = service_qs.filter(obligee=request.user)

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
        return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)


class ObligationDashboardSummaryAPIView(APIView):
    """
    GET /api/obligations/dashboard-summary/

    Scoped to the authenticated user's contracts only.

    Query params:
    - type=payment|service
    - state=<state>
    - role=obligor|obligee
    """

    def get(self, request):
        obligation_type = request.query_params.get("type")
        state = request.query_params.get("state")
        role = request.query_params.get("role")

        include_payment = obligation_type in (None, "", "payment")
        include_service = obligation_type in (None, "", "service")

        payment_qs = ContractObligation.objects.none()
        service_qs = ContractServiceObligation.objects.none()

        if include_payment:
            payment_qs = ContractObligation.objects.filter(_party_q(request.user))
            if state:
                payment_qs = payment_qs.filter(state=state)
            if role == "obligor":
                payment_qs = payment_qs.filter(obligor=request.user)
            elif role == "obligee":
                payment_qs = payment_qs.filter(obligee=request.user)

        if include_service:
            service_qs = ContractServiceObligation.objects.filter(_party_q(request.user))
            if state:
                service_qs = service_qs.filter(state=state)
            if role == "obligor":
                service_qs = service_qs.filter(obligor=request.user)
            elif role == "obligee":
                service_qs = service_qs.filter(obligee=request.user)

        payment_count = payment_qs.count()
        service_count = service_qs.count()

        payment_state_counts = {s: 0 for s in ("active", "due", "grace", "overdue", "defaulted", "resolved")}
        for ob in payment_qs:
            payment_state_counts[ob.state] = payment_state_counts.get(ob.state, 0) + 1

        service_state_counts = {s: 0 for s in ("active", "due", "overdue", "resolved")}
        for ob in service_qs:
            service_state_counts[ob.state] = service_state_counts.get(ob.state, 0) + 1

        payment_due_or_unpaid_ids = set()
        payment_overdue_ids = set()
        payment_defaulted_ids = set()
        for ob in payment_qs:
            if ob.state in ("due", "grace", "overdue", "defaulted") and ob.amount_paid < ob.amount_due:
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
            | payment_overdue_ids
            | payment_defaulted_ids
            | service_active_without_execution_ids
            | service_overdue_ids
        )

        return Response({
            "filters": {"type": obligation_type, "state": state, "role": role},
            "counts": {"total": payment_count + service_count, "payment": payment_count, "service": service_count},
            "by_state": {"payment": payment_state_counts, "service": service_state_counts},
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
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Detail views
# ---------------------------------------------------------------------------

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
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        if obligation_type == "payment":
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
                "adjustment_summary": {"total_adjustments": adjustments.count()},
                "promotion_summary": {"promoted_count": 0},
            }
            return Response(payload, status=status.HTTP_200_OK)

        # service
        sessions = obligation.execution_sessions.all()
        approvals = self.approval_repo.list_for_service_obligation(obligation.id)
        adjustments = self.adjustment_repo.list_for_service_obligation(obligation.id)
        promotions = self.promotion_repo.list_for_parent_service_obligation(obligation.id)
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
            "adjustment_summary": {"total_adjustments": adjustments.count()},
            "promotion_summary": {"promoted_count": promotions.count()},
        }
        return Response(payload, status=status.HTTP_200_OK)

    def _build_execution_summary(self, sessions):
        event_count = sum(s.events.count() for s in sessions)
        return {"session_count": sessions.count(), "event_count": event_count}

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
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        timeline = []

        if obligation_type == "payment":
            sessions = obligation.execution_sessions.all().order_by("started_at")
            approvals = self.approval_repo.list_for_payment_obligation(obligation.id)
            adjustments = self.adjustment_repo.list_for_payment_obligation(obligation.id)
        else:
            sessions = obligation.execution_sessions.all().order_by("started_at")
            approvals = self.approval_repo.list_for_service_obligation(obligation.id)
            adjustments = self.adjustment_repo.list_for_service_obligation(obligation.id)

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
                "execution_event_id": str(approval.execution_event_id) if approval.execution_event_id else None,
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
                "execution_event_id": str(adjustment.execution_event_id) if adjustment.execution_event_id else None,
                "created_at": adjustment.created_at,
            })

        if obligation_type == "service":
            promotions = self.promotion_repo.list_for_parent_service_obligation(obligation.id)
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
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        actions = []

        if obligation_type == "payment":
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

        # service
        sessions = obligation.execution_sessions.all()
        pending_approvals = self.approval_repo.list_for_service_obligation(obligation.id).filter(status="pending")
        adjustments = self.adjustment_repo.list_for_service_obligation(obligation.id)
        promotions = self.promotion_repo.list_for_parent_service_obligation(obligation.id)

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


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

class ObligationResolveAPIView(APIView):
    """
    POST /api/obligations/<obligation_type>/<obligation_id>/resolve/
    """

    def post(self, request, obligation_type, obligation_id):
        if obligation_type == "service":
            obligation = get_object_or_404(ContractServiceObligation, id=obligation_id)
            if not is_party(request.user, obligation.contract):
                return contract_party_response()

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
            return Response({
                "id": str(obligation.id),
                "type": "service",
                "contract_id": str(obligation.contract_id),
                "state": obligation.state,
                "due_date": obligation.due_date,
                "description": obligation.description,
                "obligor_id": obligation.obligor_id,
                "obligee_id": obligation.obligee_id,
                "completed_at": obligation.completed_at,
            }, status=status.HTTP_200_OK)

        if obligation_type == "payment":
            return Response(
                {"detail": "Payment obligation resolve is not supported yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return _invalid_type_response()


class ObligationPaymentResolveAPIView(APIView):
    """
    POST /api/obligations/payment/<obligation_id>/resolve/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from backend.api.contracts.services.payment_resolution_service import PaymentResolutionService
        self.service = PaymentResolutionService()

    def post(self, request, obligation_id):
        obligation = get_object_or_404(ContractObligation, id=obligation_id)
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        try:
            obligation = self.service.resolve(obligation_id=obligation_id)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "id": str(obligation.id),
            "state": obligation.state,
            "amount_due": str(obligation.amount_due),
            "amount_paid": str(obligation.amount_paid),
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Execution sessions
# ---------------------------------------------------------------------------

class ObligationExecutionSessionListAPIView(APIView):
    """
    GET  /api/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    POST /api/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_service = ObligationExecutionService()

    def get(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        sessions = obligation.execution_sessions.all().order_by("started_at")
        payload = [
            {"id": s.id, "status": s.status, "started_at": s.started_at, "ended_at": s.ended_at}
            for s in sessions
        ]
        return Response(ObligationExecutionSessionSerializer(payload, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        serializer = OpenExecutionSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = self.execution_service.open_session(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
            started_at=serializer.validated_data.get("started_at"),
        )
        return Response(ObligationExecutionSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class ObligationExecutionSessionDetailAPIView(APIView):
    """
    GET /api/obligations/execution-sessions/<session_id>/
    """

    def get(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)
        contract = get_contract_for_object(session)
        if not is_party(request.user, contract):
            return contract_party_response()

        payload = {"id": session.id, "status": session.status, "started_at": session.started_at, "ended_at": session.ended_at}
        return Response(ObligationExecutionSessionSerializer(payload).data, status=status.HTTP_200_OK)


class ObligationExecutionSessionCloseAPIView(APIView):
    """
    POST /api/obligations/execution-sessions/<session_id>/close/
    """

    def post(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)
        contract = get_contract_for_object(session)
        if not is_party(request.user, contract):
            return contract_party_response()

        if session.status == "closed":
            payload = {"id": session.id, "status": session.status, "started_at": session.started_at, "ended_at": session.ended_at}
            return Response(ObligationExecutionSessionSerializer(payload).data, status=status.HTTP_200_OK)

        session.status = "closed"
        if session.ended_at is None:
            session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])

        payload = {"id": session.id, "status": session.status, "started_at": session.started_at, "ended_at": session.ended_at}
        return Response(ObligationExecutionSessionSerializer(payload).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Execution events
# ---------------------------------------------------------------------------

class ObligationExecutionEventListAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/execution-events/
    """

    def get(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        payload = []
        for session in obligation.execution_sessions.all().order_by("started_at"):
            for event in session.events.all().order_by("created_at"):
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
        return Response(ObligationExecutionEventSerializer(payload, many=True).data, status=status.HTTP_200_OK)


class ObligationExecutionEventDetailAPIView(APIView):
    """
    GET /api/obligations/execution-events/<event_id>/
    """

    def get(self, request, event_id):
        event = get_object_or_404(ObligationExecutionEvent, id=event_id)
        contract = get_contract_for_object(event)
        if not is_party(request.user, contract):
            return contract_party_response()

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
        return Response(ObligationExecutionEventSerializer(payload).data, status=status.HTTP_200_OK)


class ObligationExecutionEventDeleteAPIView(APIView):
    """
    DELETE /api/obligations/execution-events/<event_id>/delete/
    """

    def delete(self, request, event_id):
        event = get_object_or_404(ObligationExecutionEvent, id=event_id)
        contract = get_contract_for_object(event)
        if not is_party(request.user, contract):
            return contract_party_response()

        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ObligationExecutionEventCreateAPIView(APIView):
    """
    POST /api/obligations/execution-sessions/<session_id>/execution-events/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_service = ObligationExecutionService()

    def post(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)
        contract = get_contract_for_object(session)
        if not is_party(request.user, contract):
            return contract_party_response()

        event_type = request.data.get("event_type")
        task = request.data.get("task")
        observation = request.data.get("observation")
        summary = request.data.get("summary")
        estimated_duration_minutes = request.data.get("estimated_duration_minutes")
        estimated_cost_amount = request.data.get("estimated_cost_amount")
        estimated_cost_currency = request.data.get("estimated_cost_currency")

        if event_type != "execution_item_recorded":
            return Response(
                {"event_type": ["Only 'execution_item_recorded' is supported by this endpoint."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = {}
        if not task:
            errors["task"] = ["This field is required."]
        if not observation:
            errors["observation"] = ["This field is required."]
        if not summary:
            errors["summary"] = ["This field is required."]
        if estimated_duration_minutes is None:
            errors["estimated_duration_minutes"] = ["This field is required."]
        if estimated_cost_amount is None:
            errors["estimated_cost_amount"] = ["This field is required."]
        if not estimated_cost_currency:
            errors["estimated_cost_currency"] = ["This field is required."]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

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
        return Response(ObligationExecutionEventSerializer(payload).data, status=status.HTTP_201_CREATED)


class ObligationExecutionEventPromotionAPIView(APIView):
    """
    POST /api/obligations/execution-events/<execution_event_id>/promote/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationPromotionService()

    def post(self, request, execution_event_id):
        event = get_object_or_404(ObligationExecutionEvent, id=execution_event_id)
        contract = get_contract_for_object(event)
        if not is_party(request.user, contract):
            return contract_party_response()

        serializer = PromoteExecutionEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        promotion = self.service.promote_execution_event_to_service_obligation(
            execution_event_id=execution_event_id,
            summary=serializer.validated_data.get("summary") or None,
            due_date=serializer.validated_data.get("due_date"),
        )

        promoted = promotion.promoted_service_obligation
        return Response({
            "promotion": ObligationPromotionSerializer({
                "promotion_id": promotion.id,
                "promotion_type": promotion.promotion_type,
                "summary": promotion.summary,
                "source_execution_event_id": promotion.source_execution_event_id,
                "parent_service_obligation_id": promotion.parent_service_obligation_id,
                "promoted_service_obligation_id": promotion.promoted_service_obligation_id,
                "created_at": promotion.created_at,
            }).data,
            "promoted_service_obligation": PromotedServiceObligationSerializer({
                "obligation_id": promoted.id,
                "contract_id": promoted.contract_id,
                "description": promoted.description,
                "due_date": promoted.due_date,
                "state": promoted.state,
                "obligor_id": promoted.obligor_id,
                "obligee_id": promoted.obligee_id,
            }).data,
        }, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Approval requests
# ---------------------------------------------------------------------------

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
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        if obligation_type == "payment":
            approvals = self.approval_repo.list_for_payment_obligation(obligation_id)
        else:
            approvals = self.approval_repo.list_for_service_obligation(obligation_id)

        payload = [
            {
                "approval_id": str(a.id),
                "approval_type": a.approval_type,
                "status": a.status,
                "summary": a.summary,
                "metadata": a.metadata,
                "requested_at": a.requested_at,
                "decided_at": a.decided_at,
                "execution_event_id": str(a.execution_event_id) if a.execution_event_id else None,
                "payment_obligation_id": str(a.payment_obligation_id) if a.payment_obligation_id else None,
                "service_obligation_id": str(a.service_obligation_id) if a.service_obligation_id else None,
            }
            for a in approvals.order_by("requested_at")
        ]
        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
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
        if serializer.validated_data.get("requested_by_id"):
            requested_by = get_object_or_404(User, id=serializer.validated_data["requested_by_id"])
        if serializer.validated_data.get("requested_from_id"):
            requested_from = get_object_or_404(User, id=serializer.validated_data["requested_from_id"])

        approval = self.service.request_execution_item_approval(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
            execution_event=execution_event,
            requested_by=requested_by,
            requested_from=requested_from,
            summary=serializer.validated_data["summary"],
            metadata=serializer.validated_data.get("metadata"),
        )

        return Response(ApprovalRequestSerializer({
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
        }).data, status=status.HTTP_201_CREATED)


class ObligationApprovalRequestApproveAPIView(APIView):
    """
    POST /api/obligations/approval-requests/<approval_id>/approve/

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
        return Response(ApprovalRequestSerializer({
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
        }).data, status=status.HTTP_200_OK)


class ObligationApprovalRequestRejectAPIView(APIView):
    """
    POST /api/obligations/approval-requests/<approval_id>/reject/

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
        return Response(ApprovalRequestSerializer({
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
        }).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Value adjustments
# ---------------------------------------------------------------------------

class ObligationValueAdjustmentListCreateAPIView(APIView):
    """
    GET  /api/obligations/<obligation_type>/<obligation_id>/value-adjustments/
    POST /api/obligations/<obligation_type>/<obligation_id>/value-adjustments/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ValueAdjustmentService()
        self.adjustment_repo = ContractValueAdjustmentRepository()

    def get(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        if obligation_type == "payment":
            adjustments = self.adjustment_repo.list_for_payment_obligation(obligation_id)
        else:
            adjustments = self.adjustment_repo.list_for_service_obligation(obligation_id)

        payload = [
            {
                "adjustment_id": str(adj.id),
                "event_id": str(adj.execution_event_id) if adj.execution_event_id else None,
                "session_id": (
                    str(adj.execution_event.session_id)
                    if adj.execution_event_id and adj.execution_event else None
                ),
                "adjustment_type": adj.adjustment_type,
                "mode": adj.mode,
                "amount": str(adj.amount),
                "currency": adj.currency,
                "summary": adj.summary,
                "created_at": adj.created_at,
            }
            for adj in adjustments.order_by("created_at")
        ]
        return Response(ValueAdjustmentSerializer(payload, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        serializer = ValueAdjustmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        execution_event = None
        if serializer.validated_data.get("execution_event_id"):
            execution_event = get_object_or_404(ObligationExecutionEvent, id=serializer.validated_data["execution_event_id"])

        kwargs = dict(
            contract=obligation.contract,
            execution_event=execution_event,
            amount=serializer.validated_data["amount"],
            currency=serializer.validated_data["currency"],
            summary=serializer.validated_data["summary"],
        )
        if obligation_type == "payment":
            adjustment = self.service.store_additional_charge(payment_obligation=obligation, **kwargs)
        else:
            adjustment = self.service.store_additional_charge(service_obligation=obligation, **kwargs)

        return Response(ValueAdjustmentSerializer({
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
        }).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------

class ObligationPromotionListAPIView(APIView):
    """
    GET /api/obligations/<obligation_type>/<obligation_id>/promotions/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.promotion_repo = ContractObligationPromotionRepository()

    def get(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        if obligation_type != "service":
            return Response([], status=status.HTTP_200_OK)

        promotions = self.promotion_repo.list_for_parent_service_obligation(obligation_id)
        payload = [
            {
                "promotion_id": str(p.id),
                "promotion_type": p.promotion_type,
                "summary": p.summary,
                "source_execution_event_id": str(p.source_execution_event_id),
                "parent_service_obligation_id": str(p.parent_service_obligation_id) if p.parent_service_obligation_id else None,
                "promoted_service_obligation_id": str(p.promoted_service_obligation_id) if p.promoted_service_obligation_id else None,
                "created_at": p.created_at,
            }
            for p in promotions.order_by("created_at")
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
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

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


# ---------------------------------------------------------------------------
# Proof of work
# ---------------------------------------------------------------------------

class ObligationProofOfWorkAPIView(APIView):
    """
    POST /api/obligations/<obligation_type>/<obligation_id>/proof/
    """

    def get(self, request, obligation_type, obligation_id):
        from backend.api.contracts.services.proof_of_work_service import ProofOfWorkService
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return _invalid_type_response()
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        try:
            proof = ProofOfWorkService().build_for_obligation(
                obligation_type=obligation_type,
                obligation_id=obligation_id,
            )
            return Response(proof, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
