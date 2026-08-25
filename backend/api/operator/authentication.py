from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from backend.operator.models import AdministratorAccount, OperatorViewAsSession
from backend.operator.services import IMPERSONATION_CONTEXT, OPERATOR_CONTEXT

User = get_user_model()


class BlackboardJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        auth_context = validated_token.get("auth_context")
        if auth_context == IMPERSONATION_CONTEXT:
            return self._authenticate_impersonation(request, validated_token)
        if auth_context == OPERATOR_CONTEXT:
            return self._authenticate_administrator(request, validated_token)

        user = self.get_user(validated_token)
        request.administrator = None
        request.operator_user = None
        request.impersonation_session = None
        return user, validated_token

    def _authenticate_administrator(self, request, validated_token):
        administrator_id = validated_token.get("administrator_id")
        if not administrator_id:
            raise AuthenticationFailed("Invalid administrator token.")
        try:
            administrator = AdministratorAccount.objects.get(pk=administrator_id)
        except AdministratorAccount.DoesNotExist as exc:
            raise AuthenticationFailed("Administrator account not found.") from exc
        if not administrator.is_active:
            raise AuthenticationFailed("Administrator account is inactive.")

        request.administrator = administrator
        request.operator_user = None
        request.impersonation_session = None
        return AnonymousUser(), validated_token

    def _authenticate_impersonation(self, request, validated_token):
        session_id = validated_token.get("view_as_session_id")
        administrator_id = validated_token.get("administrator_id")
        effective_user_id = validated_token.get("effective_user_id")
        if not session_id or not administrator_id or not effective_user_id:
            raise AuthenticationFailed("Invalid View-As token.")

        try:
            session = (
                OperatorViewAsSession.objects
                .select_related("administrator", "target_user")
                .get(pk=session_id)
            )
        except OperatorViewAsSession.DoesNotExist as exc:
            raise AuthenticationFailed("View-As session not found.") from exc

        if not session.is_active:
            raise AuthenticationFailed("View-As session is not active.")
        if session.administrator_id != int(administrator_id) or session.target_user_id != int(effective_user_id):
            raise AuthenticationFailed("View-As token does not match its session.")
        if not session.administrator.is_active or not session.target_user.is_active:
            raise AuthenticationFailed("View-As session account is inactive.")

        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.path != "/api/operator/view-as/exit/":
            raise PermissionDenied("View-As is read-only. Exit User View to make changes.")

        request.administrator = session.administrator
        request.operator_user = None
        request.impersonation_session = session
        return session.target_user, validated_token
