# backend/contract_pro/migrations/0003_unique_business_level_permission_rule.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contract_pro", "0002_contractpropermissionrule"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="contractpropermissionrule",
            constraint=models.UniqueConstraint(
                condition=models.Q(contract__isnull=True),
                fields=["grant", "action"],
                name="unique_business_level_permission_per_grant_action",
            ),
        ),
    ]
