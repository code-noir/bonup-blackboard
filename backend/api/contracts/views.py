from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class ContractsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list contracts"})

    def create(self, request):
        return Response({"message": "create contracts"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve contracts {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update contracts {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete contracts {pk}"})


