# backend/ai/models.py

import uuid

from django.conf import settings
from django.db import models


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
