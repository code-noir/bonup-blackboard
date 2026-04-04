from django.db import migrations


def set_has_sol(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug__in=["business", "anchor"]).update(has_sol=True)


def unset_has_sol(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug__in=["business", "anchor"]).update(has_sol=False)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0005_subscriptionplan_has_sol"),
    ]

    operations = [
        migrations.RunPython(set_has_sol, unset_has_sol),
    ]
