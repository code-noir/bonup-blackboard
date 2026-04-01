# backend/api/sessions/urls.py

from django.urls import path
from .views import SessionListCreateAPIView, SessionDetailAPIView, SessionJoinAPIView, SessionEndAPIView

urlpatterns = [
    path("", SessionListCreateAPIView.as_view(), name="session-list-create"),
    path("<uuid:session_id>/", SessionDetailAPIView.as_view(), name="session-detail"),
    path("<uuid:session_id>/join/", SessionJoinAPIView.as_view(), name="session-join"),
    path("<uuid:session_id>/end/", SessionEndAPIView.as_view(), name="session-end"),
]
