from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class ObligationsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list obligations"})

    def create(self, request):
        return Response({"message": "create obligations"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve obligations {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update obligations {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete obligations {pk}"})