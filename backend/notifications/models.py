# backend/notifications/models.py

import uuid

from django.contrib.auth import get_user_model
from django.db import models

from backend.contracts.models import Contract

User = get_user_model()


class Notification(models.Model):

    NOTIFICATION_TYPE_CHOICES = [
        # Contract lifecycle
        ("contract_created", "Contract Created"),
        ("contract_updated", "Contract Updated"),
        # Version negotiation
        ("agreement_exchange", "Agreement Exchange"),
        ("agreement_timeline", "Agreement Timeline"),
        ("version_created", "Version Created"),
        ("version_signed", "Version Signed"),
        ("version_rejected", "Version Rejected"),
        # Role management
        ("role_switch_requested", "Role Switch Requested"),
        ("role_switch_confirmed", "Role Switch Confirmed"),
        # Obligations
        ("obligation_resolved", "Obligation Resolved"),
        ("payment_obligation_resolved", "Payment Obligation Resolved"),
        # Payments
        ("payment_created", "Payment Created"),
        ("payment_confirmed", "Payment Confirmed"),
        ("payment_failed", "Payment Failed"),
        ("payment_cancelled", "Payment Cancelled"),
        ("payment_refunded", "Payment Refunded"),
        ("payment_reversed", "Payment Reversed"),
        # Approvals
        ("approval_requested", "Approval Requested"),
        ("approval_granted", "Approval Granted"),
        ("approval_rejected", "Approval Rejected"),
        # Sessions
        ("session_held", "Session Held"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.notification_type} for {self.user_id} at {self.created_at}"
