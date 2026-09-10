from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from backend.operator.models import AdministratorAccount, OperatorAuditEvent, OperatorViewAsSession


OPERATOR_CONTEXT = "operator"
IMPERSONATION_CONTEXT = "impersonation"
VIEW_AS_LIFETIME = timedelta(minutes=30)

User = get_user_model()


def client_ip(request):
    from backend.core.throttling import client_ip as trusted_client_ip
    from ipaddress import ip_address
    try:
        return str(ip_address(trusted_client_ip(request)))
    except ValueError:
        return None


def user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:4000]


def administrator_bon_id(administrator):
    try:
        return administrator.user.bon_profile.bon_id
    except Exception:
        return None


def validate_administrator_user(user):
    if user is None:
        raise ValidationError("AdministratorAccount must be linked to an existing bonUP User.")
    if not user.is_active:
        raise ValidationError("Linked bonUP User must be active.")
    try:
        profile = user.bon_profile
    except Exception as exc:
        raise ValidationError("Linked bonUP User must have a BonUserProfile.") from exc
    if not profile.email_verified:
        raise ValidationError("Linked bonUP User email must be verified.")
    if not profile.bon_id:
        raise ValidationError("Linked bonUP User must have a bonID.")
    return profile


def validate_real_administrator_account(administrator):
    if administrator is None:
        raise ValidationError("AdministratorAccount is required.")
    if administrator.is_legacy_placeholder:
        raise ValidationError("Legacy placeholder AdministratorAccounts cannot authenticate.")
    if administrator.user_id is None:
        raise ValidationError("AdministratorAccount must be linked to a bonUP User.")
    validate_administrator_user(administrator.user)
    return administrator


def authenticate_administrator(*, email, password):
    normalized_email = (email or "").strip().lower()
    if not normalized_email or not password:
        return None
    try:
        administrator = AdministratorAccount.objects.select_related("user", "user__bon_profile").get(
            email__iexact=normalized_email
        )
    except AdministratorAccount.DoesNotExist:
        return None
    if not administrator.check_password(password):
        return None
    if not administrator.is_active:
        return None
    try:
        validate_real_administrator_account(administrator)
    except ValidationError:
        return None
    return administrator


def is_operator_eligible(administrator):
    if not administrator or not administrator.is_active:
        return False
    try:
        validate_real_administrator_account(administrator)
    except ValidationError:
        return False
    return True


def has_view_as_permission(administrator):
    return bool(
        administrator
        and administrator.is_active
        and (administrator.is_super_admin or administrator.can_view_as_user)
    )


def can_view_as_target(administrator, target_user):
    if not target_user.is_active:
        return False, "Target user is inactive."
    if target_user.is_superuser and not administrator.is_super_admin:
        return False, "Superuser accounts require super administrator View-As access."
    return True, ""


def operator_token_pair(administrator):
    refresh = RefreshToken()
    refresh["auth_context"] = OPERATOR_CONTEXT
    refresh["administrator_id"] = administrator.pk
    access = refresh.access_token
    return {"access": str(access), "refresh": str(refresh)}


def impersonation_access_token(session):
    token = AccessToken.for_user(session.target_user)
    token.set_exp(lifetime=VIEW_AS_LIFETIME)
    token["auth_context"] = IMPERSONATION_CONTEXT
    token["administrator_id"] = session.administrator_id
    token["effective_user_id"] = session.target_user_id
    token["view_as_session_id"] = str(session.id)
    return str(token)


def create_audit_event(*, administrator, action, request=None, target_user=None, view_as_session=None, metadata=None):
    return OperatorAuditEvent.objects.create(
        administrator=administrator,
        target_user=target_user,
        view_as_session=view_as_session,
        action=action,
        ip_address=client_ip(request) if request is not None else None,
        user_agent=user_agent(request) if request is not None else "",
        metadata=metadata or {},
    )


def create_view_as_session(*, administrator, target_user, request):
    expires_at = timezone.now() + VIEW_AS_LIFETIME
    session = OperatorViewAsSession.objects.create(
        administrator=administrator,
        target_user=target_user,
        expires_at=expires_at,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        metadata={"source": "operator_console"},
    )
    create_audit_event(
        administrator=administrator,
        target_user=target_user,
        view_as_session=session,
        action=OperatorAuditEvent.ACTION_VIEW_AS_STARTED,
        request=request,
        metadata={"expires_at": expires_at.isoformat()},
    )
    return session
