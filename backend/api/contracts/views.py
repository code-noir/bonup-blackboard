from rest_framework import generics
from rest_framework.permissions import AllowAny

from backend.contracts.models import Contract
from .serializers import ContractSerializer


class ContractListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  -> List contracts
    POST -> Create contract
    """

    queryset = Contract.objects.all().order_by("-created_at")
    serializer_class = ContractSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        print("===== DEBUG START =====")
        print("request.user:", self.request.user)
        print("is_authenticated:", self.request.user.is_authenticated)
        print("user type:", type(self.request.user))
        print("===== DEBUG END =====")

        serializer.save(
            initiator=self.request.user if self.request.user.is_authenticated else None
        )


class ContractDetailAPIView(generics.RetrieveAPIView):
    """
    GET -> Retrieve single contract
    """

    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [AllowAny]







