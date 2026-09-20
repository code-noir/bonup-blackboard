from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.bonup.models import ApprovedProductDirection

from .serializers import ApprovedProductDirectionSerializer


class ApprovedProductDirectionListView(APIView):
    """Read-only Blackboard projection; no event input is accepted."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = ApprovedProductDirection.objects.all()[:100]
        return Response({
            "results": ApprovedProductDirectionSerializer(rows, many=True).data,
        })
