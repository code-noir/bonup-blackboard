# backend/billing/migrations/0009_add_trial_plan.py
#
# Data migration: insert (or update) the Free Trial subscription plan.
# has_sol is set here because 0005 added that field after 0002 seeded the plan.

from django.db import migrations

TRIAL_FIELDS = {
    "display_name": "Free Trial",
    "price_monthly": "0.00",
    "price_yearly": None,
    "max_active_contracts": None,
    "max_live_sessions_per_month": 20,
    "has_lifecycle": True,
    "has_notifications": True,
    "has_negotiation_prep": True,
    "all_templates": True,
    "excluded_categories": [],
    "templates_per_category": None,
    "has_sol": True,
    "ai_tier": "advanced",
    "has_priority_support": False,
    "has_early_access": False,
    "is_active": True,
}


def add_trial_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.update_or_create(
        slug="trial",
        defaults=TRIAL_FIELDS,
    )


def remove_trial_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug="trial").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0008_update_plan_prices"),
    ]

    operations = [
        migrations.RunPython(add_trial_plan, reverse_code=remove_trial_plan),
    ]
