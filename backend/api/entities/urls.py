# backend/api/entities/urls.py

from django.urls import path

from .views import EntityDetailView, EntityListCreateView

urlpatterns = [
    path("", EntityListCreateView.as_view(), name="entities-list-create"),
    path("<uuid:entity_id>/", EntityDetailView.as_view(), name="entities-detail"),
]
