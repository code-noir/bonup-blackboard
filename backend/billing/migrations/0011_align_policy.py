# backend/billing/migrations/0011_align_policy.py
#
# Data migration: align plan data with confirmed commercial policy.
#
# Changes:
#   1. professional.has_sol = True
#      Sol manager eligibility now starts at Pro (was Business/Anchor only).
#      Confirmed rule: Sol manager requires Pro or higher paid subscription.
#
#   2. starter.max_active_contracts = None  (was 3)
#      Starter plan has unlimited personal contracts.
#      Confirmed rule: Starter = personal only, unlimited contracts.

from django.db import migrations


def align_policy(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    # Sol manager now starts at Pro
    SubscriptionPlan.objects.filter(slug="professional").update(has_sol=True)
    # Starter is unlimited contracts
    SubscriptionPlan.objects.filter(slug="starter").update(max_active_contracts=None)


def revert_policy(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug="professional").update(has_sol=False)
    SubscriptionPlan.objects.filter(slug="starter").update(max_active_contracts=3)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0010_add_sol_member_plan"),
    ]

    operations = [
        migrations.RunPython(align_policy, reverse_code=revert_policy),
    ]
