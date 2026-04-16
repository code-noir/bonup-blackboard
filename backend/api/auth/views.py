# backend/api/auth/views.py

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

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
                "Check your email (or the server terminal in development) "
                "for the verification link."
            )

        return data


class EmailOrUsernameTokenView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenSerializer
