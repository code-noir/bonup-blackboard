# backend/api/prep/urls.py

from django.urls import path
from .views import (
    PrepSessionListCreateAPIView,
    PrepSessionDetailAPIView,
    PrepDocumentCreateAPIView,
    PrepDocumentDeleteAPIView,
    PrepNoteCreateAPIView,
    PrepNoteUpdateDeleteAPIView,
)

urlpatterns = [
    path("", PrepSessionListCreateAPIView.as_view(), name="prep-list-create"),
    path("<uuid:prep_id>/", PrepSessionDetailAPIView.as_view(), name="prep-detail"),
    path("<uuid:prep_id>/documents/", PrepDocumentCreateAPIView.as_view(), name="prep-document-create"),
    path("<uuid:prep_id>/documents/<uuid:doc_id>/", PrepDocumentDeleteAPIView.as_view(), name="prep-document-delete"),
    path("<uuid:prep_id>/notes/", PrepNoteCreateAPIView.as_view(), name="prep-note-create"),
    path("<uuid:prep_id>/notes/<uuid:note_id>/", PrepNoteUpdateDeleteAPIView.as_view(), name="prep-note-update-delete"),
]
