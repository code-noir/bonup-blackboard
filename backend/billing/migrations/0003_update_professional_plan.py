# backend/billing/migrations/0003_update_professional_plan.py
#
# Data migration: update professional plan — all_templates True, no excluded categories.

from django.db import migrations


def update_professional(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug="professional").update(
        all_templates=True,
        excluded_categories=[],
    )


def revert_professional(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug="professional").update(
        all_templates=False,
        excluded_categories=["creative_services"],
    )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_seed_plans"),
    ]

    operations = [
        migrations.RunPython(update_professional, reverse_code=revert_professional),
    ]
