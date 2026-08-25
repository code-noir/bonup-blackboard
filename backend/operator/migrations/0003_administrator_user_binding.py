# Adds bonUP User binding and explicit legacy placeholder marker.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


LEGACY_EMAIL_PREFIX = "legacy-operator-user-"
LEGACY_EMAIL_SUFFIX = "@invalid.bonup.local"


def mark_legacy_placeholders(apps, schema_editor):
    AdministratorAccount = apps.get_model("operator", "AdministratorAccount")
    placeholders = AdministratorAccount.objects.filter(
        user__isnull=True,
        is_active=False,
        is_super_admin=False,
        can_view_as_user=False,
        email__startswith=LEGACY_EMAIL_PREFIX,
        email__endswith=LEGACY_EMAIL_SUFFIX,
    )
    placeholders.update(is_legacy_placeholder=True)


def unmark_legacy_placeholders(apps, schema_editor):
    AdministratorAccount = apps.get_model("operator", "AdministratorAccount")
    AdministratorAccount.objects.filter(is_legacy_placeholder=True).update(
        is_legacy_placeholder=False
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("operator", "0002_administrator_account"),
    ]

    operations = [
        migrations.AddField(
            model_name="administratoraccount",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="administrator_account",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="administratoraccount",
            name="is_legacy_placeholder",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_legacy_placeholders, unmark_legacy_placeholders),
    ]
