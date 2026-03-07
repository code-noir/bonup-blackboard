from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class NotificationsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list notifications"})

    def create(self, request):
        return Response({"message": "create notifications"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve notifications {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update notifications {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete notifications {pk}"})
