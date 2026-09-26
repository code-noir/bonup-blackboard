from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from backend.community.models import Community, CommunityMembership


def get_active_membership(user, community_id):
    """Return the user's active membership, or None without granting access."""
    if not getattr(user, "is_authenticated", False):
        return None

    return (
        CommunityMembership.objects.select_related("community")
        .filter(
            community_id=community_id,
            user=user,
            status=CommunityMembership.Status.ACTIVE,
        )
        .first()
    )


def require_community_member(user, community_id):
    """Require active membership while closing private-community existence."""
    membership = get_active_membership(user, community_id)
    if membership is None:
        raise Http404("Community not found.")
    return membership


def require_community_role(user, community_id, roles):
    """Require active membership with one of the supplied Community roles."""
    membership = require_community_member(user, community_id)
    allowed_roles = {roles} if isinstance(roles, str) else set(roles)
    if membership.role not in allowed_roles:
        raise PermissionDenied("Insufficient Community role.")
    return membership


def community_resource_or_404(resource_id, community_id, *, resource_model=Community):
    """Resolve a Community or Community-owned resource within its Community.

    Callers must perform membership authorization separately. For future
    Community-owned models, pass a model with a ``community_id`` field.
    """
    if resource_model is Community:
        if str(resource_id) != str(community_id):
            raise Http404("Community resource not found.")
        return get_object_or_404(Community, pk=resource_id)

    return get_object_or_404(
        resource_model,
        pk=resource_id,
        community_id=community_id,
    )
