# backend/api/sessions/urls.py

from django.urls import path
from .views import (
    SessionListCreateAPIView,
    SessionDetailAPIView,
    SessionCancelAPIView,
    SessionJoinAPIView,
    SessionEndAPIView,
    SessionBroadcastAPIView,
)

urlpatterns = [
    path("", SessionListCreateAPIView.as_view(), name="session-list-create"),
    path("<uuid:session_id>/", SessionDetailAPIView.as_view(), name="session-detail"),
    path("<uuid:session_id>/cancel/", SessionCancelAPIView.as_view(), name="session-cancel"),
    path("<uuid:session_id>/join/", SessionJoinAPIView.as_view(), name="session-join"),
    path("<uuid:session_id>/end/", SessionEndAPIView.as_view(), name="session-end"),
    path("<uuid:session_id>/broadcast/", SessionBroadcastAPIView.as_view(), name="session-broadcast"),
]
