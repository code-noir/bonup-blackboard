# backend/api/notifications/urls.py

from django.urls import path
from .views import (
    NotificationListAPIView,
    NotificationMarkReadAPIView,
    NotificationReadAllAPIView,
    NotificationUnreadCountAPIView,
)

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="notification-list"),
    # Fixed paths must come before the UUID capture pattern.
    path("unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),
    path("read-all/", NotificationReadAllAPIView.as_view(), name="notification-read-all"),
    path("<uuid:notification_id>/read/", NotificationMarkReadAPIView.as_view(), name="notification-mark-read"),
]
