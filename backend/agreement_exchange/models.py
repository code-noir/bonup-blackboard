import uuid

from django.conf import settings
from django.db import models


class AgreementExchange(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_VIEWED = "viewed"
    STATUS_COUNTERPARTY_REVIEW = "counterparty_review"
    STATUS_CHANGES_REQUESTED = "changes_requested"
    STATUS_INITIATOR_REVIEW = "initiator_review"
    STATUS_INITIATOR_EDITING = "initiator_editing"
    STATUS_UPDATED_VERSION_SENT = "updated_version_sent"
    STATUS_READY_TO_SIGN = "ready_to_sign"
    STATUS_SIGNED = "signed"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_VIEWED, "Viewed"),
        (STATUS_COUNTERPARTY_REVIEW, "Counterparty review"),
        (STATUS_CHANGES_REQUESTED, "Changes requested"),
        (STATUS_INITIATOR_REVIEW, "Initiator review"),
        (STATUS_INITIATOR_EDITING, "Initiator editing"),
        (STATUS_UPDATED_VERSION_SENT, "Updated version sent"),
        (STATUS_READY_TO_SIGN, "Ready to sign"),
        (STATUS_SIGNED, "Signed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    ACTOR_INITIATOR = "initiator"
    ACTOR_COUNTERPARTY = "counterparty"
    ACTOR_NONE = "none"

    ACTOR_CHOICES = [
        (ACTOR_INITIATOR, "Initiator"),
        (ACTOR_COUNTERPARTY, "Counterparty"),
        (ACTOR_NONE, "None"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey("contracts.Contract", on_delete=models.CASCADE, related_name="agreement_exchanges")
    current_contract_version = models.ForeignKey("contracts.ContractVersion", on_delete=models.PROTECT, related_name="agreement_exchanges")
    staged_contract_version = models.ForeignKey("contracts.ContractVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="staged_for_exchanges")
    source_contract_version = models.ForeignKey("contracts.ContractVersion", on_delete=models.PROTECT, null=True, blank=True, related_name="agreement_exchange_restarts")
    restarted_from_exchange = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="restarted_exchanges")
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="initiated_agreement_exchanges")
    counterparty_email = models.EmailField()
    counterparty_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="counterparty_agreement_exchanges")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    current_actor = models.CharField(max_length=16, choices=ACTOR_CHOICES, default=ACTOR_INITIATOR)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contract", "current_contract_version", "counterparty_email"]),
            models.Index(fields=["initiator", "status"]),
        ]

    def __str__(self):
        return f"AgreementExchange {self.id}"


class AgreementExchangeRequest(models.Model):
    CATEGORY_RECITALS_BACKGROUND = "recitals_background"
    CATEGORY_TERMS_AND_CONDITIONS = "terms_and_conditions"
    CATEGORY_OBLIGATIONS = "obligations"
    CATEGORY_PAYMENT_TERMS = "payment_terms"
    CATEGORY_CONFIDENTIALITY = "confidentiality"
    CATEGORY_INTELLECTUAL_PROPERTY = "intellectual_property"
    CATEGORY_TERMINATION = "termination"
    CATEGORY_DISPUTE_RESOLUTION = "dispute_resolution"
    CATEGORY_GOVERNING_LAW = "governing_law"

    CATEGORY_CHOICES = [
        (CATEGORY_RECITALS_BACKGROUND, "Recitals / Background"),
        (CATEGORY_TERMS_AND_CONDITIONS, "Terms and Conditions"),
        (CATEGORY_OBLIGATIONS, "Obligations"),
        (CATEGORY_PAYMENT_TERMS, "Payment Terms"),
        (CATEGORY_CONFIDENTIALITY, "Confidentiality"),
        (CATEGORY_INTELLECTUAL_PROPERTY, "Intellectual Property"),
        (CATEGORY_TERMINATION, "Termination"),
        (CATEGORY_DISPUTE_RESOLUTION, "Dispute resolution"),
        (CATEGORY_GOVERNING_LAW, "Governing Law"),
    ]

    ACTION_REPLACE = "replace_clause"
    ACTION_ADD = "add_clause"
    ACTION_REMOVE = "remove_clause"
    ACTION_CLARIFY = "clarify_clause"

    ACTION_CHOICES = [
        (ACTION_REPLACE, "Replace clause"),
        (ACTION_ADD, "Add clause"),
        (ACTION_REMOVE, "Remove clause"),
        (ACTION_CLARIFY, "Clarify clause"),
    ]

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_EDITED = "edited"
    STATUS_REJECTED = "rejected"
    STATUS_WITHDRAWN = "withdrawn"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_EDITED, "Edited"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exchange = models.ForeignKey(AgreementExchange, on_delete=models.CASCADE, related_name="requests")
    requested_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="agreement_exchange_requests")
    requested_by_email = models.EmailField(blank=True, default="")
    target_section_id = models.CharField(max_length=128, null=True, blank=True)
    target_section_title = models.CharField(max_length=255, blank=True, default="")
    request_category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default=CATEGORY_RECITALS_BACKGROUND)
    action_type = models.CharField(max_length=32, choices=ACTION_CHOICES)
    template_key = models.CharField(max_length=80, null=True, blank=True)
    proposed_text = models.TextField()
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    initiator_response = models.TextField(null=True, blank=True)
    pending_next_version_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["exchange", "status"]),
            models.Index(fields=["request_category"]),
        ]

    def __str__(self):
        return f"AgreementExchangeRequest {self.id}"


class AgreementExchangeEvent(models.Model):
    ROLE_INITIATOR = "initiator"
    ROLE_COUNTERPARTY = "counterparty"
    ROLE_SYSTEM = "system"

    ROLE_CHOICES = [
        (ROLE_INITIATOR, "Initiator"),
        (ROLE_COUNTERPARTY, "Counterparty"),
        (ROLE_SYSTEM, "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exchange = models.ForeignKey(AgreementExchange, on_delete=models.CASCADE, related_name="events")
    actor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="agreement_exchange_events")
    actor_email = models.EmailField(null=True, blank=True)
    actor_role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_SYSTEM)
    event_type = models.CharField(max_length=80)
    message = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["exchange", "created_at"])]

    def __str__(self):
        return f"AgreementExchangeEvent {self.event_type} {self.id}"


class AgreementExchangeSignature(models.Model):
    ROLE_INITIATOR = "initiator"
    ROLE_COUNTERPARTY = "counterparty"

    ROLE_CHOICES = [
        (ROLE_INITIATOR, "Initiator"),
        (ROLE_COUNTERPARTY, "Counterparty"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exchange = models.ForeignKey(AgreementExchange, on_delete=models.CASCADE, related_name="signatures")
    signer_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="agreement_exchange_signatures")
    signer_email = models.EmailField()
    signer_role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    signed_version = models.ForeignKey("contracts.ContractVersion", on_delete=models.PROTECT, related_name="agreement_exchange_signatures")
    typed_name = models.CharField(max_length=255, null=True, blank=True)
    signature_text = models.TextField(null=True, blank=True)
    signed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["signed_at"]
        indexes = [models.Index(fields=["exchange", "signer_role"])]

    def __str__(self):
        return f"AgreementExchangeSignature {self.signer_role} {self.id}"
