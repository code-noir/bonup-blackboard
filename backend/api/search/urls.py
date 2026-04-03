# backend/api/search/urls.py

from django.urls import path

from .views import (
    GlobalSearchView,
    ContractSearchView,
    ObligationSearchView,
    PaymentSearchView,
    SessionSearchView,
    DocumentSearchView,
    TemplateSearchView,
)

urlpatterns = [
    path("", GlobalSearchView.as_view(), name="search-global"),
    path("contracts/", ContractSearchView.as_view(), name="search-contracts"),
    path("obligations/", ObligationSearchView.as_view(), name="search-obligations"),
    path("payments/", PaymentSearchView.as_view(), name="search-payments"),
    path("sessions/", SessionSearchView.as_view(), name="search-sessions"),
    path("documents/", DocumentSearchView.as_view(), name="search-documents"),
    path("templates/", TemplateSearchView.as_view(), name="search-templates"),
]
