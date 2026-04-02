# backend/sessions/models.py

import uuid

from django.contrib.auth import get_user_model
from django.db import models

from backend.contracts.models import Contract, ContractVersion

User = get_user_model()


class LiveSession(models.Model):

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("active", "Active"),
        ("ended", "Ended"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="live_sessions",
    )
    version = models.ForeignKey(
        ContractVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="live_sessions",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_live_sessions",
    )

    CONTROLLER_CHOICES = [
        ("initiator", "Initiator"),
        ("counterparty", "Counterparty"),
    ]

    title = models.CharField(max_length=200, blank=True, default="")
    room_name = models.CharField(max_length=200, unique=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )

    presentation_controller = models.CharField(
        max_length=20,
        choices=CONTROLLER_CHOICES,
        default="initiator",
    )

    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contract", "-created_at"]),
        ]

    def __str__(self):
        return f"LiveSession {self.id} ({self.status}) on contract {self.contract_id}"
