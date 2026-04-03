# backend/api/search/urls.py

from django.urls import path

from .views import GlobalSearchView, ContractSearchView, TemplateSearchView

urlpatterns = [
    path("", GlobalSearchView.as_view(), name="search-global"),
    path("contracts/", ContractSearchView.as_view(), name="search-contracts"),
    path("templates/", TemplateSearchView.as_view(), name="search-templates"),
]
