# backend/contracts/models.py

from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid

from backend.core.currencies import CURRENCY_CHOICES


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

    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default="USD",
    )

    ENTITY_TYPE_CHOICES = [("personal", "Personal"), ("business", "Business")]
    entity_type = models.CharField(
        max_length=10,
        choices=ENTITY_TYPE_CHOICES,
        default="personal",
    )
    entity = models.ForeignKey(
        "users.BusinessEntity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts",
    )

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

    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default="USD",
    )

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
   



class ObligationExecutionSession(models.Model):
    """
    Real execution session under a contract obligation.

    One obligation may have multiple execution sessions.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("closed", "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payment_obligation = models.ForeignKey(
        ContractObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="execution_sessions",
    )

    service_obligation = models.ForeignKey(
        ContractServiceObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="execution_sessions",
    )

    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ExecutionSession {self.id} ({self.status})"


class ObligationExecutionEvent(models.Model):
    """
    Structured execution event captured during an execution session.

    These events become the foundation for proof of work / PBVD.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        ObligationExecutionSession,
        on_delete=models.CASCADE,
        related_name="events",
    )

    event_type = models.CharField(max_length=100)

    task = models.CharField(max_length=255, null=True, blank=True)
    observation = models.CharField(max_length=255, null=True, blank=True)

    summary = models.TextField()

    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    estimated_cost_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    estimated_cost_currency = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    planned_execution_time = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.event_type} - {self.created_at}"


class ContractValueAdjustment(models.Model):
    """
    Stored financial adjustment connected to contract execution.

    This makes value adjustments first-class contract data instead of
    proof-only generated output.

    Examples:
    - additional_charge
    - lateness_adjustment
    """

    ADJUSTMENT_TYPE_CHOICES = [
        ("additional_charge", "Additional Charge"),
        ("lateness_adjustment", "Lateness Adjustment"),
    ]

    MODE_CHOICES = [
        ("fixed_amount", "Fixed Amount"),
        ("percentage", "Percentage"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="value_adjustments",
    )

    payment_obligation = models.ForeignKey(
        ContractObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="value_adjustments",
    )

    service_obligation = models.ForeignKey(
        ContractServiceObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="value_adjustments",
    )

    execution_event = models.ForeignKey(
        ObligationExecutionEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="value_adjustments",
    )

    adjustment_type = models.CharField(
        max_length=50,
        choices=ADJUSTMENT_TYPE_CHOICES,
    )

    mode = models.CharField(
        max_length=50,
        choices=MODE_CHOICES,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=10,
        default="USD",
    )

    summary = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.adjustment_type} - {self.amount} {self.currency}"

class ContractApprovalRequest(models.Model):
    """
    Stored approval request generated from contract execution or adjustment flow.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="approval_requests",
    )

    payment_obligation = models.ForeignKey(
        ContractObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="approval_requests",
    )

    service_obligation = models.ForeignKey(
        ContractServiceObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="approval_requests",
    )

    execution_event = models.ForeignKey(
        ObligationExecutionEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_contract_approvals",
    )

    requested_from = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_contract_approvals",
    )

    approval_type = models.CharField(
        max_length=50,
        default="execution_item",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    summary = models.TextField()

    metadata = models.JSONField(default=dict, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["requested_at"]

    def __str__(self):
        return f"{self.approval_type} - {self.status}"

class ContractRoleSwitchRequest(models.Model):
    """
    Represents a counterparty's request to swap roles with the initiator.

    On confirmation the original contract is deleted and a new one is created
    with the roles reversed (fresh start, no content, new ID).

    Only one pending request is allowed per contract at a time.
    Requests expire after 7 days if not confirmed.
    Role switches are blocked once any version has been signed.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="role_switch_requests",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_switch_requests_sent",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"RoleSwitchRequest({self.contract_id}, {self.status})"


# ============================================================
# CONTRACT OBLIGATION PROMOTION
# ============================================================

class ContractObligationPromotion(models.Model):
    """
    Tracks promotion of an execution event into a side obligation.
    """

    PROMOTION_TYPE_CHOICES = [
        ("event_to_service_obligation", "Event to Service Obligation"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="obligation_promotions",
    )

    source_execution_event = models.ForeignKey(
        ObligationExecutionEvent,
        on_delete=models.CASCADE,
        related_name="promotions",
    )

    parent_service_obligation = models.ForeignKey(
        ContractServiceObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="child_promotions",
    )

    promoted_service_obligation = models.ForeignKey(
        ContractServiceObligation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="origin_promotions",
    )

    promotion_type = models.CharField(
        max_length=50,
        choices=PROMOTION_TYPE_CHOICES,
        default="event_to_service_obligation",
    )

    summary = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.promotion_type} - {self.id}"








   
















































