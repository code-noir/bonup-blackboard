# backend/uploads/models.py

import uuid

from django.conf import settings
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

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.file_name} ({self.user_id})"


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

