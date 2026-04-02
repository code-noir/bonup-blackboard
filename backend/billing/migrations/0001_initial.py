# backend/billing/migrations/0001_initial.py

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=50, unique=True)),
                ("display_name", models.CharField(max_length=100)),
                ("price_monthly", models.DecimalField(decimal_places=2, max_digits=8)),
                ("price_yearly", models.DecimalField(decimal_places=2, max_digits=8, null=True, blank=True)),
                ("max_active_contracts", models.PositiveIntegerField(null=True, blank=True)),
                ("max_live_sessions_per_month", models.PositiveIntegerField(null=True, blank=True)),
                ("has_lifecycle", models.BooleanField(default=False)),
                ("has_notifications", models.BooleanField(default=False)),
                ("has_negotiation_prep", models.BooleanField(default=False)),
                ("all_templates", models.BooleanField(default=False)),
                ("excluded_categories", models.JSONField(blank=True, default=list)),
                ("templates_per_category", models.PositiveIntegerField(null=True, blank=True)),
                ("ai_tier", models.CharField(
                    choices=[("none", "None"), ("basic", "Basic"), ("advanced", "Advanced"), ("full", "Full")],
                    default="none",
                    max_length=20,
                )),
                ("has_priority_support", models.BooleanField(default=False)),
                ("has_early_access", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["price_monthly"]},
        ),
        migrations.CreateModel(
            name="UserSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="subscription",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("plan", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="subscriptions",
                    to="billing.subscriptionplan",
                )),
                ("status", models.CharField(
                    choices=[
                        ("active", "Active"),
                        ("cancelled", "Cancelled"),
                        ("past_due", "Past Due"),
                        ("trialing", "Trialing"),
                        ("per_contract", "Per Contract"),
                    ],
                    default="active",
                    max_length=20,
                )),
                ("billing_period", models.CharField(
                    choices=[
                        ("monthly", "Monthly"),
                        ("yearly", "Yearly"),
                        ("per_contract", "Per Contract"),
                    ],
                    default="monthly",
                    max_length=20,
                )),
                ("current_period_start", models.DateTimeField()),
                ("current_period_end", models.DateTimeField(null=True, blank=True)),
                ("contracts_used_this_period", models.PositiveIntegerField(default=0)),
                ("live_sessions_used_this_month", models.PositiveIntegerField(default=0)),
                ("stripe_customer_id", models.CharField(blank=True, default="", max_length=255)),
                ("stripe_subscription_id", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="invoices",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("subscription", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="invoices",
                    to="billing.usersubscription",
                )),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed")],
                    default="pending",
                    max_length=20,
                )),
                ("description", models.TextField(blank=True, default="")),
                ("stripe_invoice_id", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(null=True, blank=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
