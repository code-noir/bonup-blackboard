from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from backend.community.models import Community, CommunityJoinRequest, CommunityMembership, Friendship


class CommunityCreationError(ValueError):
    pass


class FriendshipError(ValueError):
    pass


class JoinRequestError(ValueError):
    pass


def accepted_friend_count(user):
    return Friendship.objects.filter(
        status=Friendship.Status.ACCEPTED,
    ).filter(Q(user_a=user) | Q(user_b=user)).count()


@transaction.atomic
def create_community(*, owner, name, description=""):
    """Create a private Community together with its active owner membership."""
    if accepted_friend_count(owner) < 1:
        raise CommunityCreationError(
            "You need at least one accepted friend before creating a Community."
        )

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


def _ordered_pair(first, second):
    if first.pk == second.pk:
        raise FriendshipError("You cannot send a friend request to yourself.")
    return (first, second) if first.pk < second.pk else (second, first)


@transaction.atomic
def send_friend_request(*, requester, recipient):
    user_a, user_b = _ordered_pair(requester, recipient)
    relationship = (
        Friendship.objects.select_for_update()
        .filter(user_a=user_a, user_b=user_b)
        .first()
    )

    if relationship is None:
        return Friendship.objects.create(
            user_a=user_a,
            user_b=user_b,
            requester=requester,
            recipient=recipient,
            status=Friendship.Status.PENDING,
        ), True

    if relationship.status == Friendship.Status.ACCEPTED:
        raise FriendshipError("You are already friends.")

    if relationship.status == Friendship.Status.PENDING:
        return relationship, False

    relationship.requester = requester
    relationship.recipient = recipient
    relationship.status = Friendship.Status.PENDING
    relationship.responded_at = None
    relationship.save(update_fields=["requester", "recipient", "status", "responded_at", "updated_at"])
    return relationship, True


@transaction.atomic
def respond_to_friend_request(*, friendship_id, recipient, accept):
    relationship = Friendship.objects.select_for_update().get(pk=friendship_id)
    if relationship.recipient_id != recipient.pk:
        raise FriendshipError("Only the request recipient can respond to this request.")
    if relationship.status != Friendship.Status.PENDING:
        raise FriendshipError("This friend request is already closed.")

    relationship.status = Friendship.Status.ACCEPTED if accept else Friendship.Status.DECLINED
    relationship.responded_at = timezone.now()
    relationship.save(update_fields=["status", "responded_at", "updated_at"])
    return relationship


@transaction.atomic
def request_to_join(*, community, user):
    membership = CommunityMembership.objects.filter(community=community, user=user).first()
    if membership and membership.status == CommunityMembership.Status.ACTIVE:
        raise JoinRequestError("You are already a member of this Community.")

    existing = (
        CommunityJoinRequest.objects.select_for_update()
        .filter(
            community=community,
            user=user,
            status=CommunityJoinRequest.Status.PENDING,
        )
        .first()
    )
    if existing:
        return existing, False

    return CommunityJoinRequest.objects.create(community=community, user=user), True


@transaction.atomic
def review_join_request(*, request_id, reviewer, approve):
    join_request = CommunityJoinRequest.objects.select_for_update().select_related("community").get(
        pk=request_id
    )
    membership = CommunityMembership.objects.select_for_update().filter(
        community=join_request.community,
        user=reviewer,
        status=CommunityMembership.Status.ACTIVE,
        role__in=[CommunityMembership.Role.OWNER, CommunityMembership.Role.ADMIN],
    ).first()
    if membership is None:
        raise JoinRequestError("Only a Community owner or admin can review join requests.")
    if join_request.status != CommunityJoinRequest.Status.PENDING:
        raise JoinRequestError("This join request is already closed.")

    join_request.status = (
        CommunityJoinRequest.Status.APPROVED
        if approve
        else CommunityJoinRequest.Status.DECLINED
    )
    join_request.reviewed_by = reviewer
    join_request.reviewed_at = timezone.now()
    join_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

    if approve:
        target_membership = CommunityMembership.objects.select_for_update().filter(
            community=join_request.community,
            user=join_request.user,
        ).first()
        if target_membership:
            target_membership.status = CommunityMembership.Status.ACTIVE
            target_membership.role = CommunityMembership.Role.MEMBER
            target_membership.removed_at = None
            target_membership.save(update_fields=["status", "role", "removed_at", "updated_at"])
        else:
            CommunityMembership.objects.create(
                community=join_request.community,
                user=join_request.user,
                role=CommunityMembership.Role.MEMBER,
                status=CommunityMembership.Status.ACTIVE,
            )

    return join_request
