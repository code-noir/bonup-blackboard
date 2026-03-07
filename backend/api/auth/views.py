from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class AuthViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list auth"})

    def create(self, request):
        return Response({"message": "create auth"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve auth {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update auth {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete auth {pk}"})




