from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class UploadsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list uploads"})

    def create(self, request):
        return Response({"message": "create uploads "})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve uploads {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update uploads {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete uploads {pk}"})