import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class AdministratorAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="administrator_account",
        null=True,
        blank=True,
    )
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_super_admin = models.BooleanField(default=False)
    can_view_as_user = models.BooleanField(default=False)
    is_legacy_placeholder = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["email"]
        indexes = [
            models.Index(fields=["email"], name="operator_admin_email_idx"),
            models.Index(fields=["is_active"], name="operator_admin_active_idx"),
        ]

    @property
    def is_authenticated(self):
        return True

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.email


class OperatorViewAsSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    administrator = models.ForeignKey(
        AdministratorAccount,
        on_delete=models.PROTECT,
        related_name="view_as_sessions",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="viewed_by_operator_sessions",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        permissions = [
            ("access_operator_console", "Can access Operator Console"),
            ("view_as_user", "Can view as a user"),
        ]
        indexes = [
            models.Index(fields=["administrator", "-started_at"], name="operator_view_operator_idx"),
            models.Index(fields=["target_user", "-started_at"], name="operator_view_target_idx"),
            models.Index(fields=["ended_at", "expires_at"], name="operator_view_active_idx"),
        ]

    @property
    def is_active(self):
        return self.ended_at is None and self.expires_at > timezone.now()

    def end(self, *, reason="operator_exit"):
        if self.ended_at is None:
            self.ended_at = timezone.now()
            metadata = dict(self.metadata or {})
            metadata["ended_reason"] = reason
            self.metadata = metadata
            self.save(update_fields=["ended_at", "metadata"])

    def __str__(self):
        return f"{self.administrator_id} viewing {self.target_user_id}"


class OperatorAuditEvent(models.Model):
    ACTION_OPERATOR_LOGIN = "operator_login"
    ACTION_VIEW_AS_STARTED = "view_as_started"
    ACTION_VIEW_AS_ENDED = "view_as_ended"

    ACTION_CHOICES = [
        (ACTION_OPERATOR_LOGIN, "Operator login"),
        (ACTION_VIEW_AS_STARTED, "View-As started"),
        (ACTION_VIEW_AS_ENDED, "View-As ended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    administrator = models.ForeignKey(
        AdministratorAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_operator_audit_events",
    )
    view_as_session = models.ForeignKey(
        OperatorViewAsSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["administrator", "-created_at"], name="operator_audit_operator_idx"),
            models.Index(fields=["target_user", "-created_at"], name="operator_audit_target_idx"),
            models.Index(fields=["action", "-created_at"], name="operator_audit_action_idx"),
        ]

    def __str__(self):
        return f"{self.action} by {self.administrator_id}"
