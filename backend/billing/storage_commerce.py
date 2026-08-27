# backend/billing/storage_commerce.py
#
# Storage commerce and accounting services. This module snapshots commercial
# terms at purchase time and does not call payment processors or providers.

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .models import (
    Product,
    ProductPrice,
    ProviderStorageCost,
    StorageCapacityGrantOrigin,
    StoragePurchase,
    StoragePurchaseStatus,
)
from .storage import (
    LAUNCH_STORAGE_PRODUCTS,
    create_storage_capacity_grant,
    evaluate_storage_purchase_eligibility,
    get_platform_storage_capacity_report,
)


@dataclass(frozen=True)
class StoragePurchaseReport:
    completed_storage_purchase_count: int
    completed_storage_revenue: Decimal
    completed_capacity_sold_bytes: int
    refunded_purchase_count: int
    pending_purchase_count: int
    currency: str


@dataclass(frozen=True)
class StorageEconomicsReport:
    completed_storage_revenue: Decimal
    completed_capacity_sold_bytes: int
    total_customer_entitled_bytes: int
    total_customer_used_bytes: int
    provider_cost_total_or_none: Decimal | None
    physical_capacity_bytes_or_none: int | None
    gross_margin_or_none: Decimal | None
    utilization_ratio: Decimal | None
    currency: str


def active_product_prices(product, price_type, now=None, currency=None):
    now = now or timezone.now()
    qs = ProductPrice.objects.filter(
        product=product,
        price_type=price_type,
        active=True,
        effective_from__lte=now,
    ).filter(models.Q(effective_until__isnull=True) | models.Q(effective_until__gt=now))
    if currency is not None:
        qs = qs.filter(currency=currency)
    return qs


def get_active_product_price(product, price_type, now=None, currency=None):
    matching_prices = list(active_product_prices(product, price_type, now=now, currency=currency).order_by("id")[:2])
    if len(matching_prices) == 0:
        return None
    if len(matching_prices) > 1:
        raise ValidationError({"product_price": "Ambiguous active ProductPrice for product, price type, and currency."})
    return matching_prices[0]


def validate_storage_purchase_product(product, *, require_active=True):
    if product.product_type != Product.ProductType.STORAGE:
        raise ValidationError({"product": "Storage purchases require a Storage product."})
    if require_active and not product.active:
        raise ValidationError({"product": "Inactive storage products cannot be purchased."})
    if not hasattr(product, "storage_metadata"):
        raise ValidationError({"product": "Storage purchases require storage metadata."})
    if product.storage_metadata.capacity_bytes not in LAUNCH_STORAGE_PRODUCTS.values():
        raise ValidationError({"product": "Unsupported storage capacity block."})
    return True


@transaction.atomic
def create_storage_purchase(
    *,
    user,
    product,
    declared_upcoming_need_bytes=0,
    payment_reference="",
    metadata=None,
    now=None,
):
    now = now or timezone.now()
    product = Product.objects.select_for_update().select_related("storage_metadata").get(pk=product.pk)
    validate_storage_purchase_product(product, require_active=True)

    price = get_active_product_price(product, ProductPrice.PriceType.ONE_TIME, now=now)
    if price is None:
        raise ValidationError({"product_price": "Storage purchases require an active one-time ProductPrice."})

    capacity_bytes = product.storage_metadata.capacity_bytes
    eligibility = evaluate_storage_purchase_eligibility(
        user,
        capacity_bytes,
        declared_upcoming_need_bytes=declared_upcoming_need_bytes,
        now=now,
    )
    if not eligibility.eligible:
        raise ValidationError({"eligibility": eligibility.reason})

    return StoragePurchase.objects.create(
        user=user,
        product=product,
        product_price=price,
        capacity_bytes_snapshot=capacity_bytes,
        capacity_label_snapshot=product.name,
        price_amount_snapshot=price.amount,
        currency_snapshot=price.currency,
        status=StoragePurchaseStatus.PENDING,
        purchased_at=now,
        payment_reference=payment_reference,
        metadata=metadata or {},
    )


