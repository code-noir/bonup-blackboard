from rest_framework.viewsets import ViewSet
from rest_framework.response import Response


class DocumentsViewSet(ViewSet):

    def list(self, request):
        return Response({"message": "list documents"})

    def create(self, request):
        return Response({"message": "create documents"})

    def retrieve(self, request, pk=None):
        return Response({"message": f"retrieve documents {pk}"})

    def update(self, request, pk=None):
        return Response({"message": f"update documents {pk}"})

    def destroy(self, request, pk=None):
        return Response({"message": f"delete documents {pk}"})
