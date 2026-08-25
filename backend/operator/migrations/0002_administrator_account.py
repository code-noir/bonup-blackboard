# Generated for dedicated bonUP AdministratorAccount identity.

import django.db.models.deletion
from django.db import migrations, models
from django.contrib.auth.hashers import make_password


def preserve_legacy_operator_rows(apps, schema_editor):
    AdministratorAccount = apps.get_model("operator", "AdministratorAccount")
    User = apps.get_model("auth", "User")
    OperatorViewAsSession = apps.get_model("operator", "OperatorViewAsSession")
    OperatorAuditEvent = apps.get_model("operator", "OperatorAuditEvent")

    ids = set(
        OperatorViewAsSession.objects.exclude(operator_user_id=None).values_list("operator_user_id", flat=True)
    )
    ids.update(
        OperatorAuditEvent.objects.exclude(operator_user_id=None).values_list("operator_user_id", flat=True)
    )

    unusable_password = make_password(None)
    for user_id in sorted(ids):
        if AdministratorAccount.objects.filter(pk=user_id).exists():
            continue
        first_name = ""
        last_name = ""
        try:
            user = User.objects.get(pk=user_id)
            first_name = user.first_name or ""
            last_name = user.last_name or ""
        except User.DoesNotExist:
            pass
        AdministratorAccount.objects.create(
            id=user_id,
            email=f"legacy-operator-user-{user_id}@invalid.bonup.local",
            password=unusable_password,
            first_name=first_name,
            last_name=last_name,
            is_active=False,
            is_super_admin=False,
            can_view_as_user=False,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("operator", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdministratorAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password", models.CharField(max_length=128)),
                ("first_name", models.CharField(blank=True, default="", max_length=150)),
                ("last_name", models.CharField(blank=True, default="", max_length=150)),
                ("is_active", models.BooleanField(default=True)),
                ("is_super_admin", models.BooleanField(default=False)),
                ("can_view_as_user", models.BooleanField(default=False)),
                ("last_login_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["email"],
            },
        ),
        migrations.AddIndex(
            model_name="administratoraccount",
            index=models.Index(fields=["email"], name="operator_admin_email_idx"),
        ),
        migrations.AddIndex(
            model_name="administratoraccount",
            index=models.Index(fields=["is_active"], name="operator_admin_active_idx"),
        ),
        migrations.RunPython(preserve_legacy_operator_rows, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name="operatorviewassession",
            name="operator_view_operator_idx",
        ),
        migrations.RemoveIndex(
            model_name="operatorauditevent",
            name="operator_audit_operator_idx",
        ),
        migrations.RenameField(
            model_name="operatorviewassession",
            old_name="operator_user",
            new_name="administrator",
        ),
        migrations.RenameField(
            model_name="operatorauditevent",
            old_name="operator_user",
            new_name="administrator",
        ),
        migrations.AlterField(
            model_name="operatorviewassession",
            name="administrator",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="view_as_sessions", to="operator.administratoraccount"),
        ),
        migrations.AlterField(
            model_name="operatorauditevent",
            name="administrator",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="operator.administratoraccount"),
        ),
        migrations.AddIndex(
            model_name="operatorviewassession",
            index=models.Index(fields=["administrator", "-started_at"], name="operator_view_operator_idx"),
        ),
        migrations.AddIndex(
            model_name="operatorauditevent",
            index=models.Index(fields=["administrator", "-created_at"], name="operator_audit_operator_idx"),
        ),
        migrations.AlterModelOptions(
            name="operatorviewassession",
            options={
                "ordering": ["-started_at"],
                "permissions": [
                    ("access_operator_console", "Can access Operator Console"),
                    ("view_as_user", "Can view as a user"),
                ],
            },
        ),
    ]
