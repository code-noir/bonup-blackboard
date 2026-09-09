# backend/uploads/models.py

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Upload(models.Model):

    FILE_TYPE_CHOICES = [
        ("pdf", "PDF"),
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("slides", "Slides"),
        ("document", "Document"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploads",
    )

    file_url = models.CharField(max_length=2048)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.PositiveIntegerField()

    # Storage key — the path within the bucket (used for deletion)
    storage_key = models.CharField(max_length=1024, blank=True)

    stored_object = models.ForeignKey(
        "uploads.StoredObject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploads",
    )

    vault_folder = models.ForeignKey(
        "uploads.VaultFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploads",
    )

    related_contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploads",
    )

    related_session = models.ForeignKey(
        "live_sessions.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploads",
    )

    is_prep_material = models.BooleanField(default=False)
    is_draft_document = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    vault_removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.file_name} ({self.user_id})"


class VaultFolder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vault_folders",
    )
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "parent", "name"],
                condition=models.Q(parent__isnull=False),
                name="vault_folder_user_parent_name_unique",
            ),
            models.UniqueConstraint(
                fields=["user", "name"],
                condition=models.Q(parent__isnull=True),
                name="vault_folder_user_root_name_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "parent"], name="vault_folder_user_parent_idx"),
            models.Index(fields=["parent"], name="vault_folder_parent_idx"),
        ]

    def clean(self):
        super().clean()
        name = self.name.strip() if isinstance(self.name, str) else ""
        if not name:
            raise ValidationError({"name": "Folder name is required."})
        self.name = name

        if self.parent_id is None:
            return
        if self.pk is not None and self.parent_id == self.pk:
            raise ValidationError({"parent": "Folder cannot be its own parent."})
        if self.parent.user_id != self.user_id:
            raise ValidationError({"parent": "Parent folder must belong to the same user."})

        ancestor = self.parent
        while ancestor is not None:
            if self.pk is not None and ancestor.pk == self.pk:
                raise ValidationError({"parent": "Folder cannot be moved inside one of its descendants."})
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.user_id})"


class StoredObject(models.Model):
    """Physical storage identity for a bonUP-managed object.

    StoredObject identifies one physical object known to bonUP. It does not
    represent customer ownership, customer access, Vault visibility, quota
    entitlement, PBVD ownership, contract ownership, retention status, or
    billing status. Those domain references and policies belong in separate
    layers built on top of this physical identity.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backend = models.CharField(max_length=80, default="default")
    bucket = models.CharField(max_length=255, blank=True, default="")
    object_key = models.CharField(max_length=1024)
    size_bytes = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=255, blank=True, default="")
    checksum = models.CharField(max_length=255, blank=True, default="")
    checksum_algorithm = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(size_bytes__gte=0),
                name="stored_object_size_non_negative",
            ),
            models.UniqueConstraint(
                fields=["backend", "bucket", "object_key"],
                name="stored_object_physical_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["backend", "bucket"], name="stored_obj_backend_bucket_idx"),
            models.Index(fields=["object_key"], name="stored_obj_key_idx"),
            models.Index(fields=["created_at"], name="stored_obj_created_idx"),
        ]

    def __str__(self):
        bucket = self.bucket or "<no bucket>"
        return f"{self.backend}:{bucket}:{self.object_key}"


class UserObjectAccess(models.Model):
    """A user's logical relationship to a physical bonUP stored object.

    StoredObject is the physical object. UserObjectAccess is one user's access
    or reference to that object. Removing this row's active access does not mean
    the StoredObject or provider bytes should be deleted. Future quota accounting
    should treat active references with counts_toward_quota=True as candidates
    for customer usage calculations, but this model does not perform quota,
    retention, Vault, PBVD, contract, or billing policy work.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stored_object_accesses",
    )
    stored_object = models.ForeignKey(
        StoredObject,
        on_delete=models.PROTECT,
        related_name="user_accesses",
    )
    is_active = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)
    counts_toward_quota = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "stored_object"],
                name="user_object_access_user_object_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"], name="user_obj_acc_user_active_idx"),
            models.Index(fields=["stored_object", "is_active"], name="user_obj_acc_obj_active_idx"),
            models.Index(fields=["is_visible"], name="user_obj_acc_visible_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}: {self.stored_object_id} ({'active' if self.is_active else 'removed'})"


class VaultShare(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vault_shares",
    )
    stored_object = models.ForeignKey(
        StoredObject,
        on_delete=models.PROTECT,
        related_name="vault_shares",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "revoked_at"], name="vault_share_owner_revoked_idx"),
            models.Index(fields=["stored_object", "revoked_at"], name="vault_share_obj_revoked_idx"),
            models.Index(fields=["expires_at"], name="vault_share_expires_idx"),
        ]

    def __str__(self):
        return f"{self.owner_id}: {self.stored_object_id}"


class VaultEmailDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vault_email_deliveries",
    )
    stored_object = models.ForeignKey(
        StoredObject,
        on_delete=models.PROTECT,
        related_name="email_deliveries",
    )
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    provider = models.CharField(max_length=80)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    idempotency_key = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["sender_user", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="vault_email_delivery_idempotent",
            ),
        ]
        indexes = [
            models.Index(fields=["sender_user", "created_at"], name="vault_email_sender_created_idx"),
            models.Index(fields=["stored_object", "created_at"], name="vault_email_object_created_idx"),
            models.Index(fields=["status", "created_at"], name="vault_email_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.sender_user_id}: {self.recipient_email} ({self.status})"

