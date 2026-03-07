from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class ActivityViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list activity logs"})

    def create(self, request):
        return Response({"message": "create activity log"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve activity {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update activity {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete activity {pk}"})
