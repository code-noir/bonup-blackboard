# backend/contracts/models.py

from django.db import models
from django.utils import timezone
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

    STRUCTURE_CHOICES = [
        ("ONE_TIME", "One-Time Service"),
        ("ONGOING", "Ongoing Service"),
        ("COLLABORATIVE", "Collaborative Relationship"),
        ("RESOLUTION", "Resolution Contract"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_contracts",
    )

    counterparty_email = models.EmailField()

    structure_type = models.CharField(
        max_length=20,
        choices=STRUCTURE_CHOICES,
        default="ONE_TIME"
    )

    max_versions = models.PositiveIntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    state = models.CharField(
        max_length=20,
        default="active"
    )

    def str(self):
        return f"Contract {self.id}"

    def refresh_state(self):
        obligations = list(self.obligations.all())

        if not obligations:
            return self.state

        if all(ob.state == "resolved" for ob in obligations):
            self.state = "fulfilled"
        elif any(ob.state == "overdue" for ob in obligations):
            self.state = "at_risk"
        else:
            self.state = "active"

        return self.state


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

    def str(self):
        return f"{self.contract.id} - v{self.version_number} - {self.status}"

    def save(self, *args, **kwargs):

        if self._state.adding:
            return super().save(*args, **kwargs)

        allowed_fields = {"status", "superseded"}
        update_fields = set(kwargs.get("update_fields", []))

        if update_fields and update_fields.issubset(allowed_fields):
            return super().save(*args, **kwargs)

        raise Exception("ContractVersion is immutable and cannot be modified.")


# ============================================================
# OBLIGATION TEMPLATE (DEFINITION)
# ============================================================

class Obligation(models.Model):
    """
    Defines a contract obligation template.

    The engine expands this into actual lifecycle instances
    stored in ContractObligation.
    """

    OBLIGATION_TYPE_CHOICES = [
        ("payment", "Payment Obligation"),
        ("service", "Service Obligation"),
    ]

    STATE_CHOICES = [
        ("pending", "Pending"),
        ("due", "Due"),
        ("fulfilled", "Fulfilled"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="obligations"
    )

    obligation_type = models.CharField(
        max_length=20,
        choices=OBLIGATION_TYPE_CHOICES,
        default="payment"
    )

    from_party = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="obligations_owed"
    )

    to_party = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="obligations_due"
    )

    description = models.TextField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    currency = models.CharField(
        max_length=10,
        default="USD"
    )

    start_date = models.DateTimeField(
        null=True,
        blank=True
    )

    due_date = models.DateTimeField(
        null=True,
        blank=True
    )

    recurrence_interval_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="If set, obligation recurs every X days."
    )

    recurrence_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="How many times this obligation repeats."
    )

    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def str(self):
        return f"{self.contract.id} - {self.obligation_type} - {self.description}"


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

    def str(self):
        return f"RequestChange {self.id} - {self.status}"


# ============================================================
# CONTRACT OBLIGATION (ENGINE GENERATED INSTANCE)
# ============================================================

class ContractObligation(models.Model):
    """
    Database representation of a generated obligation instance.

    Engine logic lives in backend.engine.obligations.
    """

    STATE_CHOICES = [
        ("active", "Active"),
        ("due", "Due"),
        ("grace", "Grace"),
        ("overdue", "Overdue"),
        ("defaulted", "Defaulted"),
        ("resolved", "Resolved"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="contract_obligations_links"
    )

   




    version = models.ForeignKey(
        ContractVersion,
        on_delete=models.CASCADE,
        related_name="obligations"
    )

    obligor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owed_obligations"
    )

    obligee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="receivable_obligations"
    )

    installment_number = models.PositiveIntegerField()

    amount_due = models.DecimalField(max_digits=12, decimal_places=2)

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    due_date = models.DateTimeField()

    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default="active"
    )

    is_defaulted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date"]

    def str(self):
        return f"Obligation {self.installment_number} - {self.state}"

    def is_past_due(self, current_time=None):

        if current_time is None:
            current_time = timezone.now()

        if self.due_date is None:
            return False

        return (
            self.state == "active"
            and self.amount_paid < self.amount_due
            and self.due_date < current_time
        )

class ContractServiceObligation(models.Model):

        STATE_CHOICES = [
            ("active", "Active"),
            ("due", "Due"),
            ("overdue", "Overdue"),
            ("resolved", "Resolved"),
        ]

        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

        contract = models.ForeignKey(
            Contract,
            on_delete=models.CASCADE,
            related_name="service_obligations"
        )

        version = models.ForeignKey(
            ContractVersion,
            on_delete=models.CASCADE,
            related_name="service_obligations"
        )

        obligor = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE,
            related_name="service_owed"
        )

        obligee = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE,
            related_name="service_receivable"
        )

        description = models.TextField()

        due_date = models.DateTimeField()

        state = models.CharField(
            max_length=20,
            choices=STATE_CHOICES,
            default="active"
        )

        completed_at = models.DateTimeField(null=True, blank=True)

        created_at = models.DateTimeField(auto_now_add=True)

        updated_at = models.DateTimeField(auto_now=True)

        def mark_completed(self):
            self.state = "resolved"
            self.completed_at = timezone.now()
            self.save(update_fields=["state", "completed_at", "updated_at"])
   











   
















































