from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from backend.contracts.models import Obligation
from .serializers import ObligationSerializer


class ObligationsViewSet(ViewSet):

    def list(self, request):
        obligations = Obligation.objects.all()
        serializer = ObligationSerializer(obligations, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = ObligationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)

    def retrieve(self, request, pk=None):
        obligation = Obligation.objects.get(pk=pk)
        serializer = ObligationSerializer(obligation)
        return Response(serializer.data)

    def update(self, request, pk=None):
        obligation = Obligation.objects.get(pk=pk)
        serializer = ObligationSerializer(obligation, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)

    def destroy(self, request, pk=None):
        obligation = Obligation.objects.get(pk=pk)
        obligation.delete()
        return Response({"message": "obligation deleted"})


