# backend/billing/models.py

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

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


class Product(models.Model):
    class ProductType(models.TextChoices):
        TOOL = "tool", "Tool"
        STORAGE = "storage", "Storage"
        AI = "ai", "AI"

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    product_type = models.CharField(max_length=20, choices=ProductType.choices)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True, default="")
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    annual_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.slug})"


class ToolProductMetadata(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="tool_metadata",
    )
    tool_slug = models.SlugField(max_length=80, unique=True)
    ai_capable = models.BooleanField(default=False)

    class Meta:
        ordering = ["tool_slug"]

    def clean(self):
        if self.product_id and self.product.product_type != Product.ProductType.TOOL:
            raise ValidationError({"product": "Tool metadata requires a Tool product."})

    def __str__(self):
        return self.tool_slug


class StorageProductMetadata(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="storage_metadata",
    )
    capacity_bytes = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["capacity_bytes"]

    def clean(self):
        if self.product_id and self.product.product_type != Product.ProductType.STORAGE:
            raise ValidationError({"product": "Storage metadata requires a Storage product."})

    def __str__(self):
        return f"{self.product.slug}: {self.capacity_bytes} bytes"


class AIProductMetadata(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="ai_metadata",
    )
    service_level = models.CharField(max_length=80, blank=True, default="")

    def clean(self):
        if self.product_id and self.product.product_type != Product.ProductType.AI:
            raise ValidationError({"product": "AI metadata requires an AI product."})

    def __str__(self):
        return self.product.slug


class CustomerPackage(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CANCELED = "canceled", "Canceled"

    class BillingInterval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="commercial_packages",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="active"),
                name="one_active_customer_package_per_user",
            ),
        ]

    def __str__(self):
        return f"Package {self.id} - {self.user} ({self.status})"


class PackageItem(models.Model):
    package = models.ForeignKey(
        CustomerPackage,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="package_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["package", "product"],
                name="unique_product_per_customer_package",
            ),
        ]

    def __str__(self):
        return f"{self.package_id}: {self.product.slug}"


class CommercialEntitlementStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    EXPIRED = "expired", "Expired"


class ToolEntitlement(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tool_entitlements",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="tool_entitlements",
    )
    status = models.CharField(
        max_length=20,
        choices=CommercialEntitlementStatus.choices,
        default=CommercialEntitlementStatus.ACTIVE,
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    source_item = models.ForeignKey(
        PackageItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tool_entitlements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]

    def clean(self):
        if self.product_id and self.product.product_type != Product.ProductType.TOOL:
            raise ValidationError({"product": "Tool entitlement requires a Tool product."})
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Entitlement end must be after start."})

    def __str__(self):
        return f"{self.user_id}: {self.product.slug} ({self.status})"


class StorageEntitlement(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="storage_entitlements",
    )
    capacity_bytes = models.PositiveBigIntegerField()
    usage_bytes = models.PositiveBigIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=CommercialEntitlementStatus.choices,
        default=CommercialEntitlementStatus.ACTIVE,
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    source_item = models.ForeignKey(
        PackageItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_entitlements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity_bytes__gte=0),
                name="storage_entitlement_capacity_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(usage_bytes__gte=0),
                name="storage_entitlement_usage_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(usage_bytes__lte=models.F("capacity_bytes")),
                name="storage_entitlement_usage_not_above_capacity",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="active"),
                name="one_active_storage_entitlement_per_user",
            ),
        ]

    def clean(self):
        if self.usage_bytes > self.capacity_bytes:
            raise ValidationError({"usage_bytes": "Storage usage cannot exceed capacity."})
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Entitlement end must be after start."})

    def set_usage(self, usage_bytes):
        if usage_bytes < 0:
            raise ValidationError({"usage_bytes": "Storage usage cannot be negative."})
        if usage_bytes > self.capacity_bytes:
            raise ValidationError({"usage_bytes": "Storage usage cannot exceed capacity."})
        self.usage_bytes = usage_bytes

    def add_usage(self, additional_bytes):
        self.set_usage(self.usage_bytes + additional_bytes)

    def __str__(self):
        return f"{self.user_id}: {self.usage_bytes}/{self.capacity_bytes} bytes ({self.status})"


class AIEntitlement(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_entitlements",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="ai_entitlements",
    )
    status = models.CharField(
        max_length=20,
        choices=CommercialEntitlementStatus.choices,
        default=CommercialEntitlementStatus.ACTIVE,
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    source_item = models.ForeignKey(
        PackageItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_entitlements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]

    def clean(self):
        if self.product_id and self.product.product_type != Product.ProductType.AI:
            raise ValidationError({"product": "AI entitlement requires an AI product."})
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Entitlement end must be after start."})

    def __str__(self):
        return f"{self.user_id}: {self.product.slug} ({self.status})"
