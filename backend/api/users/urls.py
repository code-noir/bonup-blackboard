# backend/api/users/urls.py

from django.urls import path
from backend.api.auth.views import EmailOrUsernameTokenView, NormalTokenRefreshView

from .views import (
    BillingInfoAPIView,
    ChangePasswordAPIView,
    InvitationAcceptAPIView,
    InvitationDetailAPIView,
    InvitationListCreateAPIView,
    LogoutAPIView,
    MeAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    PublicProfileAPIView,
    RegisterAPIView,
    ResendVerificationAPIView,
    UpdateEmailAPIView,
    UpdateLanguageAPIView,
    UpdateLocationAPIView,
    UpdatePhoneAPIView,
    UserSearchAPIView,
    VerifyEmailAPIView,
    VerifyPendingEmailAPIView,
)

urlpatterns = [
    # --------------------------------------------------
    # Auth
    # --------------------------------------------------
    path("register/", RegisterAPIView.as_view(), name="users-register"),
    path("login/", EmailOrUsernameTokenView.as_view(), name="users-login"),
    path("login/refresh/", NormalTokenRefreshView.as_view(), name="users-login-refresh"),
    path("logout/", LogoutAPIView.as_view(), name="users-logout"),
    path("password-reset/", PasswordResetRequestAPIView.as_view(), name="users-password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmAPIView.as_view(), name="users-password-reset-confirm"),
    path("verify-email/", VerifyEmailAPIView.as_view(), name="users-verify-email"),
    path("verify-pending/", VerifyPendingEmailAPIView.as_view(), name="users-verify-pending"),
    path("resend-verification/", ResendVerificationAPIView.as_view(), name="users-resend-verification"),

    # --------------------------------------------------
    # Discovery
    # --------------------------------------------------
    path("search/", UserSearchAPIView.as_view(), name="users-search"),

    # --------------------------------------------------
    # Profile — /me/ must be declared before <str:bon_id>/
    # --------------------------------------------------
    path("me/", MeAPIView.as_view(), name="users-me"),
    path("me/change-password/", ChangePasswordAPIView.as_view(), name="users-change-password"),
    path("me/update-email/", UpdateEmailAPIView.as_view(), name="users-update-email"),
    path("me/update-phone/", UpdatePhoneAPIView.as_view(), name="users-update-phone"),
    path("me/update-location/", UpdateLocationAPIView.as_view(), name="users-update-location"),
    path("me/language/", UpdateLanguageAPIView.as_view(), name="users-update-language"),
    path("me/billing/", BillingInfoAPIView.as_view(), name="users-billing"),
    path("me/invitations/", InvitationListCreateAPIView.as_view(), name="users-invitations"),

    # --------------------------------------------------
    # Invitations (public)
    # --------------------------------------------------
    path("invitations/<uuid:token>/", InvitationDetailAPIView.as_view(), name="users-invitation-detail"),
    path("invitations/<uuid:token>/accept/", InvitationAcceptAPIView.as_view(), name="users-invitation-accept"),

    # --------------------------------------------------
    # Public profile — wildcard last
    # --------------------------------------------------
    path("<str:bon_id>/", PublicProfileAPIView.as_view(), name="users-public-profile"),
]
