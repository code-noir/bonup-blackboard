from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.community.serializers import (
    CommunityMemberSerializer,
    CommunityCreateSerializer,
    CommunitySerializer,
    CommunityUpdateSerializer,
)
from backend.users.models import BonUserProfile
from backend.community.models import Community, CommunityJoinRequest, CommunityMembership, Friendship
from backend.community.permissions import (
    community_resource_or_404,
    require_community_member,
    require_community_role,
)
from backend.community.services import (
    CommunityCreationError,
    FriendshipError,
    JoinRequestError,
    create_community,
    request_to_join,
    respond_to_friend_request,
    review_join_request,
    send_friend_request,
)
from backend.api.community.serializers import CommunityJoinRequestSerializer
from backend.users.profile_photo import profile_photo_url

User = get_user_model()

def _person_payload(user):
    try:
        profile = user.bon_profile
        bon_id = profile.bon_id
        photo_url = profile_photo_url(profile)
    except BonUserProfile.DoesNotExist:
        bon_id = None
        photo_url = None
    return {
        "user_id": user.pk,
        "bon_id": bon_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": " ".join(filter(None, [user.first_name, user.last_name])) or user.username,
        "profile_photo_url": photo_url,
    }


def _friendship_for(user, other):
    if user.pk == other.pk:
        return None
    first, second = sorted([user.pk, other.pk])
    return Friendship.objects.filter(user_a_id=first, user_b_id=second).first()


def _friendship_payload(relationship, viewer):
    other = relationship.user_b if relationship.user_a_id == viewer.pk else relationship.user_a
    payload = _person_payload(other)
    payload.update({
        "id": str(relationship.id),
        "status": relationship.status,
        "requester_id": relationship.requester_id,
        "recipient_id": relationship.recipient_id,
    })
    return payload


def _community_profile_payload(community, viewer):
    active_members = list(
        CommunityMembership.objects.select_related("user", "user__bon_profile")
        .filter(community=community, status=CommunityMembership.Status.ACTIVE)
        .order_by("created_at")[:6]
    )
    member_count = CommunityMembership.objects.filter(
        community=community,
        status=CommunityMembership.Status.ACTIVE,
    ).count()
    membership = CommunityMembership.objects.filter(community=community, user=viewer).first()
    pending_request = CommunityJoinRequest.objects.filter(
        community=community,
        user=viewer,
        status=CommunityJoinRequest.Status.PENDING,
    ).first()
    owner = community.owner
    return {
        "id": str(community.id),
        "name": community.name,
        "description": community.description,
        "is_private": community.is_private,
        "member_count": member_count,
        "members_preview": [_person_payload(member.user) for member in active_members],
        "owner": _person_payload(owner),
        "membership_status": (
            "member" if membership and membership.status == CommunityMembership.Status.ACTIVE
            else "removed" if membership else "not_member"
        ),
        "membership_role": membership.role if membership and membership.status == CommunityMembership.Status.ACTIVE else None,
        "join_request_status": pending_request.status if pending_request else None,
        "can_request_join": not membership or membership.status == CommunityMembership.Status.REMOVED,
        "can_manage_join_requests": bool(
            membership
            and membership.status == CommunityMembership.Status.ACTIVE
            and membership.role in [CommunityMembership.Role.OWNER, CommunityMembership.Role.ADMIN]
        ),
        "created_at": community.created_at,
    }


class CommunityListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        communities = (
            Community.objects.filter(
                memberships__user=request.user,
                memberships__status=CommunityMembership.Status.ACTIVE,
            )
            .select_related("owner")
            .distinct()
        )
        serializer = CommunitySerializer(communities, many=True)
        return Response({"count": communities.count(), "results": serializer.data})

    def post(self, request):
        serializer = CommunityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            community = create_community(owner=request.user, **serializer.validated_data)
        except CommunityCreationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            CommunitySerializer(community).data,
            status=status.HTTP_201_CREATED,
        )


class CommunityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        require_community_member(request.user, community_id)
        community = community_resource_or_404(community_id, community_id)
        return Response(CommunitySerializer(community).data)

    def patch(self, request, community_id):
        require_community_role(request.user, community_id, CommunityMembership.Role.OWNER)
        community = community_resource_or_404(community_id, community_id)
        serializer = CommunityUpdateSerializer(community, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CommunitySerializer(community).data)


class CommunityMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        current_membership = require_community_member(request.user, community_id)
        community = get_object_or_404(Community, pk=community_id)
        members = CommunityMembership.objects.select_related(
            "user", "user__bon_profile",
        ).filter(
            community=community,
            status=CommunityMembership.Status.ACTIVE,
        )
        member_payload = []
        for membership in members:
            person = _person_payload(membership.user)
            person.update({
                "role": membership.role,
                "joined_at": membership.joined_at,
            })
            member_payload.append(person)
        return Response({
            "id": str(community.id),
            "name": community.name,
            "description": community.description,
            "is_private": community.is_private,
            "is_discoverable": community.is_discoverable,
            "member_count": len(member_payload),
            "current_member_role": current_membership.role,
            "members": CommunityMemberSerializer(member_payload, many=True).data,
        })


