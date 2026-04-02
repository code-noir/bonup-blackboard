# backend/negotiation_prep/models.py
#
# NegotiationPrep domain:
#   PrepSession  — private workspace owned by a single user, optionally linked to a LiveSession
#   PrepDocument — file reference (URL) attached to a PrepSession
#   PrepNote     — ordered text note attached to a PrepSession
#
# Privacy model:
#   Prep sessions are visible only to their owner.  Both parties of a contract
#   may create independent prep sessions linked to the same LiveSession, but
#   neither can see the other's prep until they choose to broadcast it.

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class PrepSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_session = models.ForeignKey(
        "live_sessions.LiveSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prep_sessions",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="prep_sessions",
    )
    title = models.CharField(max_length=255)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PrepSession '{self.title}' owned by {self.owner_id}"


class PrepDocument(models.Model):
    FILE_TYPE_CHOICES = [
        ("pdf", "PDF"),
        ("image", "Image"),
        ("video", "Video"),
        ("slides", "Slides"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prep_session = models.ForeignKey(
        PrepSession,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    title = models.CharField(max_length=255)
    file_url = models.CharField(max_length=2048)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"PrepDocument '{self.title}' ({self.file_type})"


class PrepNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prep_session = models.ForeignKey(
        PrepSession,
        on_delete=models.CASCADE,
        related_name="note_items",
    )
    content = models.TextField()
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"PrepNote order={self.order} on session {self.prep_session_id}"
