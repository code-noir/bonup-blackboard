# Generated for Vault email attachment delivery.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uploads", "0007_vaultshare"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VaultEmailDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=255)),
                ("provider", models.CharField(max_length=80)),
                ("provider_message_id", models.CharField(blank=True, default="", max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")], default="pending", max_length=20)),
                ("idempotency_key", models.CharField(blank=True, default="", max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(blank=True, default="", max_length=80)),
                ("sender_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vault_email_deliveries", to=settings.AUTH_USER_MODEL)),
                ("stored_object", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="email_deliveries", to="uploads.storedobject")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["sender_user", "created_at"], name="vault_email_sender_created_idx"),
                    models.Index(fields=["stored_object", "created_at"], name="vault_email_object_created_idx"),
                    models.Index(fields=["status", "created_at"], name="vault_email_status_created_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(condition=~models.Q(idempotency_key=""), fields=("sender_user", "idempotency_key"), name="vault_email_delivery_idempotent"),
                ],
            },
        ),
    ]
