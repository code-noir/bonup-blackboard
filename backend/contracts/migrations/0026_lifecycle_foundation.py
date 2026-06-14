# Generated for signed contract lifecycle foundation

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("agreement_exchange", "0002_restart_fields"),
        ("contracts", "0025_fix_lawwn_entity"),
    ]

    operations = [
        migrations.CreateModel(
            name="LifecycleAgreement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("active", "Active"), ("completed", "Completed"), ("archived", "Archived")], default="active", max_length=20)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("contract", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="lifecycle_agreement", to="contracts.contract")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_lifecycle_agreements", to=settings.AUTH_USER_MODEL)),
                ("signed_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lifecycle_agreements", to="contracts.contractversion")),
                ("source_exchange", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_agreements", to="agreement_exchange.agreementexchange")),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="LifecycleEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("lifecycle_agreement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="contracts.lifecycleagreement")),
            ],
            options={
                "ordering": ["-occurred_at", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="LifecycleItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("item_type", models.CharField(choices=[("obligation", "Obligation"), ("payment", "Payment"), ("deadline", "Deadline"), ("service", "Service"), ("risk", "Risk"), ("note", "Note")], max_length=20)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("responsible_party", models.CharField(blank=True, default="", max_length=255)),
                ("beneficiary_party", models.CharField(blank=True, default="", max_length=255)),
                ("due_date", models.DateTimeField(blank=True, null=True)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("recurrence", models.CharField(blank=True, max_length=100, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("overdue", "Overdue"), ("cancelled", "Cancelled")], default="pending", max_length=20)),
                ("source_clause", models.TextField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lifecycle_agreement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="contracts.lifecycleagreement")),
            ],
            options={
                "ordering": ["due_date", "created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="lifecycleevent",
            index=models.Index(fields=["lifecycle_agreement", "event_type"], name="contracts_l_lifecyc_9aca54_idx"),
        ),
        migrations.AddIndex(
            model_name="lifecycleitem",
            index=models.Index(fields=["lifecycle_agreement", "item_type"], name="contracts_l_lifecyc_4c36b4_idx"),
        ),
        migrations.AddIndex(
            model_name="lifecycleitem",
            index=models.Index(fields=["status", "due_date"], name="contracts_l_status_e2c12a_idx"),
        ),
    ]
