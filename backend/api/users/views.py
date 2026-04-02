# backend/api/users/views.py

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from backend.users.models import BonUserProfile, UserBillingInfo, UserInvitation

from .serializers import (
    ChangePasswordSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UpdateEmailSerializer,
    UpdateLocationSerializer,
    UpdatePhoneSerializer,
    UserBillingInfoSerializer,
    UserInvitationSerializer,
    UserProfileSerializer,
)

User = get_user_model()
_token_generator = PasswordResetTokenGenerator()

INVITATION_TTL_DAYS = 7


# ============================================================
# AUTH
# ============================================================

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Set initial email verification token on the auto-created profile
        profile = user.bon_profile
        profile.email_verification_token = uuid.uuid4()
        profile.save(update_fields=["email_verification_token"])

        # Start free trial on the business tier
        from backend.billing.gates import start_trial
        start_trial(user)

        # In production: send verification email with the token.
        # In dev: return the token in the response so it can be used directly.
        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
                "bon_id": profile.bon_id,
                "email_verification_token": str(profile.email_verification_token),
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "refresh token required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"error": "invalid or already blacklisted token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip()
        # Always return 200 — do not reveal whether the email exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "If that email is registered, a reset link has been sent."})

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = _token_generator.make_token(user)

        # In production: send email with reset link containing uid + token.
        # In dev: return them directly.
        return Response(
            {
                "detail": "If that email is registered, a reset link has been sent.",
                "uid": uid,
                "token": token,
            }
        )


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        new_password = request.data.get("new_password", "")

        if not uid or not token or not new_password:
            return Response(
                {"error": "uid, token, and new_password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_pk)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not _token_generator.check_token(user, token):
            return Response(
                {"error": "Invalid or expired reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password has been reset."})


class VerifyEmailAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("token", "")
        if not token_str:
            return Response(
                {"error": "token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token_uuid = uuid.UUID(token_str)
        except ValueError:
            return Response(
                {"error": "Invalid token format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = BonUserProfile.objects.select_related("user").get(
                email_verification_token=token_uuid
            )
        except BonUserProfile.DoesNotExist:
            return Response(
                {"error": "Invalid or already used token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = profile.user

        if profile.pending_email:
            # Email change verification
            user.email = profile.pending_email
            user.save(update_fields=["email"])
            profile.pending_email = None

        profile.email_verified = True
        profile.email_verification_token = None
        profile.save(update_fields=["email_verified", "email_verification_token", "pending_email"])

        return Response({"detail": "Email verified."})


# ============================================================
# PROFILE
# ============================================================

class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

    def patch(self, request):
        user = request.user
        allowed_fields = {"username", "first_name", "last_name"}
        updates = {k: v for k, v in request.data.items() if k in allowed_fields}

        if not updates:
            return Response(
                {"error": "No updatable fields provided. Allowed: username, first_name, last_name."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "username" in updates:
            new_username = updates["username"]
            if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                return Response(
                    {"error": "Username already taken."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.username = new_username

        if "first_name" in updates:
            user.first_name = updates["first_name"]
        if "last_name" in updates:
            user.last_name = updates["last_name"]

        user.save()
        return Response(UserProfileSerializer(user).data)


class PublicProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, bon_id):
        try:
            profile = BonUserProfile.objects.select_related("user").get(bon_id=bon_id)
        except BonUserProfile.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(PublicUserSerializer(profile.user).data)


# ============================================================
# ACCOUNT SETTINGS
# ============================================================

class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password changed."})


class UpdateEmailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_email = serializer.validated_data["new_email"]
        profile = request.user.bon_profile
        profile.pending_email = new_email
        profile.email_verified = False
        profile.email_verification_token = uuid.uuid4()
        profile.save(update_fields=["pending_email", "email_verified", "email_verification_token"])

        # In production: send verification email to new_email.
        # In dev: return the token.
        return Response(
            {
                "detail": "Verification email sent to the new address.",
                "email_verification_token": str(profile.email_verification_token),
            }
        )


class UpdatePhoneAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdatePhoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.bon_profile
        profile.phone = serializer.validated_data["phone"] or None
        profile.save(update_fields=["phone"])
        return Response({"phone": profile.phone})


class UpdateLocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.bon_profile
        data = serializer.validated_data
        if "city" in data:
            profile.city = data["city"] or None
        if "state_region" in data:
            profile.state_region = data["state_region"] or None
        if "country" in data:
            profile.country = data["country"] or None
        profile.save(update_fields=["city", "state_region", "country"])

        return Response(
            {
                "city": profile.city,
                "state_region": profile.state_region,
                "country": profile.country,
            }
        )


class BillingInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        info, _ = UserBillingInfo.objects.get_or_create(user=request.user)
        return Response(UserBillingInfoSerializer(info).data)

    def put(self, request):
        info, _ = UserBillingInfo.objects.get_or_create(user=request.user)
        serializer = UserBillingInfoSerializer(info, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ============================================================
# DISCOVERY
# ============================================================

class UserSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response(
                {"error": "q parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profiles = (
            BonUserProfile.objects.select_related("user")
            .filter(
                models.Q(bon_id__icontains=q)
                | models.Q(user__first_name__icontains=q)
                | models.Q(user__last_name__icontains=q)
            )
            .order_by("bon_id")[:50]
        )

        results = [
            {
                "bon_id": p.bon_id,
                "first_name": p.user.first_name,
                "last_name": p.user.last_name,
            }
            for p in profiles
        ]
        return Response(results)


# ============================================================
# INVITATIONS
# ============================================================

class ResendVerificationAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip()
        if not email:
            return Response(
                {"error": "email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Always return 200 — do not reveal whether the email exists
        try:
            user = User.objects.get(email=email)
            profile = user.bon_profile
        except (User.DoesNotExist, BonUserProfile.DoesNotExist):
            return Response({"detail": "If that email is registered and unverified, a new verification link has been sent."})

        if profile.email_verified and not profile.pending_email:
            return Response({"detail": "This email is already verified."})

        profile.email_verification_token = uuid.uuid4()
        profile.save(update_fields=["email_verification_token"])

        # In production: send verification email.
        # In dev: return the token directly.
        return Response(
            {
                "detail": "If that email is registered and unverified, a new verification link has been sent.",
                "email_verification_token": str(profile.email_verification_token),
            }
        )


class InvitationAcceptAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token):
        try:
            invitation = UserInvitation.objects.get(token=token)
        except UserInvitation.DoesNotExist:
            return Response(
                {"error": "Invitation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.status == "accepted":
            return Response(
                {"error": "This invitation has already been used."},
                status=status.HTTP_410_GONE,
            )

        if invitation.expires_at < timezone.now():
            if invitation.status != "expired":
                invitation.status = "expired"
                invitation.save(update_fields=["status"])
            return Response(
                {"error": "This invitation has expired."},
                status=status.HTTP_410_GONE,
            )

        # Registration fields — pre-populate email and name from the invitation
        data = request.data.copy()
        data.setdefault("email", invitation.invitee_email)

        # Split invitee_name into first/last on the first space if the caller
        # didn't explicitly send first_name / last_name
        if "first_name" not in data and "last_name" not in data:
            parts = invitation.invitee_name.split(" ", 1)
            data["first_name"] = parts[0]
            data["last_name"] = parts[1] if len(parts) > 1 else ""

        serializer = RegisterSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        invitation.status = "accepted"
        invitation.save(update_fields=["status"])

        profile = user.bon_profile
        profile.email_verified = True  # invited email is considered pre-verified
        profile.save(update_fields=["email_verified"])

        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
                "bon_id": profile.bon_id,
            },
            status=status.HTTP_201_CREATED,
        )


class InvitationListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        invitations = UserInvitation.objects.filter(inviter=request.user).order_by("-created_at")
        return Response(UserInvitationSerializer(invitations, many=True).data)

    def post(self, request):
        serializer = UserInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expires_at = timezone.now() + timedelta(days=INVITATION_TTL_DAYS)
        invitation = UserInvitation.objects.create(
            inviter=request.user,
            invitee_email=serializer.validated_data["invitee_email"],
            invitee_name=serializer.validated_data["invitee_name"],
            expires_at=expires_at,
        )
        return Response(
            UserInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )


class InvitationDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invitation = UserInvitation.objects.select_related("inviter").get(token=token)
        except UserInvitation.DoesNotExist:
            return Response(
                {"error": "Invitation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.status == "accepted":
            return Response(
                {"error": "This invitation has already been used."},
                status=status.HTTP_410_GONE,
            )

        if invitation.expires_at < timezone.now():
            if invitation.status != "expired":
                invitation.status = "expired"
                invitation.save(update_fields=["status"])
            return Response(
                {"error": "This invitation has expired."},
                status=status.HTTP_410_GONE,
            )

        return Response(
            {
                "invitee_email": invitation.invitee_email,
                "invitee_name": invitation.invitee_name,
                "status": invitation.status,
                "expires_at": invitation.expires_at,
            }
        )
