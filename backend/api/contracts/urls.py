# backend/api/contracts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ContractViewSet
from .obligations_views import ContractObligationsAPIView

# -----------------------------
# ROUTER (for contracts CRUD)
# -----------------------------
router = DefaultRouter()
router.register(r"", ContractViewSet, basename="contract")

# -----------------------------
# CUSTOM ENDPOINTS (OBLIGATIONS)
# -----------------------------
urlpatterns = [
    # custom obligations endpoint
    path(
        "<uuid:contract_id>/obligations/",
        ContractObligationsAPIView.as_view(),
        name="contract-obligations",
    ),

    # router endpoints
    path("", include(router.urls)),
]






