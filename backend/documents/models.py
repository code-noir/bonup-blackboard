# backend/documents/models.py

import uuid

from django.conf import settings
from django.db import models


class ContractDocument(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="contract_documents",
    )

    upload = models.ForeignKey(
        "uploads.Upload",
        on_delete=models.CASCADE,
        related_name="contract_documents",
    )

    attached_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="attached_documents",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_proof = models.BooleanField(default=False)
    attached_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attached_at"]

    def __str__(self):
        return f"{self.title} — {self.contract_id}"
