from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.operator.permissions import CanExitViewAs, CanViewAsUser, IsOperator
from backend.operator.models import OperatorAuditEvent, OperatorViewAsSession
from backend.operator.services import (
    administrator_bon_id,
    authenticate_administrator,
    can_view_as_target,
    create_audit_event,
    create_view_as_session,
    has_view_as_permission,
    impersonation_access_token,
    operator_token_pair,
)

User = get_user_model()


def _operator_payload(administrator):
    return {
        "id": administrator.pk,
        "email": administrator.email,
        "first_name": administrator.first_name,
        "last_name": administrator.last_name,
        "is_active": administrator.is_active,
        "is_super_admin": administrator.is_super_admin,
        "is_super_operator": administrator.is_super_admin,
        "is_legacy_placeholder": administrator.is_legacy_placeholder,
        "user_id": administrator.user_id,
        "bon_id": administrator_bon_id(administrator),
        "permissions": ["operator.access_operator_console"] + (
            ["operator.view_as_user"] if has_view_as_permission(administrator) else []
        ),
        "can_view_as_user": has_view_as_permission(administrator),
        "last_login_at": administrator.last_login_at,
        "created_at": administrator.created_at,
    }


def _user_summary(user):
    return {
        "id": user.pk,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
    }


class OperatorTokenView(APIView):
    throttle_scope = "operator_login"
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email") or request.data.get("username") or ""
        password = request.data.get("password") or ""
        administrator = authenticate_administrator(email=email, password=password)
        if administrator is None:
            return Response(
                {"detail": "Administrator credentials are invalid or inactive."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        administrator.last_login_at = timezone.now()
        administrator.save(update_fields=["last_login_at", "updated_at"])
        create_audit_event(
            administrator=administrator,
            action=OperatorAuditEvent.ACTION_OPERATOR_LOGIN,
            request=request,
        )
        tokens = operator_token_pair(administrator)
        return Response({**tokens, "operator": _operator_payload(administrator)})


class OperatorMeView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        return Response({"operator": _operator_payload(request.administrator)})


class OperatorViewAsStartView(APIView):
    permission_classes = [CanViewAsUser]

    def post(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        administrator = request.administrator
        allowed, reason = can_view_as_target(administrator, target)
        if not allowed:
            return Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)

        session = create_view_as_session(administrator=administrator, target_user=target, request=request)
        return Response({
            "view_as_session_id": str(session.id),
            "expires_at": session.expires_at,
            "access": impersonation_access_token(session),
            "operator": _operator_payload(administrator),
            "effective_user": _user_summary(target),
        }, status=status.HTTP_201_CREATED)


class OperatorViewAsExitView(APIView):
    permission_classes = [CanExitViewAs]

    def post(self, request):
        session = getattr(request, "impersonation_session", None)
        administrator = getattr(request, "administrator", None)
        if session is None:
            session_id = request.data.get("view_as_session_id") or request.data.get("session_id")
            if not session_id:
                return Response({"detail": "view_as_session_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                session = OperatorViewAsSession.objects.select_related("administrator", "target_user").get(pk=session_id)
            except (OperatorViewAsSession.DoesNotExist, ValueError, ValidationError, TypeError):
                return Response({"detail": "View-As session not found."}, status=status.HTTP_404_NOT_FOUND)
            if administrator is None:
                return Response({"detail": "Administrator context is required."}, status=status.HTTP_403_FORBIDDEN)
            if session.administrator_id != administrator.pk and not administrator.is_super_admin:
                return Response({"detail": "You cannot end this View-As session."}, status=status.HTTP_403_FORBIDDEN)
        else:
            administrator = session.administrator

        already_ended = session.ended_at is not None
        if not already_ended:
            session.end(reason="operator_exit")
            create_audit_event(
                administrator=session.administrator,
                target_user=session.target_user,
                view_as_session=session,
                action=OperatorAuditEvent.ACTION_VIEW_AS_ENDED,
                request=request,
                metadata={"ended_reason": "operator_exit"},
            )

        return Response({
            "view_as_session_id": str(session.id),
            "ended": True,
            "already_ended": already_ended,
        })


class OperatorLogoutView(APIView):
    permission_classes = [IsOperator]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError
        from backend.operator.services import OPERATOR_CONTEXT
        try:
            token = RefreshToken(request.data.get("refresh", ""))
            if token.get("auth_context") != OPERATOR_CONTEXT or str(token.get("administrator_id")) != str(request.administrator.pk):
                return Response({"detail": "Invalid logout token."}, status=400)
            token.blacklist()
        except (TokenError, TypeError):
            return Response({"detail": "Invalid logout token."}, status=400)
        # End outstanding View-As contexts through the same explicit audit boundary.
        for session in OperatorViewAsSession.objects.filter(administrator=request.administrator, ended_at__isnull=True):
            session.end(reason="operator_logout")
            create_audit_event(administrator=request.administrator, target_user=session.target_user,
                               view_as_session=session, action=OperatorAuditEvent.ACTION_VIEW_AS_ENDED,
                               request=request, metadata={"ended_reason": "operator_logout"})
        return Response(status=204)
