# Generated for Operator authentication and View-As foundation.

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OperatorViewAsSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("operator_user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operator_view_as_sessions", to=settings.AUTH_USER_MODEL)),
                ("target_user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viewed_by_operator_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-started_at"],
                "permissions": [
                    ("access_operator_console", "Can access Operator Console"),
                    ("view_as_user", "Can view as a user"),
                    ("view_as_operator", "Can view as an operator account"),
                ],
            },
        ),
        migrations.CreateModel(
            name="OperatorAuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(choices=[("operator_login", "Operator login"), ("view_as_started", "View-As started"), ("view_as_ended", "View-As ended")], max_length=64)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("operator_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operator_audit_events", to=settings.AUTH_USER_MODEL)),
                ("target_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="targeted_operator_audit_events", to=settings.AUTH_USER_MODEL)),
                ("view_as_session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="operator.operatorviewassession")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="operatorviewassession",
            index=models.Index(fields=["operator_user", "-started_at"], name="operator_view_operator_idx"),
        ),
        migrations.AddIndex(
            model_name="operatorviewassession",
            index=models.Index(fields=["target_user", "-started_at"], name="operator_view_target_idx"),
        ),
        migrations.AddIndex(
            model_name="operatorviewassession",
            index=models.Index(fields=["ended_at", "expires_at"], name="operator_view_active_idx"),
        ),
        migrations.AddIndex(
            model_name="operatorauditevent",
            index=models.Index(fields=["operator_user", "-created_at"], name="operator_audit_operator_idx"),
        ),
        migrations.AddIndex(
            model_name="operatorauditevent",
            index=models.Index(fields=["target_user", "-created_at"], name="operator_audit_target_idx"),
        ),
        migrations.AddIndex(
            model_name="operatorauditevent",
            index=models.Index(fields=["action", "-created_at"], name="operator_audit_action_idx"),
        ),
    ]
