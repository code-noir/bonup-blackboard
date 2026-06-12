import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class AIConversation(models.Model):

    CONVERSATION_TYPE_CHOICES = [
        ("general", "General"),
        ("contract_help", "Contract Help"),
        ("template_recommendation", "Template Recommendation"),
        ("contract_generation", "Contract Generation"),
        ("obligation_creation", "Obligation Creation"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )

    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )

    conversation_type = models.CharField(
        max_length=30,
        choices=CONVERSATION_TYPE_CHOICES,
        default="general",
    )

    # List of {"role": "user"|"assistant", "content": "..."}
    messages = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"AIConversation({self.user_id}, {self.conversation_type}, {self.updated_at:%Y-%m-%d})"


class WorkflowState(models.Model):

    STATE_UPLOADED = "uploaded"
    STATE_ANALYZING = "analyzing"
    STATE_REVIEW_READY = "review_ready"
    STATE_COUNTER_DRAFT_READY = "counter_draft_ready"
    STATE_VERSION_CREATED = "version_created"
    STATE_SENT_TO_COUNTERPARTY = "sent_to_counterparty"
    STATE_COUNTERPARTY_VIEWED = "counterparty_viewed"
    STATE_COUNTERPARTY_REQUESTED_CHANGES = "counterparty_requested_changes"
    STATE_COUNTERPARTY_COUNTER_GENERATED = "counterparty_counter_generated"
    STATE_ACCEPTED = "accepted"
    STATE_REJECTED = "rejected"
    STATE_SIGNED = "signed"

    STATE_CHOICES = [
        (STATE_UPLOADED, "Uploaded"),
        (STATE_ANALYZING, "Analyzing"),
        (STATE_REVIEW_READY, "Review Ready"),
        (STATE_COUNTER_DRAFT_READY, "Counter Draft Ready"),
        (STATE_VERSION_CREATED, "Version Created"),
        (STATE_SENT_TO_COUNTERPARTY, "Sent To Counterparty"),
        (STATE_COUNTERPARTY_VIEWED, "Counterparty Viewed"),
        (STATE_COUNTERPARTY_REQUESTED_CHANGES, "Counterparty Requested Changes"),
        (STATE_COUNTERPARTY_COUNTER_GENERATED, "Counterparty Counter Generated"),
        (STATE_ACCEPTED, "Accepted"),
        (STATE_REJECTED, "Rejected"),
        (STATE_SIGNED, "Signed"),
    ]

    TIMELINE_STATES = [
        STATE_UPLOADED,
        STATE_ANALYZING,
        STATE_REVIEW_READY,
        STATE_COUNTER_DRAFT_READY,
        STATE_VERSION_CREATED,
        STATE_SENT_TO_COUNTERPARTY,
        STATE_COUNTERPARTY_VIEWED,
        STATE_COUNTERPARTY_REQUESTED_CHANGES,
        STATE_COUNTERPARTY_COUNTER_GENERATED,
        STATE_ACCEPTED,
        STATE_REJECTED,
        STATE_SIGNED,
    ]

    INITIAL_PENDING_STATES = [
        STATE_ANALYZING,
        STATE_REVIEW_READY,
        STATE_COUNTER_DRAFT_READY,
        STATE_VERSION_CREATED,
        STATE_SENT_TO_COUNTERPARTY,
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    current_state = models.CharField(max_length=40, choices=STATE_CHOICES, default=STATE_UPLOADED)
    completed_states = models.JSONField(blank=True, default=list)
    pending_states = models.JSONField(blank=True, default=list)
    state_timestamps = models.JSONField(blank=True, default=dict)
    source_label = models.CharField(blank=True, default="", max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workflow_states",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_states",
    )
    created_version = models.ForeignKey(
        "contracts.ContractVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_states",
    )
    sent_to_counterparty_email = models.EmailField(blank=True, default="")
    counterparty_email = models.EmailField(blank=True, default="")
    counterparty_requested_changes = models.JSONField(blank=True, default=list)
    counterparty_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="counterparty_workflow_states",
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
            models.Index(fields=["contract", "-updated_at"]),
        ]

    def __str__(self):
        return f"WorkflowState({self.id}, {self.current_state})"

    @classmethod
    def timeline_order(cls):
        return list(cls.TIMELINE_STATES)

    def initialize(self):
        now = timezone.now().isoformat()
        self.current_state = self.STATE_UPLOADED
        self.completed_states = [self.STATE_UPLOADED]
        self.pending_states = list(self.INITIAL_PENDING_STATES)
        self.state_timestamps = {self.STATE_UPLOADED: now}
        return self

    def advance_to(self, new_state):
        if new_state not in self.TIMELINE_STATES:
            raise ValueError(f"Unknown workflow state: {new_state}")

        order = self.timeline_order()
        current_index = order.index(self.current_state)
        target_index = order.index(new_state)
        if target_index != current_index + 1:
            raise ValueError(f"Cannot advance workflow from {self.current_state} to {new_state}.")

        self.current_state = new_state
        self.completed_states = order[: target_index + 1]
        self.pending_states = order[target_index + 1 :]
        self.state_timestamps = dict(self.state_timestamps or {})
        self.state_timestamps[new_state] = timezone.now().isoformat()
        return self.current_state

    def mark_state(self, new_state, completed_states=None, pending_states=None):
        if new_state not in self.TIMELINE_STATES:
            raise ValueError(f"Unknown workflow state: {new_state}")

        self.current_state = new_state
        if completed_states is not None:
            self.completed_states = completed_states
        if pending_states is not None:
            self.pending_states = pending_states
        self.state_timestamps = dict(self.state_timestamps or {})
        self.state_timestamps[new_state] = timezone.now().isoformat()
        return self.current_state


class ReviewResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.OneToOneField(
        WorkflowState,
        on_delete=models.CASCADE,
        related_name="review_result",
    )
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_results",
    )
    summary = models.TextField(blank=True, default="")
    identified_risks = models.JSONField(blank=True, default=list)
    unclear_clauses = models.JSONField(blank=True, default=list)
    negotiation_opportunities = models.JSONField(blank=True, default=list)
    suggested_changes = models.JSONField(blank=True, default=list)
    key_terms = models.JSONField(blank=True, default=dict)
    questions = models.JSONField(blank=True, default=list)
    ai_metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"ReviewResult({self.workflow_id})"


class CounterDraft(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_DISCARDED = "discarded"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DISCARDED, "Discarded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(
        WorkflowState,
        on_delete=models.CASCADE,
        related_name="counter_drafts",
    )
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="counter_drafts",
    )
    created_version = models.ForeignKey(
        "contracts.ContractVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_counter_drafts",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    generated_revised_contract = models.TextField(blank=True, default="")
    selected_requested_changes = models.JSONField(blank=True, default=list)
    user_negotiation_instructions = models.TextField(blank=True, default="")
    summary = models.TextField(blank=True, default="")
    concerning_clauses = models.JSONField(blank=True, default=list)
    negotiation_strategy = models.JSONField(blank=True, default=dict)
    ai_metadata = models.JSONField(blank=True, default=dict)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["workflow", "-updated_at"]),
            models.Index(fields=["status", "-updated_at"]),
        ]

    def __str__(self):
        return f"CounterDraft({self.workflow_id}, {self.status})"


class NegotiationComment(models.Model):
    COMMENT_TYPE_GENERAL = "general"
    COMMENT_TYPE_CLARIFICATION = "clarification_request"
    COMMENT_TYPE_CHANGE = "change_request"
    COMMENT_TYPE_RISK = "risk_note"
    COMMENT_TYPE_ACCEPTANCE = "acceptance_note"

    COMMENT_TYPE_CHOICES = [
        (COMMENT_TYPE_GENERAL, "General"),
        (COMMENT_TYPE_CLARIFICATION, "Clarification Request"),
        (COMMENT_TYPE_CHANGE, "Change Request"),
        (COMMENT_TYPE_RISK, "Risk Note"),
        (COMMENT_TYPE_ACCEPTANCE, "Acceptance Note"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(
        WorkflowState,
        on_delete=models.CASCADE,
        related_name="negotiation_comments",
    )
    version = models.ForeignKey(
        "contracts.ContractVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negotiation_comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negotiation_comments",
    )
    comment_type = models.CharField(max_length=40, choices=COMMENT_TYPE_CHOICES, default=COMMENT_TYPE_GENERAL)
    clause_reference = models.CharField(blank=True, default="", max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["workflow", "created_at"]),
            models.Index(fields=["version", "created_at"]),
        ]

    def __str__(self):
        return f"NegotiationComment({self.workflow_id}, {self.comment_type})"


class WorkflowShareLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(
        WorkflowState,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    counterparty_email = models.EmailField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_workflow_share_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workflow", "-created_at"]),
            models.Index(fields=["token"]),
        ]

    def __str__(self):
        return f"WorkflowShareLink({self.workflow_id}, {self.token})"

    @property
    def is_active(self):
        if self.revoked_at is not None:
            return False
        if self.expires_at is None:
            return True
        return self.expires_at >= timezone.now()

    @classmethod
    def default_expires_at(cls):
        return timezone.now() + timedelta(days=7)
