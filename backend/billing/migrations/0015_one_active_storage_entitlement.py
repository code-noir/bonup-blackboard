# backend/billing/migrations/0015_one_active_storage_entitlement.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0014_seed_blackbod_product"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="storageentitlement",
            constraint=models.UniqueConstraint(
                fields=("user",),
                condition=models.Q(("status", "active")),
                name="one_active_storage_entitlement_per_user",
            ),
        ),
    ]
