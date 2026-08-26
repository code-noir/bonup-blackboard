# backend/billing/migrations/0016_toolentitlement_origin.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0015_one_active_storage_entitlement"),
    ]

    operations = [
        migrations.AddField(
            model_name="toolentitlement",
            name="origin",
            field=models.CharField(
                choices=[
                    ("native", "Native"),
                    ("legacy_subscription", "Legacy Subscription"),
                ],
                default="native",
                max_length=40,
            ),
        ),
    ]
