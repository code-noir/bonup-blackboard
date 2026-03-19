# backend/api/contracts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ContractViewSet
from .obligations_views import ContractObligationsAPIView
from .proof_views import ObligationProofOfWorkAPIView


router = DefaultRouter()
router.register(r"", ContractViewSet, basename="contract")


urlpatterns = [
    path(
        "<uuid:contract_id>/obligations/",
        ContractObligationsAPIView.as_view(),
        name="contract-obligations",
    ),
    path(
        "obligations/<str:obligation_type>/<uuid:obligation_id>/proof/",
        ObligationProofOfWorkAPIView.as_view(),
        name="contract-obligation-proof-of-work",
    ),
    path("", include(router.urls)),
]






