# backend/api/auth/views.py

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from backend.operator.services import OPERATOR_CONTEXT

User = get_user_model()


class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    """
    Extends the default simplejwt serializer to:
    1. Accept either a username or an email address in the username field.
    2. Enforce the email-verification gate: sign-in is blocked for any account
       whose BonUserProfile.email_verified is False.

    Admin/superuser accounts that have no BonUserProfile are exempt — they
    are considered verified by definition (created outside the signup flow).
    """

    def validate(self, attrs):
        username_or_email = attrs.get(self.username_field, '')
        if '@' in username_or_email:
            try:
                user = User.objects.get(email=username_or_email)
                attrs[self.username_field] = user.username
            except User.DoesNotExist:
                pass  # fall through — parent validate() will produce the standard error

        data = super().validate(attrs)  # sets self.user; raises AuthenticationFailed on bad creds

        # Email-verification gate.
        # self.user is the authenticated User object set by the parent validate().
        try:
            email_verified = self.user.bon_profile.email_verified
        except Exception:
            email_verified = True  # no BonUserProfile → admin/superuser → allow

        if not email_verified:
            raise AuthenticationFailed(
                "Email address not verified. "
                "Check your email "
                "for the verification link."
            )

        return data


class EmailOrUsernameTokenView(TokenObtainPairView):
    throttle_scope = "login"
    serializer_class = EmailOrUsernameTokenSerializer


class ContextTokenRefreshSerializer(TokenRefreshSerializer):
    required_auth_context = None

    def validate(self, attrs):
        token = self.token_class(attrs["refresh"])
        auth_context = token.get("auth_context")
        if self.required_auth_context is None and auth_context is not None:
            raise InvalidToken("Refresh token is not valid for this endpoint.")
        if self.required_auth_context is not None and auth_context != self.required_auth_context:
            raise InvalidToken("Refresh token is not valid for this endpoint.")
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            raise InvalidToken("Refresh token is unavailable.") from None


class NormalTokenRefreshSerializer(ContextTokenRefreshSerializer):
    required_auth_context = None


class OperatorTokenRefreshSerializer(ContextTokenRefreshSerializer):
    required_auth_context = OPERATOR_CONTEXT

    def validate(self, attrs):
        data = super().validate(attrs)
        token = self.token_class(attrs["refresh"])
        administrator_id = token.get("administrator_id")
        if not administrator_id:
            raise InvalidToken("Refresh token is not valid for this endpoint.")
        from backend.operator.models import AdministratorAccount
        try:
            administrator = AdministratorAccount.objects.get(pk=administrator_id)
        except AdministratorAccount.DoesNotExist as exc:
            raise InvalidToken("Administrator account no longer exists.") from exc
        if not administrator.is_active:
            raise InvalidToken("Administrator account is inactive.")
        return data


class NormalTokenRefreshView(TokenRefreshView):
    throttle_scope = "refresh"
    serializer_class = NormalTokenRefreshSerializer


class OperatorTokenRefreshView(TokenRefreshView):
    throttle_scope = "refresh"
    serializer_class = OperatorTokenRefreshSerializer
