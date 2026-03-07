from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class WorkspaceViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list workspace"})

    def create(self, request):
        return Response({"message": "create workspace "})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve workspace {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update workspace {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete workspace {pk}"})