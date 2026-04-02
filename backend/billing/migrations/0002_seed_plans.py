# backend/billing/migrations/0002_seed_plans.py
#
# Data migration: seed the five canonical subscription plans.

from django.db import migrations


PLANS = [
    {
        "slug": "per_contract",
        "display_name": "Per Contract",
        "price_monthly": "15.00",
        "price_yearly": None,
        "max_active_contracts": 1,
        "max_live_sessions_per_month": 0,
        "has_lifecycle": False,
        "has_notifications": False,
        "has_negotiation_prep": False,
        "all_templates": True,
        "excluded_categories": [],
        "templates_per_category": None,
        "ai_tier": "none",
        "has_priority_support": False,
        "has_early_access": False,
        "is_active": True,
    },
    {
        "slug": "starter",
        "display_name": "Starter",
        "price_monthly": "10.00",
        "price_yearly": "100.00",
        "max_active_contracts": 3,
        "max_live_sessions_per_month": 1,
        "has_lifecycle": True,
        "has_notifications": True,
        "has_negotiation_prep": True,
        "all_templates": False,
        "excluded_categories": [],
        "templates_per_category": 1,
        "ai_tier": "none",
        "has_priority_support": False,
        "has_early_access": False,
        "is_active": True,
    },
    {
        "slug": "professional",
        "display_name": "Professional",
        "price_monthly": "83.00",
        "price_yearly": None,
        "max_active_contracts": None,
        "max_live_sessions_per_month": 20,
        "has_lifecycle": True,
        "has_notifications": True,
        "has_negotiation_prep": True,
        "all_templates": True,
        "excluded_categories": [],
        "templates_per_category": None,
        "ai_tier": "basic",
        "has_priority_support": False,
        "has_early_access": False,
        "is_active": True,
    },
    {
        "slug": "business",
        "display_name": "Business",
        "price_monthly": "200.00",
        "price_yearly": None,
        "max_active_contracts": None,
        "max_live_sessions_per_month": 60,
        "has_lifecycle": True,
        "has_notifications": True,
        "has_negotiation_prep": True,
        "all_templates": True,
        "excluded_categories": [],
        "templates_per_category": None,
        "ai_tier": "advanced",
        "has_priority_support": False,
        "has_early_access": False,
        "is_active": True,
    },
    {
        "slug": "anchor",
        "display_name": "Anchor",
        "price_monthly": "600.00",
        "price_yearly": None,
        "max_active_contracts": None,
        "max_live_sessions_per_month": None,
        "has_lifecycle": True,
        "has_notifications": True,
        "has_negotiation_prep": True,
        "all_templates": True,
        "excluded_categories": [],
        "templates_per_category": None,
        "ai_tier": "full",
        "has_priority_support": True,
        "has_early_access": True,
        "is_active": True,
    },
]


def seed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    for plan_data in PLANS:
        SubscriptionPlan.objects.get_or_create(
            slug=plan_data["slug"],
            defaults=plan_data,
        )


def unseed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    slugs = [p["slug"] for p in PLANS]
    SubscriptionPlan.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_plans, reverse_code=unseed_plans),
    ]
