from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from backend.operator.services import OPERATOR_CONTEXT, has_view_as_permission, is_operator_eligible


class IsOperator(BasePermission):
    def has_permission(self, request, view):
        token = getattr(request, "auth", None)
        administrator = getattr(request, "administrator", None)
        return bool(
            token
            and token.get("auth_context") == OPERATOR_CONTEXT
            and is_operator_eligible(administrator)
        )


class CanViewAsUser(IsOperator):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and has_view_as_permission(getattr(request, "administrator", None))


class CanExitViewAs(BasePermission):
    def has_permission(self, request, view):
        token = getattr(request, "auth", None)
        administrator = getattr(request, "administrator", None)
        if token and token.get("auth_context") == OPERATOR_CONTEXT and is_operator_eligible(administrator):
            return True
        return bool(getattr(request, "impersonation_session", None))


def file_content_prohibited(request):
    """Only authenticated View-As context prohibits customer content access."""
    return getattr(request, "impersonation_session", None) is not None


def require_file_content_access(request):
    """Reject before opening storage, generating URLs, or producing content."""
    if file_content_prohibited(request):
        raise PermissionDenied("File content is unavailable during View-As.")
