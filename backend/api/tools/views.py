from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class ToolsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list tools"})

    def create(self, request):
        return Response({"message": "create tools"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve tools {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update tools {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete tools {pk}"})