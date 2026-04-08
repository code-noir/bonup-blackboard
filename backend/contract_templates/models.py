# backend/contract_templates/models.py

import uuid
from django.db import models


class ContractTemplate(models.Model):

    TIER_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("premium", "Premium"),
        ("enterprise", "Enterprise"),
    ]

    STRUCTURE_CHOICES = [
        ("ONE_TIME", "One-Time Service"),
        ("ONGOING", "Ongoing Service"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    description = models.TextField()
    structure_type = models.CharField(
        max_length=20,
        choices=STRUCTURE_CHOICES,
        default="ONE_TIME",
    )
    is_active = models.BooleanField(default=True)
    tier_required = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default="free",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.category} / {self.subcategory})"


class TemplateGuidedField(models.Model):

    FIELD_TYPE_CHOICES = [
        ("text", "Text"),
        ("number", "Number"),
        ("choice", "Choice"),
        ("boolean", "Boolean"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.CASCADE,
        related_name="guided_fields",
    )
    field_key = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    choices = models.JSONField(null=True, blank=True)
    is_required = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    # Conditionality: this field is only active/required when another field
    # equals a specific value. Both must be set together or left empty.
    condition_field_key = models.CharField(max_length=100, blank=True, default="")
    condition_value = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["order"]
        unique_together = ("template", "field_key")

    def __str__(self):
        return f"{self.template.name} — {self.label} ({self.field_key})"


class TemplateClause(models.Model):

    CLAUSE_TYPE_CHOICES = [
        ("scope", "Scope of Services"),
        ("payment", "Payment Terms"),
        ("cancellation", "Cancellation Policy"),
        ("liability", "Limitation of Liability"),
        ("termination", "Termination"),
        ("risk", "Assumption of Risk"),
        ("confidentiality", "Confidentiality"),
        ("general", "General"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.CASCADE,
        related_name="clauses",
    )
    clause_type = models.CharField(max_length=50, choices=CLAUSE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_conditional = models.BooleanField(default=False)
    condition_description = models.CharField(max_length=500, blank=True, default="")
    is_required = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.template.name} — {self.title}"


class TemplateObligationPattern(models.Model):

    OBLIGATION_TYPE_CHOICES = [
        ("service", "Service Only"),
        ("payment", "Payment Only"),
        ("both", "Service and Payment"),
    ]

    FREQUENCY_TYPE_CHOICES = [
        ("one_time", "One Time"),
        ("per_session", "Per Session"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("installment", "Installment"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.OneToOneField(
        ContractTemplate,
        on_delete=models.CASCADE,
        related_name="obligation_pattern",
    )
    obligation_type = models.CharField(
        max_length=20,
        choices=OBLIGATION_TYPE_CHOICES,
        default="both",
    )
    frequency_type = models.CharField(
        max_length=20,
        choices=FREQUENCY_TYPE_CHOICES,
        default="one_time",
    )
    # Each token field names the guided_field.field_key that supplies the value.
    amount_token = models.CharField(max_length=100, blank=True, default="")
    installments_token = models.CharField(max_length=100, blank=True, default="")
    interval_days_token = models.CharField(max_length=100, blank=True, default="")
    # When set, names the guided field that selects the payment model
    # (e.g. "single_session" / "package_upfront" / "package_installments").
    # The instantiation service branches on this value to resolve amounts and counts.
    payment_model_token = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"{self.template.name} — obligation pattern ({self.obligation_type}, {self.frequency_type})"


class ObligationTemplate(models.Model):
    """Standalone obligation/deliverable template extracted from contract templates."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    content = models.TextField()
    category = models.CharField(max_length=100)
    contract_template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="obligation_templates",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.category})"


class PaymentTemplate(models.Model):
    """Standalone payment terms template extracted from contract templates."""

    SCHEDULE_TYPE_CHOICES = [
        ("one_time", "One Time"),
        ("installment", "Installment"),
        ("recurring", "Recurring"),
        ("milestone", "Milestone"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    content = models.TextField()
    schedule_type = models.CharField(
        max_length=50,
        choices=SCHEDULE_TYPE_CHOICES,
        default="one_time",
    )
    category = models.CharField(max_length=100)
    contract_template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_templates",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.category} / {self.schedule_type})"
