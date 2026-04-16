# backend/api/users/views.py

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from backend.users.models import BonUserProfile, PendingSignup, UserBillingInfo, UserInvitation

from .serializers import (
    ChangePasswordSerializer,
    PendingSignupSerializer,
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
# EMAIL HELPERS
# ============================================================

def _send_verification_email(email: str, token) -> None:
    """
    Send the signup email-verification message.

    In dev (EMAIL_BACKEND = console.EmailBackend) this prints the full email —
    including the clickable verification link — to the Django server terminal.
    In production, swap EMAIL_BACKEND for a real SMTP or SES backend and set
    FRONTEND_URL to the live domain; no code changes needed.
    """
    from django.conf import settings
    from django.core.mail import send_mail

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
    verification_url = f"{frontend_url}/verify-email?token={token}"

    send_mail(
        subject="Verify your bonUP email address",
        message=(
            "Hi,\n\n"
            "Click the link below to verify your email address and complete "
            "your bonUP account setup:\n\n"
            f"{verification_url}\n\n"
            "This link expires in 24 hours.\n\n"
            "If you did not sign up for bonUP, you can safely ignore this email.\n\n"
            "— The bonUP team"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


# ============================================================
# AUTH
# ============================================================

class RegisterAPIView(APIView):
    """
    Stage 1 of signup: validate form data and create a PendingSignup record.

    NO User, BonUserProfile, or bonID is created here.
    NO Blackboard subscription is assigned.

    The real account is created only after the user verifies their email via
    VerifyPendingEmailAPIView (POST /users/verify-pending/).

    DUPLICATE PENDING HANDLING
    --------------------------
    If a PendingSignup already exists for the submitted email, this endpoint
    returns 409 Conflict with {"pending_verification": true, "email": ...}
    instead of a field validation error.  This gives the frontend a clean,
    detectable signal to show a "Resend verification email" CTA rather than
    a generic error the user cannot act on.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        # Preempt serializer validation: if a PendingSignup already exists for
        # this email, return a structured 409 so the frontend can offer resend.
        email_raw = (request.data.get("email") or "").strip()
        if email_raw and PendingSignup.objects.filter(email__iexact=email_raw).exists():
            return Response(
                {
                    "pending_verification": True,
                    "email": email_raw,
                    "detail": "A verification email was already sent to this address.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        serializer = PendingSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pending = serializer.save()

        # Send (or print, in dev) the verification email.
        # Console backend prints the full message — including the verification
        # link — to the Django terminal so local dev is never blocked.
        _send_verification_email(pending.email, pending.token)

        return Response(
            {"detail": "Account pending. Check your email to verify and complete signup."},
            status=status.HTTP_201_CREATED,
        )


class VerifyPendingEmailAPIView(APIView):
    """
    Stage 2 of signup: consume the verification token, create the real account.

    On success:
      - User is created (triggers post_save signal → BonUserProfile + bonID)
      - email_verified is set to True on the profile
      - PendingSignup record is deleted
      - Returns 200 with "sign in now" message; does NOT issue JWT tokens

    The caller (frontend) must redirect the user to the sign-in page.
    Auto-login after verification is intentionally not supported.
    """

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
            pending = PendingSignup.objects.get(token=token_uuid)
        except PendingSignup.DoesNotExist:
            return Response(
                {"error": "Invalid or already used verification link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if pending.expires_at < timezone.now():
            pending.delete()
            return Response(
                {"error": "Verification link has expired. Please sign up again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guard against race: another request already created this account
        if User.objects.filter(email=pending.email).exists():
            pending.delete()
            return Response(
                {"error": "An account with this email already exists. Please sign in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Create User — password_hash is already hashed; bypass create_user()
            # so it isn't double-hashed.
            user = User(
                username=pending.email,
                email=pending.email,
                first_name=pending.first_name,
                last_name=pending.last_name,
                password=pending.password_hash,
                is_active=True,
            )
            user.save()  # triggers post_save → BonUserProfile creation + bonID assignment

            # Mark email as verified immediately (the link IS the verification)
            profile = user.bon_profile
            profile.email_verified = True
            profile.save(update_fields=["email_verified"])

            pending.delete()

        return Response({"detail": "Email verified. You can now sign in."})


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
        allowed_fields = {"first_name", "last_name"}
        updates = {k: v for k, v in request.data.items() if k in allowed_fields}

        if not updates:
            return Response(
                {"error": "No updatable fields provided. Allowed: first_name, last_name."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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


class UpdateLanguageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    VALID_LANGUAGES = [code for code, _ in BonUserProfile.LANGUAGE_CHOICES]

    def post(self, request):
        lang = (request.data.get("language") or "").strip()
        if lang not in self.VALID_LANGUAGES:
            return Response(
                {"error": f"Invalid language. Choices: {', '.join(self.VALID_LANGUAGES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile = request.user.bon_profile
        profile.language = lang
        profile.save(update_fields=["language"])
        return Response({"language": lang})


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

        # Check PendingSignup first — handles the initial signup verification case
        try:
            pending = PendingSignup.objects.get(email=email)
            pending.token = uuid.uuid4()
            pending.expires_at = timezone.now() + timedelta(hours=PendingSignup.EXPIRY_HOURS)
            pending.save(update_fields=["token", "expires_at"])
            _send_verification_email(pending.email, pending.token)
            return Response(
                {"detail": "If that email is awaiting verification, a new link has been sent."}
            )
        except PendingSignup.DoesNotExist:
            pass

        # Fall through: email-change verification for an existing verified user
        try:
            user = User.objects.get(email=email)
            profile = user.bon_profile
        except (User.DoesNotExist, BonUserProfile.DoesNotExist):
            return Response({"detail": "If that email is registered and unverified, a new verification link has been sent."})

        if profile.email_verified and not profile.pending_email:
            return Response({"detail": "This email is already verified."})

        profile.email_verification_token = uuid.uuid4()
        profile.save(update_fields=["email_verification_token"])
        return Response(
            {"detail": "If that email is registered and unverified, a new verification link has been sent."}
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
