#backend/api/contracts/execution_views.py
from backend.api.contracts.serializers import (
    OpenExecutionSessionSerializer,
    ObligationExecutionSessionSerializer,
    RecordExecutionItemSerializer,
    ExecutionDecisionSerializer,
    ObligationExecutionEventSerializer,
    CloseExecutionSessionSerializer,
    AutoApprovalRequestSerializer,
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
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class ObligationExecutionSessionListCreateAPIView(APIView):
    """
    GET  /api/contracts/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    POST /api/contracts/obligations/<obligation_type>/<obligation_id>/execution-sessions/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationExecutionService()

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

        session = self.service.open_session(
            obligation_type=obligation_type,
            obligation_id=obligation_id,
            started_at=serializer.validated_data.get("started_at"),
        )

        response_serializer = ObligationExecutionSessionSerializer(
            {
                "id": session.id,
                "status": session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            }
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def _get_obligation(self, *, obligation_type, obligation_id):
        if obligation_type == "payment":
            return ContractObligation.objects.get(id=obligation_id)

        if obligation_type == "service":
            return ContractServiceObligation.objects.get(id=obligation_id)

        raise Exception("Invalid obligation type")


class ExecutionItemCreateAPIView(APIView):
    """
    POST /api/contracts/execution-sessions/<session_id>/execution-items/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationExecutionService()

    def post(self, request, session_id):
        serializer = RecordExecutionItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = ObligationExecutionSession.objects.get(id=session_id)

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

        response_data = {
            "event": ObligationExecutionEventSerializer(event_payload).data,
            "decision": ExecutionDecisionSerializer(decision_payload).data,
            "approval_request": (
                AutoApprovalRequestSerializer(approval_payload).data
                if approval_payload is not None
                else None
            ),
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class ExecutionSessionEventListAPIView(APIView):
    """
    GET /api/contracts/execution-sessions/<session_id>/events/
    """

    def get(self, request, session_id):
        session = ObligationExecutionSession.objects.get(id=session_id)
        events = session.events.all().order_by("created_at")

        payload = [
            {
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
            for event in events
        ]

        serializer = ObligationExecutionEventSerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ExecutionSessionCloseAPIView(APIView):
    """
    POST /api/contracts/execution-sessions/<session_id>/close/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationExecutionService()

    def post(self, request, session_id):
        serializer = CloseExecutionSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = ObligationExecutionSession.objects.get(id=session_id)
        closed_session = self.service.close_session(
            session=session,
            ended_at=serializer.validated_data.get("ended_at"),
        )

        response_serializer = ObligationExecutionSessionSerializer(
            {
                "id": closed_session.id,
                "status": closed_session.status,
                "started_at": closed_session.started_at,
                "ended_at": closed_session.ended_at,
            }
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ExecutionSessionDetailAPIView(APIView):
    """
    GET /api/contracts/execution-sessions/<session_id>/
    """

    def get(self, request, session_id):
        try:
            session = ObligationExecutionSession.objects.get(id=session_id)
        except ObligationExecutionSession.DoesNotExist:
            return Response(
                {"error": "Execution session not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
        }

        serializer = ObligationExecutionSessionSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)




class ExecutionEventDetailAPIView(APIView):
    """
    GET /api/contracts/execution-events/<event_id>/
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

class ExecutionEventDeleteAPIView(APIView):
    """
    DELETE /api/contracts/execution-events/<event_id>/delete/
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


class ExecutionEventDeleteAPIView(APIView):
    """
    DELETE /api/contracts/execution-events/<event_id>/delete/
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