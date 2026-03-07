from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class TemplatesViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list templates"})

    def create(self, request):
        return Response({"message": "create templates"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve templates {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update templates {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete templates {pk}"})