class CommunityDiscoverView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        communities = Community.objects.filter(is_discoverable=True)
        if query:
            communities = communities.filter(Q(name__icontains=query) | Q(description__icontains=query))
        communities = communities.order_by("-created_at")[:24]
        return Response({
            "count": len(communities),
            "results": [_community_profile_payload(community, request.user) for community in communities],
        })


class CommunityProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        community = get_object_or_404(
            Community,
            pk=community_id,
            is_discoverable=True,
        )
        return Response(_community_profile_payload(community, request.user))


class CommunityJoinRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id):
        community = get_object_or_404(Community, pk=community_id, is_discoverable=True)
        try:
            join_request, created = request_to_join(community=community, user=request.user)
        except JoinRequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            CommunityJoinRequestSerializer(join_request).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CommunityJoinRequestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        managed_communities = CommunityMembership.objects.filter(
            user=request.user,
            status=CommunityMembership.Status.ACTIVE,
            role__in=[CommunityMembership.Role.OWNER, CommunityMembership.Role.ADMIN],
        ).values_list("community_id", flat=True)
        incoming = CommunityJoinRequest.objects.select_related("community", "user", "reviewed_by").filter(
            community_id__in=managed_communities,
        )
        outgoing = CommunityJoinRequest.objects.select_related("community", "user", "reviewed_by").filter(
            user=request.user,
        )
        return Response({
            "incoming": CommunityJoinRequestSerializer(incoming, many=True).data,
            "outgoing": CommunityJoinRequestSerializer(outgoing, many=True).data,
        })


class CommunityJoinRequestDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id, decision):
        if decision not in {"approve", "decline"}:
            return Response({"detail": "Unknown join-request decision."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            join_request = review_join_request(
                request_id=request_id,
                reviewer=request.user,
                approve=decision == "approve",
            )
        except CommunityJoinRequest.DoesNotExist:
            return Response({"detail": "Join request not found."}, status=status.HTTP_404_NOT_FOUND)
        except JoinRequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommunityJoinRequestSerializer(join_request).data)


class PeopleSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"count": 0, "results": []})
        profiles = BonUserProfile.objects.select_related("user").filter(
            user__is_active=True,
        ).filter(
            Q(bon_id__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
        ).exclude(user=request.user).order_by("bon_id")[:24]
        results = []
        for profile in profiles:
            payload = _person_payload(profile.user)
            relationship = _friendship_for(request.user, profile.user)
            payload["relationship_status"] = (
                "none" if relationship is None
                else relationship.status if relationship.status == Friendship.Status.ACCEPTED
                else "pending_outgoing" if relationship.requester_id == request.user.pk
                else "pending_incoming" if relationship.status == Friendship.Status.PENDING
                else relationship.status
            )
            results.append(payload)
        return Response({"count": len(results), "results": results})


class FriendListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        relationships = Friendship.objects.select_related(
            "user_a", "user_b",
        ).filter(Q(user_a=request.user) | Q(user_b=request.user))
        accepted = relationships.filter(status=Friendship.Status.ACCEPTED)
        incoming = relationships.filter(status=Friendship.Status.PENDING, recipient=request.user)
        outgoing = relationships.filter(status=Friendship.Status.PENDING, requester=request.user)
        return Response({
            "friends": [_friendship_payload(item, request.user) for item in accepted],
            "incoming_requests": [_friendship_payload(item, request.user) for item in incoming],
            "outgoing_requests": [_friendship_payload(item, request.user) for item in outgoing],
        })

    def post(self, request):
        bon_id = (request.data.get("bon_id") or "").strip()
        try:
            recipient = BonUserProfile.objects.select_related("user").get(
                bon_id=bon_id,
                user__is_active=True,
            ).user
        except BonUserProfile.DoesNotExist:
            return Response({"detail": "That bonID could not be found."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            relationship, created = send_friend_request(requester=request.user, recipient=recipient)
        except FriendshipError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            _friendship_payload(relationship, request.user),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class FriendRequestDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id, decision):
        if decision not in {"accept", "decline"}:
            return Response({"detail": "Unknown friend-request decision."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            relationship = respond_to_friend_request(
                friendship_id=request_id,
                recipient=request.user,
                accept=decision == "accept",
            )
        except Friendship.DoesNotExist:
            return Response({"detail": "Friend request not found."}, status=status.HTTP_404_NOT_FOUND)
        except FriendshipError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_friendship_payload(relationship, request.user))
