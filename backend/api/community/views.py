from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.community.serializers import (
    CommunityCreateSerializer,
    CommunitySerializer,
)
from backend.community.models import Community, CommunityMembership
from backend.community.permissions import (
    community_resource_or_404,
    require_community_member,
)
from backend.community.services import create_community


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
        community = create_community(owner=request.user, **serializer.validated_data)
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
