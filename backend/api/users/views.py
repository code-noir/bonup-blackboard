from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class UsersViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list users"})

    def create(self, request):
        return Response({"message": "create users"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve users {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update users {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete users {pk}"})