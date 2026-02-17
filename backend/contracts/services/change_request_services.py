# backend/contracts/services/change_request_services.py

from django.utils import timezone
from backend.contracts.models import RequestChange


def mark_reviewed(change_request: RequestChange):
    change_request.status = "reviewed"
    change_request.reviewed_at = timezone.now()
    change_request.save(update_fields=["status", "reviewed_at"])
    return change_request


def mark_resolved(change_request: RequestChange):
    change_request.status = "resolved"
    change_request.save(update_fields=["status"])
    return change_request


def mark_rejected(change_request: RequestChange):
    change_request.status = "rejected"
    change_request.save(update_fields=["status"])
    return change_request
