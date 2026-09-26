from django.db import transaction

from backend.community.models import Community, CommunityMembership


@transaction.atomic
def create_community(*, owner, name, description=""):
    """Create a private Community together with its active owner membership."""
    community = Community.objects.create(
        owner=owner,
        name=name,
        description=description,
    )
    CommunityMembership.objects.create(
        community=community,
        user=owner,
        role=CommunityMembership.Role.OWNER,
        status=CommunityMembership.Status.ACTIVE,
    )
    return community
