# backend/billing/migrations/0012_blackbod_launch_tiers.py
#
# Establishes the approved launch-era Blackbòd subscription foundation while
# preserving legacy rows for historical and Stripe compatibility.

from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def _copy_plan_fields(source, overrides):
    fields = {
        "display_name": source.display_name,
        "price_monthly": source.price_monthly,
        "price_yearly": source.price_yearly,
        "max_active_contracts": source.max_active_contracts,
        "max_live_sessions_per_month": source.max_live_sessions_per_month,
        "has_lifecycle": source.has_lifecycle,
        "has_notifications": source.has_notifications,
        "has_negotiation_prep": source.has_negotiation_prep,
        "all_templates": source.all_templates,
        "excluded_categories": source.excluded_categories,
        "templates_per_category": source.templates_per_category,
        "has_sol": source.has_sol,
        "ai_tier": source.ai_tier,
        "has_priority_support": source.has_priority_support,
        "has_early_access": source.has_early_access,
        "is_active": True,
    }
    fields.update(overrides)
    return fields


def establish_blackbod_launch_tiers(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    UserSubscription = apps.get_model("billing", "UserSubscription")

    starter = SubscriptionPlan.objects.filter(slug="starter").first()
    professional = SubscriptionPlan.objects.filter(slug="professional").first()
    business = SubscriptionPlan.objects.filter(slug="business").first()

    if starter is not None:
        basic_fields = _copy_plan_fields(starter, {
            "display_name": "Blackbòd Basic",
            "is_active": True,
        })
        basic, _ = SubscriptionPlan.objects.update_or_create(slug="basic", defaults=basic_fields)
        UserSubscription.objects.filter(plan=starter).update(plan=basic)
        starter.is_active = False
        starter.display_name = "Blackboard Starter (Legacy)"
        starter.save(update_fields=["is_active", "display_name"])

    if professional is not None:
        professional.display_name = "Blackbòd Professional"
        professional.is_active = True
        professional.save(update_fields=["display_name", "is_active"])

    if business is not None:
        advanced_fields = _copy_plan_fields(business, {
            "display_name": "Blackbòd Advanced",
            "has_priority_support": False,
            "has_early_access": False,
            "is_active": True,
        })
        advanced, _ = SubscriptionPlan.objects.update_or_create(slug="advanced", defaults=advanced_fields)
        UserSubscription.objects.filter(plan=business).update(plan=advanced)
        business.is_active = False
        business.display_name = "Blackboard Business (Legacy)"
        business.save(update_fields=["is_active", "display_name"])

    anchor = SubscriptionPlan.objects.filter(slug="anchor").first()
    if anchor is not None:
        anchor.is_active = False
        anchor.display_name = "Blackboard Enterprise (Legacy)"
        anchor.save(update_fields=["is_active", "display_name"])

    trial = SubscriptionPlan.objects.filter(slug="trial").first()
    if trial is not None:
        trial.display_name = "Blackbòd Trial"
        if professional is not None:
            trial.max_active_contracts = professional.max_active_contracts
            trial.max_live_sessions_per_month = professional.max_live_sessions_per_month
            trial.has_lifecycle = professional.has_lifecycle
            trial.has_notifications = professional.has_notifications
            trial.has_negotiation_prep = professional.has_negotiation_prep
            trial.all_templates = professional.all_templates
            trial.excluded_categories = professional.excluded_categories
            trial.templates_per_category = professional.templates_per_category
            trial.has_sol = professional.has_sol
            trial.ai_tier = professional.ai_tier
            trial.has_priority_support = False
            trial.has_early_access = False
        trial.is_active = True
        trial.save()

        now = timezone.now()
        for sub in UserSubscription.objects.filter(status="trialing"):
            start = sub.trial_start or sub.current_period_start or now
            end = sub.trial_end or start + timedelta(days=14)
            sub.plan = trial
            sub.trial_start = start
            sub.trial_end = end
            sub.current_period_start = start
            sub.current_period_end = end
            sub.save(update_fields=[
                "plan",
                "trial_start",
                "trial_end",
                "current_period_start",
                "current_period_end",
                "updated_at",
            ])


def reverse_blackbod_launch_tiers(apps, schema_editor):
    SubscriptionPlan = apps.get_model("billing", "SubscriptionPlan")
    UserSubscription = apps.get_model("billing", "UserSubscription")

    starter = SubscriptionPlan.objects.filter(slug="starter").first()
    business = SubscriptionPlan.objects.filter(slug="business").first()
    basic = SubscriptionPlan.objects.filter(slug="basic").first()
    advanced = SubscriptionPlan.objects.filter(slug="advanced").first()

    if starter is not None and basic is not None:
        UserSubscription.objects.filter(plan=basic).update(plan=starter)
        starter.is_active = True
        starter.display_name = "Blackboard Starter"
        starter.save(update_fields=["is_active", "display_name"])

    if business is not None and advanced is not None:
        UserSubscription.objects.filter(plan=advanced).update(plan=business)
        business.is_active = True
        business.display_name = "Blackboard Business"
        business.save(update_fields=["is_active", "display_name"])

    SubscriptionPlan.objects.filter(slug="professional").update(display_name="Blackboard Pro", is_active=True)
    SubscriptionPlan.objects.filter(slug="anchor").update(display_name="Blackboard Enterprise", is_active=True)
    SubscriptionPlan.objects.filter(slug="trial").update(display_name="Free Trial", is_active=True)
    SubscriptionPlan.objects.filter(slug__in=["basic", "advanced"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0011_align_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersubscription",
            name="trial_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersubscription",
            name="trial_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(establish_blackbod_launch_tiers, reverse_code=reverse_blackbod_launch_tiers),
    ]
