

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class BillingViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list billing logs"})

    def create(self, request):
        return Response({"message": "create billing log"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve billing {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update billing {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete billing {pk}"})
