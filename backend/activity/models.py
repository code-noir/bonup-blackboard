# backend/activity/models.py

import uuid

from django.contrib.auth import get_user_model
from django.db import models

from backend.contracts.models import Contract

User = get_user_model()


class ContractActivity(models.Model):

    ACTIVITY_TYPE_CHOICES = [
        # Contract lifecycle
        ("contract_created", "Contract Created"),
        ("contract_updated", "Contract Updated"),
        # Version negotiation
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
        # Sessions (reserved for future Sessions domain)
        ("session_held", "Session Held"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="activity_log",
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_events",
    )
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contract", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.activity_type} on contract {self.contract_id} at {self.created_at}"
