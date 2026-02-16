
# backend/contracts/models.py
#
# SPEC: dev/specs/contract-container.md
# SPEC: dev/specs/contract-version-engine.md

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

    # 🔒 Negotiation limit (long-term architecture)
    max_versions = models.PositiveIntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Contract {self.id}"

    def current_version_count(self):
        return self.versions.count()

    def negotiation_rounds_used(self):
        """
        Version 1 = original
        Negotiation rounds = total_versions - 1
        """
        count = self.current_version_count()
        return max(count - 1, 0)


    # ============================================================
    # CONTRACT VERSION ENGINE (IMMUTABLE)
    # ============================================================

class ContractVersion(models.Model):
    """
    Immutable snapshot of a contract at a specific moment.

    Every negotiation creates a new version.
    Previous versions are NEVER edited.
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

    # =========================================================
    # IMMUTABILITY + VERSION SEQUENCING
    # =========================================================

    def save(self, *args, **kwargs):

        # If updating existing version
        if not self._state.adding:

            # Allow controlled updates (like superseding)
            if "update_fields" in kwargs:
                return super().save(*args, **kwargs)

            raise Exception("Contract versions are immutable.")

        # 🔒 ENFORCE NEGOTIATION LIMIT
        current_count = self.contract.versions.count()

        if current_count >= self.contract.max_versions:
            raise Exception("Negotiation limit reached for this contract.")

        last_version = (
            ContractVersion.objects
            .filter(contract=self.contract)
            .order_by("-version_number")
            .first()
        )

        if last_version:
            self.version_number = last_version.version_number + 1
            self.previous_version = last_version

            # Mark previous version as superseded
            last_version.status = "superseded"
            last_version.superseded = True
            last_version.save(update_fields=["status", "superseded"])
        else:
            self.version_number = 1

        return super().save(*args, **kwargs)

    # =========================================================
    # STATE TRANSITIONS
    # =========================================================

    ALLOWED_TRANSITIONS = {
        "draft": ["sent", "archived"],
        "sent": ["negotiating", "signed", "rejected", "archived"],
        "negotiating": ["superseded", "archived"],
        "signed": ["archived"],
        "rejected": ["archived"],
        "superseded": [],
        "archived": [],
    }

    def transition_to(self, new_status):

        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError(f"Invalid status: {new_status}")

        allowed = self.ALLOWED_TRANSITIONS.get(self.status, [])

        if new_status not in allowed:
            raise ValueError(
                f"Illegal transition from '{self.status}' to '{new_status}'"
            )

        self.status = new_status
        super().save(update_fields=["status"])

        # =========================================================
        # VERSION CREATION HELPERS
        # =========================================================

    @classmethod
    def create_initial_version(cls, contract, content, user=None):

        if cls.objects.filter(contract=contract).exists():
            raise Exception("Initial version already exists.")

        return cls.objects.create(
            contract=contract,
            content_snapshot=content,
            created_by=user,
            status="draft"
        )

    @classmethod
    def create_new_version(cls, contract, content, user=None):
        """
        Creates a new negotiated/amended version.
        Enforces negotiation round limit.
        """

        versions = (
            cls.objects
            .filter(contract=contract)
            .order_by("-version_number")
        )

        if not versions.exists():
            raise Exception("No previous version exists.")

        # Initial version does NOT count toward negotiation rounds
        total_versions = versions.count()

        MAX_NEGOTIATION_ROUNDS = 2

        # total versions = 1 (initial) + negotiation rounds
        if total_versions >= 1 + MAX_NEGOTIATION_ROUNDS:
            raise Exception("Negotiation limit reached for this contract.")

        return cls.objects.create(
            contract=contract,
            content_snapshot=content,
            created_by=user,
            status="draft"
        )

        # ============================================================
        # REQUEST CHANGE MODEL (NEGOTIATION INTENT)
        # ============================================================

class RequestChange(models.Model):
    """
    Represents a structured negotiation request
    submitted by the counterparty.

    Does NOT create a new version automatically.
    Initiator must review and create a new version.
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

    message = models.TextField(
        help_text="Structured explanation of requested changes."
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    def mark_reviewed(self):
        self.status = "reviewed"
        self.save(update_fields=["status"])

    def mark_resolved(self):
        self.status = "resolved"
        self.save(update_fields=["status"])

    def mark_rejected(self):
        self.status = "rejected"
        self.save(update_fields=["status"])

    def __str__(self):
        return f"RequestChange {self.id} - {self.status}"
























