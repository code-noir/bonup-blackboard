# backend/api/notifications/views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.notifications.models import Notification
from backend.notifications.visibility import visible_notifications


_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100
_UNREAD_DROPDOWN_SIZE = 20


def _serialize(n):
    return {
        "id": str(n.id),
        "notification_type": n.notification_type,
        "title": n.title,
        "message": n.message,
        "is_read": n.is_read,
        "related_contract_id": str(n.related_contract_id) if n.related_contract_id else None,
        "metadata": n.metadata,
        "redirect_url": (n.metadata or {}).get("redirect_url", ""),
        "target_url": (n.metadata or {}).get("redirect_url", ""),
        "created_at": n.created_at,
    }


class NotificationListAPIView(APIView):
    """
    GET /api/notifications/

    List the authenticated user's notifications, newest first.
    Supports:
      ?is_read=true|false  — filter by read status
      ?page=               — 1-based page number (default 1)
      ?page_size=          — items per page (default 20, max 100)
    """

    def get(self, request):
        qs = visible_notifications(Notification.objects.filter(user=request.user))

        is_read_param = request.query_params.get("is_read")
        if is_read_param is not None:
            qs = qs.filter(is_read=is_read_param.lower() == "true")

        total = qs.count()

        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = min(_MAX_PAGE_SIZE, max(1, int(request.query_params.get("page_size", _DEFAULT_PAGE_SIZE))))
        except (ValueError, TypeError):
            page_size = _DEFAULT_PAGE_SIZE

        offset = (page - 1) * page_size
        results = qs[offset: offset + page_size]

        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": [_serialize(n) for n in results],
        })


class NotificationUnreadListAPIView(APIView):
    """
    GET /api/notifications/unread/

    Returns the authenticated user's unread notifications, newest first.
    """

    def get(self, request):
        qs = visible_notifications(Notification.objects.filter(user=request.user, is_read=False)).order_by("-created_at")[:_UNREAD_DROPDOWN_SIZE]
        return Response({"results": [_serialize(n) for n in qs]})


class NotificationUnreadCountAPIView(APIView):
    """
    GET /api/notifications/unread-count/

    Returns the number of unread notifications for the authenticated user.
    """

    def get(self, request):
        count = visible_notifications(Notification.objects.filter(user=request.user, is_read=False)).count()
        return Response({"unread_count": count})


class NotificationReadAllAPIView(APIView):
    """
    POST /api/notifications/read-all/

    Marks all of the authenticated user's unread notifications as read.
    """

    def post(self, request):
        updated = visible_notifications(Notification.objects.filter(user=request.user, is_read=False)).update(is_read=True)
        return Response({"marked_read": updated})


class NotificationMarkReadAPIView(APIView):
    """
    POST /api/notifications/<notification_id>/read/

    Marks a single notification as read. Returns 403 if the notification
    belongs to a different user.
    """

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id)
        if notification.user_id != request.user.pk:
            return Response(
                {"error": "Not found."},
                status=status.HTTP_403_FORBIDDEN,
            )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(_serialize(notification))
