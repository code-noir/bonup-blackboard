# backend/api/contracts/execution_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.serializers import (
    AutoApprovalRequestSerializer,
    CloseExecutionSessionSerializer,
    ExecutionDecisionSerializer,
    ObligationExecutionEventSerializer,
    ObligationExecutionSessionSerializer,
    OpenExecutionSessionSerializer,
    RecordExecutionItemSerializer,
)
from backend.api.contracts.services.obligation_execution_service import (
    ObligationExecutionService,
)
from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
    ObligationExecutionEvent,
    ObligationExecutionSession,
)
from .permissions import contract_party_response, get_contract_for_object, is_party


def _get_obligation_or_404(obligation_type, obligation_id):
    """Look up a payment or service obligation by type + id."""
    if obligation_type == "payment":
        return get_object_or_404(ContractObligation, id=obligation_id)
    if obligation_type == "service":
        return get_object_or_404(ContractServiceObligation, id=obligation_id)
    return None


class ObligationExecutionSessionListCreateAPIView(APIView):
    """
    GET  /api/contracts/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationExecutionService()

    def get(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return Response(
                {"error": "Invalid obligation type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        sessions = obligation.execution_sessions.all().order_by("started_at")
        payload = [
            {
                "id": s.id,
                "status": s.status,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
            }
            for s in sessions
        ]
        return Response(
            ObligationExecutionSessionSerializer(payload, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, obligation_type, obligation_id):
        obligation = _get_obligation_or_404(obligation_type, obligation_id)
        if obligation is None:
            return Response(
                {"error": "Invalid obligation type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        serializer = OpenExecutionSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = self.service.open_session(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
            started_at=serializer.validated_data.get("started_at"),
        )

        return Response(
            ObligationExecutionSessionSerializer({
                "id": session.id,
                "status": session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            }).data,
            status=status.HTTP_201_CREATED,
        )


class ExecutionItemCreateAPIView(APIView):
    """
    POST /api/contracts/execution-sessions/<session_id>/execution-items/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationExecutionService()

    def post(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)
        contract = get_contract_for_object(session)
        if not is_party(request.user, contract):
            return contract_party_response()

        serializer = RecordExecutionItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = self.service.record_execution_item(
            session=session,
            task=serializer.validated_data["task"],
            observation=serializer.validated_data["observation"],
            summary=serializer.validated_data["summary"],
            estimated_duration_minutes=serializer.validated_data["estimated_duration_minutes"],
            estimated_cost_amount=serializer.validated_data["estimated_cost_amount"],
            estimated_cost_currency=serializer.validated_data["estimated_cost_currency"],
            planned_execution_time=serializer.validated_data.get("planned_execution_time"),
            metadata=serializer.validated_data.get("metadata"),
        )

        event = result["event"]
        decision = result["decision"]
        approval_request = result["approval_request"]

        event_payload = {
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

        decision_payload = {
            "decision_status": decision.decision_status,
            "authorization_mode": decision.authorization_mode,
            "billing_mode": decision.billing_mode,
            "promotion_suggestion": decision.promotion_suggestion,
            "required_next_step": decision.required_next_step,
            "rationale": decision.rationale,
            "proof_tags": decision.proof_tags,
        }

        approval_payload = None
        if approval_request is not None:
            approval_payload = {
                "id": approval_request.id,
                "approval_type": approval_request.approval_type,
                "status": approval_request.status,
                "summary": approval_request.summary,
                "metadata": approval_request.metadata,
                "requested_at": approval_request.requested_at,
                "decided_at": approval_request.decided_at,
                "execution_event_id": approval_request.execution_event_id,
                "payment_obligation_id": approval_request.payment_obligation_id,
                "service_obligation_id": approval_request.service_obligation_id,
            }

        return Response(
            {
                "event": ObligationExecutionEventSerializer(event_payload).data,
                "decision": ExecutionDecisionSerializer(decision_payload).data,
                "approval_request": (
                    AutoApprovalRequestSerializer(approval_payload).data
                    if approval_payload is not None
                    else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ExecutionSessionEventListAPIView(APIView):
    """
    GET /api/contracts/execution-sessions/<session_id>/events/
    """

    def get(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)
        contract = get_contract_for_object(session)
        if not is_party(request.user, contract):
            return contract_party_response()

        events = session.events.all().order_by("created_at")
        payload = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "task": e.task,
                "observation": e.observation,
                "summary": e.summary,
                "estimated_duration_minutes": e.estimated_duration_minutes,
                "estimated_cost_amount": e.estimated_cost_amount,
                "estimated_cost_currency": e.estimated_cost_currency,
                "planned_execution_time": e.planned_execution_time,
                "metadata": e.metadata,
                "created_at": e.created_at,
            }
            for e in events
        ]
        return Response(
            ObligationExecutionEventSerializer(payload, many=True).data,
            status=status.HTTP_200_OK,
        )


class ExecutionSessionCloseAPIView(APIView):
    """
    POST /api/contracts/execution-sessions/<session_id>/close/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationExecutionService()

    def post(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)
        contract = get_contract_for_object(session)
        if not is_party(request.user, contract):
            return contract_party_response()

        serializer = CloseExecutionSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        closed_session = self.service.close_session(
            session=session,
            ended_at=serializer.validated_data.get("ended_at"),
        )

        return Response(
            ObligationExecutionSessionSerializer({
                "id": closed_session.id,
                "status": closed_session.status,
                "started_at": closed_session.started_at,
                "ended_at": closed_session.ended_at,
            }).data,
            status=status.HTTP_200_OK,
        )


class ExecutionSessionDetailAPIView(APIView):
    """
    GET /api/contracts/execution-sessions/<session_id>/
    """

    def get(self, request, session_id):
        session = get_object_or_404(ObligationExecutionSession, id=session_id)
        contract = get_contract_for_object(session)
        if not is_party(request.user, contract):
            return contract_party_response()

        return Response(
            ObligationExecutionSessionSerializer({
                "id": session.id,
                "status": session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            }).data,
            status=status.HTTP_200_OK,
        )


class ExecutionEventDetailAPIView(APIView):
    """
    GET /api/contracts/execution-events/<event_id>/
    """

    def get(self, request, event_id):
        event = get_object_or_404(ObligationExecutionEvent, id=event_id)
        contract = get_contract_for_object(event)
        if not is_party(request.user, contract):
            return contract_party_response()

        return Response(
            ObligationExecutionEventSerializer({
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
            }).data,
            status=status.HTTP_200_OK,
        )


class ExecutionEventDeleteAPIView(APIView):
    """
    DELETE /api/contracts/execution-events/<event_id>/delete/
    """

    def delete(self, request, event_id):
        event = get_object_or_404(ObligationExecutionEvent, id=event_id)
        contract = get_contract_for_object(event)
        if not is_party(request.user, contract):
            return contract_party_response()

        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
