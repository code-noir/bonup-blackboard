# backend/billing/migrations/0004_trial_fields.py
#
# Adds trial_contracts_remaining to UserSubscription and no_subscription status.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0003_update_professional_plan"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersubscription",
            name="trial_contracts_remaining",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="usersubscription",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("cancelled", "Cancelled"),
                    ("past_due", "Past Due"),
                    ("trialing", "Trialing"),
                    ("per_contract", "Per Contract"),
                    ("no_subscription", "No Subscription"),
                ],
                default="active",
                max_length=20,
            ),
        ),
    ]
