# backend/api/auth/views.py

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    """
    Extends the default simplejwt serializer to accept either a username
    or an email address in the username field.

    If the submitted value contains '@', we look up the corresponding
    username and swap it in before the normal validation runs.
    The rest of the JWT pipeline — password check, token generation,
    blacklist checking — is unchanged.
    """

    def validate(self, attrs):
        username_or_email = attrs.get(self.username_field, '')
        if '@' in username_or_email:
            try:
                user = User.objects.get(email=username_or_email)
                attrs[self.username_field] = user.username
            except User.DoesNotExist:
                pass  # fall through — parent validate() will produce the standard error
        return super().validate(attrs)


class EmailOrUsernameTokenView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenSerializer
