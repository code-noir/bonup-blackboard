# backend/billing/migrations/0007_rename_display_names.py
#
# Data migration: update subscription plan display names to new brand names.

from django.db import migrations

RENAMES = {
    "per_contract": "Pay as you go",
    "starter":      "Blackboard Starter",
    "professional": "Blackboard Pro",
    "business":     "Blackboard Business",
    "anchor":       "Blackboard Premium",
}


def rename_display_names(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    for slug, display_name in RENAMES.items():
        SubscriptionPlan.objects.filter(slug=slug).update(display_name=display_name)


def revert_display_names(apps, schema_editor):
    originals = {
        "per_contract": "Per Contract",
        "starter":      "Starter",
        "professional": "Professional",
        "business":     "Business",
        "anchor":       "Anchor",
    }
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    for slug, display_name in originals.items():
        SubscriptionPlan.objects.filter(slug=slug).update(display_name=display_name)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0006_set_has_sol_on_business_anchor"),
    ]

    operations = [
        migrations.RunPython(rename_display_names, reverse_code=revert_display_names),
    ]
