# backend/billing/models.py

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class SubscriptionPlan(models.Model):

    AI_TIER_CHOICES = [
        ("none", "None"),
        ("basic", "Basic"),
        ("advanced", "Advanced"),
        ("full", "Full"),
    ]

    slug = models.SlugField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # Limits (null = unlimited)
    max_active_contracts = models.PositiveIntegerField(null=True, blank=True)
    max_live_sessions_per_month = models.PositiveIntegerField(null=True, blank=True)

    # Features
    has_lifecycle = models.BooleanField(default=False)
    has_notifications = models.BooleanField(default=False)
    has_negotiation_prep = models.BooleanField(default=False)

    # Template access
    all_templates = models.BooleanField(default=False)
    excluded_categories = models.JSONField(default=list, blank=True)
    templates_per_category = models.PositiveIntegerField(null=True, blank=True)

    # Sol (rotating savings group)
    has_sol = models.BooleanField(default=False)

    # AI and extras
    ai_tier = models.CharField(max_length=20, choices=AI_TIER_CHOICES, default="none")
    has_priority_support = models.BooleanField(default=False)
    has_early_access = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self):
        return f"{self.display_name} ({self.slug})"


class UserSubscription(models.Model):

    STATUS_CHOICES = [
        ("active", "Active"),
        ("cancelled", "Cancelled"),
        ("past_due", "Past Due"),
        ("trialing", "Trialing"),
        ("per_contract", "Per Contract"),
        ("no_subscription", "No Subscription"),
    ]

    BILLING_PERIOD_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
        ("per_contract", "Per Contract"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    billing_period = models.CharField(
        max_length=20,
        choices=BILLING_PERIOD_CHOICES,
        default="monthly",
    )

    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField(null=True, blank=True)

    # Usage counters (reset on period renewal)
    contracts_used_this_period = models.PositiveIntegerField(default=0)
    live_sessions_used_this_month = models.PositiveIntegerField(default=0)

    # Trial
    trial_contracts_remaining = models.PositiveIntegerField(default=0)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Stripe stubs
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.plan.slug} ({self.status})"


class Invoice(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    description = models.TextField(blank=True, default="")
    stripe_invoice_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice {self.id} — {self.user} — {self.amount} {self.currency} ({self.status})"
