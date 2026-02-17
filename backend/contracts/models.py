# backend/contracts/models.py

from django.db import models
from django.conf import settings
import uuid


# ============================================================
# CONTRACT CONTAINER
# ============================================================

class Contract(models.Model):
    """
    Contract container.
    Holds identity, relationship, and negotiation limits.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="initiated_contracts"
    )

    counterparty_email = models.EmailField()

    max_versions = models.PositiveIntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Contract {self.id}"


# ============================================================
# CONTRACT VERSION (IMMUTABLE SNAPSHOT)
# ============================================================

class ContractVersion(models.Model):
    """
    Immutable snapshot of a contract at a specific moment.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("negotiating", "Negotiating"),
        ("signed", "Signed"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="versions"
    )

    version_number = models.PositiveIntegerField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    previous_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_versions"
    )

    superseded = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )

    content_snapshot = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("contract", "version_number")
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.contract.id} - v{self.version_number} - {self.status}"
    
    def save(self, *args, **kwargs):
        if self.pk:
            raise Exception("ContractVersion is immutable and cannot be modified.")
        super().save(*args, **kwargs)



# ============================================================
# REQUEST CHANGE (NEGOTIATION INTENT)
# ============================================================

class RequestChange(models.Model):
    """
    Represents a structured negotiation request.
    Does NOT create a new version automatically.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
        ("resolved", "Resolved"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="change_requests"
    )

    version = models.ForeignKey(
        ContractVersion,
        on_delete=models.CASCADE,
        related_name="change_requests"
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"RequestChange {self.id} - {self.status}"





































