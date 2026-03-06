# backend/api/contracts/urls.py

from django.urls import path
from .views import (
    ContractListCreateAPIView,
    ContractDetailAPIView,
)

urlpatterns = [
    path("", ContractListCreateAPIView.as_view(), name="contract-list-create"),
    path("<uuid:id>/", ContractDetailAPIView.as_view(), name="contract-detail"),
]



