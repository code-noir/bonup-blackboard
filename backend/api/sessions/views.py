# backend/api/sessions/views.py

import uuid as _uuid

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import Contract, ContractVersion
from backend.sessions.models import LiveSession
from backend.sessions.token import generate_token
from backend.activity.log import log_activity
from backend.api.contracts.permissions import contract_party_response, is_party


def _serialize(session):
    return {
        "id": str(session.id),
        "contract_id": str(session.contract_id),
        "version_id": str(session.version_id) if session.version_id else None,
        "created_by_id": session.created_by_id,
        "title": session.title,
        "room_name": session.room_name,
        "status": session.status,
        "scheduled_at": session.scheduled_at,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "created_at": session.created_at,
        "livekit_host": settings.LIVEKIT_HOST,
    }


def _party_q_sessions(user):
    from django.db.models import Q
    return Q(contract__initiator=user) | Q(contract__counterparty_email=user.email)


class SessionListCreateAPIView(APIView):
    """
    GET  /api/sessions/  — list all sessions across user's contracts
    POST /api/sessions/  — create a new session

    POST body:
      contract_id    (required) UUID
      version_id     (optional) UUID — the version being negotiated
      title          (optional) string
      scheduled_at   (optional) ISO-8601 datetime
    """

    def get(self, request):
        qs = LiveSession.objects.filter(_party_q_sessions(request.user))

        contract_id = request.query_params.get("contract_id")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response([_serialize(s) for s in qs])

    def post(self, request):
        contract_id = request.data.get("contract_id")
        if not contract_id:
            return Response(
                {"error": "contract_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        version = None
        version_id = request.data.get("version_id")
        if version_id:
            version = get_object_or_404(ContractVersion, id=version_id, contract=contract)

        scheduled_at = request.data.get("scheduled_at") or None

        # Generate a stable, unique room name tied to this session UUID
        session_uuid = _uuid.uuid4()
        room_name = f"bonup-{session_uuid}"

        with transaction.atomic():
            session = LiveSession.objects.create(
                id=session_uuid,
                contract=contract,
                version=version,
                created_by=request.user,
                title=request.data.get("title", ""),
                room_name=room_name,
                scheduled_at=scheduled_at,
            )
            log_activity(
                contract=contract,
                user=request.user,
                activity_type="session_held",
                description=(
                    f"Live session scheduled"
                    + (f": {session.title}" if session.title else "")
                    + ("." if not session.title else "")
                ),
                metadata={
                    "session_id": str(session.id),
                    "room_name": room_name,
                    "version_id": str(version.id) if version else None,
                },
            )

        return Response(_serialize(session), status=status.HTTP_201_CREATED)


class SessionDetailAPIView(APIView):
    """
    GET /api/sessions/<session_id>/

    Returns session detail. Requires party membership on the linked contract.
    """

    def get(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        if not is_party(request.user, session.contract):
            return contract_party_response()
        return Response(_serialize(session))


class SessionJoinAPIView(APIView):
    """
    POST /api/sessions/<session_id>/join/

    Generates a LiveKit access token for the requesting user and returns
    the token + host URL the client needs to connect.

    If the session is still 'scheduled', it is automatically moved to 'active'.
    """

    def post(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        if not is_party(request.user, session.contract):
            return contract_party_response()

        if session.status == "ended":
            return Response(
                {"error": "This session has ended."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            if session.status == "scheduled":
                session.status = "active"
                session.started_at = timezone.now()
                session.save(update_fields=["status", "started_at", "updated_at"])

        token = generate_token(
            room_name=session.room_name,
            user_identity=str(request.user.id),
            user_display_name=request.user.username,
        )

        return Response({
            "session_id": str(session.id),
            "room_name": session.room_name,
            "livekit_host": settings.LIVEKIT_HOST,
            "token": token,
            "status": session.status,
        })


class SessionEndAPIView(APIView):
    """
    POST /api/sessions/<session_id>/end/

    Marks the session as ended and logs a PBVD activity record.
    Either party may end the session.
    """

    def post(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        if not is_party(request.user, session.contract):
            return contract_party_response()

        if session.status == "ended":
            return Response(
                {"error": "Session is already ended."},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        duration_seconds = None
        if session.started_at:
            duration_seconds = int((now - session.started_at).total_seconds())

        with transaction.atomic():
            session.status = "ended"
            session.ended_at = now
            session.save(update_fields=["status", "ended_at", "updated_at"])

            log_activity(
                contract=session.contract,
                user=request.user,
                activity_type="session_held",
                description=(
                    f"Live session ended"
                    + (f": {session.title}" if session.title else "")
                    + (f" — {duration_seconds}s" if duration_seconds is not None else "")
                    + "."
                ),
                metadata={
                    "session_id": str(session.id),
                    "room_name": session.room_name,
                    "duration_seconds": duration_seconds,
                    "version_id": str(session.version_id) if session.version_id else None,
                },
            )

        return Response(_serialize(session))


class ContractSessionListAPIView(APIView):
    """
    GET /api/contracts/<contract_id>/sessions/

    List all live sessions for a specific contract.
    Ownership enforced.
    """

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        qs = LiveSession.objects.filter(contract=contract)
        return Response([_serialize(s) for s in qs])
