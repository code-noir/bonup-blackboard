# Generated for logical Vault folders.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uploads", "0008_vaultemaildelivery"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VaultFolder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="uploads.vaultfolder")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vault_folders", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["name", "created_at"],
                "indexes": [
                    models.Index(fields=["user", "parent"], name="vault_folder_user_parent_idx"),
                    models.Index(fields=["parent"], name="vault_folder_parent_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("parent__isnull", False)), fields=("user", "parent", "name"), name="vault_folder_user_parent_name_unique"),
                    models.UniqueConstraint(condition=models.Q(("parent__isnull", True)), fields=("user", "name"), name="vault_folder_user_root_name_unique"),
                ],
            },
        ),
        migrations.AddField(
            model_name="upload",
            name="vault_folder",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploads", to="uploads.vaultfolder"),
        ),
    ]
