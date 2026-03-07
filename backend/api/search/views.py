from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class SearchViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list search"})

    def create(self, request):
        return Response({"message": "create search"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve search {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update search {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete search {pk}"})