from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class SessionsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list sessions"})

    def create(self, request):
        return Response({"message": "create sessions"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve sessions {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update sessions {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete sessions {pk}"})