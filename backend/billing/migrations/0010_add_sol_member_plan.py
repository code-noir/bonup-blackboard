# backend/billing/migrations/0010_add_sol_member_plan.py
#
# Data migration: insert (or update) the Sol Member subscription plan.
# has_sol is set here because 0005 added that field after 0002 seeded the plan.

from django.db import migrations

SOL_MEMBER_FIELDS = {
    "display_name": "Sol Member",
    "price_monthly": "10.00",
    "price_yearly": None,
    "max_active_contracts": 3,
    "max_live_sessions_per_month": 1,
    "has_lifecycle": True,
    "has_notifications": True,
    "has_negotiation_prep": True,
    "all_templates": False,
    "excluded_categories": [],
    "templates_per_category": 1,
    "ai_tier": "none",
    "has_sol": True,
    "has_priority_support": False,
    "has_early_access": False,
    "is_active": True,
}


def add_sol_member_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.update_or_create(
        slug="sol_member",
        defaults=SOL_MEMBER_FIELDS,
    )


def remove_sol_member_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug="sol_member").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0009_add_trial_plan"),
    ]

    operations = [
        migrations.RunPython(add_sol_member_plan, reverse_code=remove_sol_member_plan),
    ]
