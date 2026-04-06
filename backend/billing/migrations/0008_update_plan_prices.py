# backend/billing/migrations/0008_update_plan_prices.py
#
# Data migration: update subscription plan prices to correct values.

from django.db import migrations

NEW_PRICES = {
    "per_contract": "25.00",   # Pay As You Go — per-use fee
    "starter":      "19.00",   # Blackboard Basic
    "professional": "149.00",  # Blackboard Pro
    "business":     "399.00",  # Blackboard Business
    "anchor":       "999.00",  # Blackboard Enterprise
}

OLD_PRICES = {
    "per_contract": "15.00",
    "starter":      "10.00",
    "professional": "83.00",
    "business":     "200.00",
    "anchor":       "600.00",
}


def update_prices(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    for slug, price in NEW_PRICES.items():
        SubscriptionPlan.objects.filter(slug=slug).update(price_monthly=price)


def revert_prices(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    for slug, price in OLD_PRICES.items():
        SubscriptionPlan.objects.filter(slug=slug).update(price_monthly=price)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0007_rename_display_names"),
    ]

    operations = [
        migrations.RunPython(update_prices, reverse_code=revert_prices),
    ]
