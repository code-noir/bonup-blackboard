import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_bon_id_invariants"),
        ("uploads", "0010_upload_vault_removed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="bonuserprofile",
            name="profile_photo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="profile_photo_profiles",
                to="uploads.upload",
            ),
        ),
        migrations.AddField(
            model_name="bonuserprofile",
            name="profile_photo_visible",
            field=models.BooleanField(default=True),
        ),
    ]
