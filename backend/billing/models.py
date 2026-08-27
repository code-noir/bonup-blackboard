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


class ProductPrice(models.Model):
    class PriceType(models.TextChoices):
        ONE_TIME = "one_time", "One Time"
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="prices",
    )
    price_type = models.CharField(max_length=20, choices=PriceType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product", "price_type", "-effective_from"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="product_price_amount_nonneg",
            ),
        ]

    def clean(self):
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValidationError({"effective_until": "Price end must be after price start."})

    def __str__(self):
        return f"{self.product.slug}: {self.amount} {self.currency} ({self.price_type})"


class ToolProductMetadata(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="tool_metadata",
    )
    tool_slug = models.SlugField(max_length=80, unique=True)
    ai_capable = models.BooleanField(default=False)
    included_storage_bytes = models.PositiveBigIntegerField(default=0)
    included_ai_allowance = models.CharField(max_length=80, blank=True, default="")

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


class ToolEntitlementOrigin(models.TextChoices):
    NATIVE = "native", "Native"
    LEGACY_SUBSCRIPTION = "legacy_subscription", "Legacy Subscription"


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
    origin = models.CharField(
        max_length=40,
        choices=ToolEntitlementOrigin.choices,
        default=ToolEntitlementOrigin.NATIVE,
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


class StorageCapacityGrantOrigin(models.TextChoices):
    PURCHASE = "purchase", "Purchase"
    OPERATOR_ADJUSTMENT = "operator_adjustment", "Operator Adjustment"


class StorageCapacityGrantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


class StorageCapacityGrant(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="storage_capacity_grants",
    )
    capacity_bytes = models.PositiveBigIntegerField()
    origin = models.CharField(
        max_length=40,
        choices=StorageCapacityGrantOrigin.choices,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="storage_capacity_grants",
    )
    source_item = models.ForeignKey(
        PackageItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_capacity_grants",
    )
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StorageCapacityGrantStatus.choices,
        default=StorageCapacityGrantStatus.ACTIVE,
    )
    reason = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-granted_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity_bytes__gt=0),
                name="storage_grant_capacity_pos",
            ),
        ]

    def clean(self):
        if self.origin == StorageCapacityGrantOrigin.PURCHASE and self.product_id is None:
            raise ValidationError({"product": "Purchased storage capacity requires a Storage product."})
        if self.product_id and self.product.product_type != Product.ProductType.STORAGE:
            raise ValidationError({"product": "Storage capacity grants may only reference Storage products."})
        if self.origin == StorageCapacityGrantOrigin.PURCHASE and self.expires_at is not None:
            raise ValidationError({"expires_at": "Purchased storage capacity must not expire."})
        if self.expires_at is not None and self.expires_at <= self.granted_at:
            raise ValidationError({"expires_at": "Grant expiration must be after grant time."})

    def __str__(self):
        return f"{self.user_id}: {self.capacity_bytes} bytes ({self.origin}, {self.status})"


class StoragePurchaseStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class StoragePurchase(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="storage_purchases",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="storage_purchases",
    )
    product_price = models.ForeignKey(
        ProductPrice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="storage_purchases",
    )
    capacity_bytes_snapshot = models.PositiveBigIntegerField()
    capacity_label_snapshot = models.CharField(max_length=120, blank=True, default="")
    price_amount_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    currency_snapshot = models.CharField(max_length=3)
    status = models.CharField(
        max_length=20,
        choices=StoragePurchaseStatus.choices,
        default=StoragePurchaseStatus.PENDING,
    )
    purchased_at = models.DateTimeField(default=timezone.now)
    payment_reference = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    capacity_grant = models.OneToOneField(
        StorageCapacityGrant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="storage_purchase",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-purchased_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity_bytes_snapshot__gt=0),
                name="storage_purchase_capacity_pos",
            ),
            models.CheckConstraint(
                condition=models.Q(price_amount_snapshot__gte=0),
                name="storage_purchase_price_nonneg",
            ),
        ]

    def clean(self):
        if self.product_id and self.product.product_type != Product.ProductType.STORAGE:
            raise ValidationError({"product": "Storage purchases require a Storage product."})
        if self.capacity_grant_id and self.capacity_grant.capacity_bytes != self.capacity_bytes_snapshot:
            raise ValidationError({"capacity_grant": "Storage grant capacity must match the purchase snapshot."})
        if self.capacity_grant_id and self.capacity_grant.origin != StorageCapacityGrantOrigin.PURCHASE:
            raise ValidationError({"capacity_grant": "Storage purchases require purchase-origin capacity grants."})
        if self.capacity_grant_id and self.capacity_grant.expires_at is not None:
            raise ValidationError({"capacity_grant": "Storage purchase grants must not expire."})

    def __str__(self):
        return f"{self.user_id}: {self.product.slug} ({self.status})"


class ProviderStorageCost(models.Model):
    provider = models.CharField(max_length=120)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    physical_capacity_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    stored_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start", "provider"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="provider_storage_cost_nonneg",
            ),
        ]

    def clean(self):
        if self.period_end <= self.period_start:
            raise ValidationError({"period_end": "Provider cost period end must be after period start."})

    def __str__(self):
        return f"{self.provider}: {self.amount} {self.currency}"


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