@transaction.atomic
def complete_storage_purchase(purchase, *, now=None):
    now = now or timezone.now()
    purchase = StoragePurchase.objects.select_for_update().select_related("product", "capacity_grant").get(pk=purchase.pk)

    if purchase.status == StoragePurchaseStatus.COMPLETED and purchase.capacity_grant_id is not None:
        return purchase
    if purchase.status not in {StoragePurchaseStatus.PENDING, StoragePurchaseStatus.COMPLETED}:
        raise ValidationError({"status": "Only pending storage purchases can be completed."})

    if purchase.capacity_grant_id is None:
        grant = create_storage_capacity_grant(
            user=purchase.user,
            capacity_bytes=purchase.capacity_bytes_snapshot,
            origin=StorageCapacityGrantOrigin.PURCHASE,
            product=purchase.product,
            granted_at=now,
            expires_at=None,
            reason=f"Storage purchase {purchase.id}",
            metadata={"storage_purchase_id": purchase.id},
        )
        purchase.capacity_grant = grant

    purchase.status = StoragePurchaseStatus.COMPLETED
    purchase.save(update_fields=["status", "capacity_grant", "updated_at"])
    return purchase


@transaction.atomic
def fail_storage_purchase(purchase):
    purchase = StoragePurchase.objects.select_for_update().get(pk=purchase.pk)
    if purchase.capacity_grant_id is not None:
        raise ValidationError({"capacity_grant": "Storage purchase with a capacity grant cannot be failed."})
    purchase.status = StoragePurchaseStatus.FAILED
    purchase.save(update_fields=["status", "updated_at"])
    return purchase


@transaction.atomic
def refund_storage_purchase(purchase):
    purchase = StoragePurchase.objects.select_for_update().get(pk=purchase.pk)
    purchase.status = StoragePurchaseStatus.REFUNDED
    purchase.save(update_fields=["status", "updated_at"])
    return purchase


def get_storage_purchase_report(currency="USD"):
    completed = StoragePurchase.objects.filter(status=StoragePurchaseStatus.COMPLETED, currency_snapshot=currency)
    totals = completed.aggregate(
        revenue=models.Sum("price_amount_snapshot"),
        capacity=models.Sum("capacity_bytes_snapshot"),
    )
    return StoragePurchaseReport(
        completed_storage_purchase_count=completed.count(),
        completed_storage_revenue=totals["revenue"] or Decimal("0.00"),
        completed_capacity_sold_bytes=totals["capacity"] or 0,
        refunded_purchase_count=StoragePurchase.objects.filter(status=StoragePurchaseStatus.REFUNDED, currency_snapshot=currency).count(),
        pending_purchase_count=StoragePurchase.objects.filter(status=StoragePurchaseStatus.PENDING, currency_snapshot=currency).count(),
        currency=currency,
    )


def get_provider_storage_cost_total(currency="USD"):
    qs = ProviderStorageCost.objects.filter(currency=currency)
    if not qs.exists():
        return None
    return qs.aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")


def get_physical_capacity_bytes():
    result = ProviderStorageCost.objects.exclude(physical_capacity_bytes__isnull=True).aggregate(
        total=models.Sum("physical_capacity_bytes")
    )
    return result["total"]


def get_storage_economics_report(currency="USD", now=None):
    purchase_report = get_storage_purchase_report(currency=currency)
    capacity_report = get_platform_storage_capacity_report(now=now)
    provider_cost = get_provider_storage_cost_total(currency=currency)
    physical_capacity = get_physical_capacity_bytes()
    gross_margin = None if provider_cost is None else purchase_report.completed_storage_revenue - provider_cost
    utilization_ratio = None
    if capacity_report.total_customer_entitled_bytes > 0:
        utilization_ratio = Decimal(capacity_report.total_customer_used_bytes) / Decimal(capacity_report.total_customer_entitled_bytes)

    return StorageEconomicsReport(
        completed_storage_revenue=purchase_report.completed_storage_revenue,
        completed_capacity_sold_bytes=purchase_report.completed_capacity_sold_bytes,
        total_customer_entitled_bytes=capacity_report.total_customer_entitled_bytes,
        total_customer_used_bytes=capacity_report.total_customer_used_bytes,
        provider_cost_total_or_none=provider_cost,
        physical_capacity_bytes_or_none=physical_capacity,
        gross_margin_or_none=gross_margin,
        utilization_ratio=utilization_ratio,
        currency=currency,
    )
