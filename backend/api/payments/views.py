from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class PaymentsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list payments"})

    def create(self, request):
        return Response({"message": "create payments"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve payments {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update payments {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete payments {pk}"})