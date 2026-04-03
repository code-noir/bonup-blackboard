# backend/uploads/models.py

import uuid

from django.conf import settings
from django.db import models


class Upload(models.Model):

    FILE_TYPE_CHOICES = [
        ("pdf", "PDF"),
        ("image", "Image"),
        ("video", "Video"),
        ("slides", "Slides"),
        ("document", "Document"),
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
