# backend/billing/commercial.py
#
# Platform commercial package services. This module is intentionally separate
# from legacy Blackbòd billing gates during the package architecture migration.

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .models import (
    AIEntitlement,
    AIProductMetadata,
    CommercialEntitlementStatus,
    CustomerPackage,
    PackageItem,
    Product,
    StorageEntitlement,
    StorageProductMetadata,
    ToolEntitlement,
    ToolProductMetadata,
)


def _is_active_status(status):
    return status == CommercialEntitlementStatus.ACTIVE


def _is_currently_active(record, now=None):
    now = now or timezone.now()
    return (
        _is_active_status(record.status)
        and record.starts_at <= now
        and (record.ends_at is None or record.ends_at > now)
    )


def validate_temporal_interval(starts_at, ends_at):
    if ends_at is not None and ends_at <= starts_at:
        raise ValidationError({"ends_at": "Entitlement end must be after start."})
    return True


def validate_tool_product(product, *, require_active=False):
    if product.product_type != Product.ProductType.TOOL:
        raise ValidationError({"product": "Tool entitlement requires a Tool product."})
    if require_active and not product.active:
        raise ValidationError({"product": "Inactive products cannot be activated."})
    if not ToolProductMetadata.objects.filter(product=product).exists():
        raise ValidationError({"product": "Tool products require tool metadata."})
    return True


def validate_storage_product(product, *, require_active=False):
    if product.product_type != Product.ProductType.STORAGE:
        raise ValidationError({"product": "Storage products require storage metadata."})
    if require_active and not product.active:
        raise ValidationError({"product": "Inactive products cannot be activated."})
    if not StorageProductMetadata.objects.filter(product=product).exists():
        raise ValidationError({"product": "Storage products require storage metadata."})
    return True


def validate_ai_product(product, *, require_active=False):
    if product.product_type != Product.ProductType.AI:
        raise ValidationError({"product": "AI entitlement requires an AI product."})
    if require_active and not product.active:
        raise ValidationError({"product": "Inactive products cannot be activated."})
    if not AIProductMetadata.objects.filter(product=product).exists():
        raise ValidationError({"product": "AI products require AI metadata."})
    return True


def validate_product_metadata(product):
    if product.product_type == Product.ProductType.TOOL:
        return validate_tool_product(product)
    if product.product_type == Product.ProductType.STORAGE:
        return validate_storage_product(product)
    if product.product_type == Product.ProductType.AI:
        return validate_ai_product(product)
    raise ValidationError({"product_type": "Unsupported product type."})


def validate_package(package, *, target_status=None):
    effective_status = target_status or package.status
    activating = effective_status == CustomerPackage.Status.ACTIVE
    items = list(
        PackageItem.objects
        .filter(package=package)
        .select_related("product")
    )
    product_ids = [item.product_id for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationError({"items": "A package cannot contain duplicate products."})

    has_ai_product = False
    has_ai_capable_tool = False
    for item in items:
        product = item.product
        validate_product_metadata(product)
        if activating and not product.active:
            raise ValidationError({"items": "Inactive products cannot be activated in a package."})
        if product.product_type == Product.ProductType.TOOL and product.tool_metadata.ai_capable:
            has_ai_capable_tool = True
        if product.product_type == Product.ProductType.AI:
            has_ai_product = True

    if activating and has_ai_product and not has_ai_capable_tool:
        raise ValidationError({"items": "AI requires at least one active AI-capable Tool in the package."})

    return True


@transaction.atomic
def create_customer_package(
    *,
    user,
    billing_interval=CustomerPackage.BillingInterval.MONTHLY,
    status=CustomerPackage.Status.DRAFT,
    products=None,
):
    package = CustomerPackage(
        user=user,
        billing_interval=billing_interval,
        status=CustomerPackage.Status.DRAFT,
    )
    package.save()
    for product in products or []:
        validate_product_metadata(product)
        PackageItem.objects.create(package=package, product=product)
    if status == CustomerPackage.Status.ACTIVE:
        return activate_package(package)
    package.status = status
    validate_package(package)
    package.save(update_fields=["status", "updated_at"])
    return package


def activate_package(package):
    validate_package(package, target_status=CustomerPackage.Status.ACTIVE)
    package.status = CustomerPackage.Status.ACTIVE
    package.save(update_fields=["status", "updated_at"])
    return package


def has_tool(user, tool_slug, now=None):
    now = now or timezone.now()
    return ToolEntitlement.objects.filter(
        user=user,
        product__tool_metadata__tool_slug=tool_slug,
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
    ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)).exists()


def get_storage_entitlement(user, now=None):
    now = now or timezone.now()
    return StorageEntitlement.objects.filter(
        user=user,
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
    ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)).order_by("-starts_at").first()


def user_has_ai_capable_tool(user, now=None):
    now = now or timezone.now()
    return ToolEntitlement.objects.filter(
        user=user,
        product__tool_metadata__ai_capable=True,
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
    ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)).exists()


def _validate_active_storage_uniqueness(user, *, exclude_pk=None):
    qs = StorageEntitlement.objects.filter(user=user, status=CommercialEntitlementStatus.ACTIVE)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError({"user": "A user may have only one active storage entitlement."})


def validate_tool_entitlement(entitlement, *, require_active_product=True):
    validate_temporal_interval(entitlement.starts_at, entitlement.ends_at)
    if _is_active_status(entitlement.status):
        validate_tool_product(entitlement.product, require_active=require_active_product)
    else:
        validate_tool_product(entitlement.product, require_active=False)
    return True


def validate_storage_entitlement(entitlement):
    validate_temporal_interval(entitlement.starts_at, entitlement.ends_at)
    if entitlement.capacity_bytes < 0:
        raise ValidationError({"capacity_bytes": "Storage capacity cannot be negative."})
    if entitlement.usage_bytes < 0:
        raise ValidationError({"usage_bytes": "Storage usage cannot be negative."})
    if entitlement.usage_bytes > entitlement.capacity_bytes:
        raise ValidationError({"usage_bytes": "Storage usage cannot exceed capacity."})
    if _is_active_status(entitlement.status):
        _validate_active_storage_uniqueness(entitlement.user, exclude_pk=entitlement.pk)
    return True


def validate_ai_entitlement(entitlement, now=None, *, require_active_product=True):
    validate_temporal_interval(entitlement.starts_at, entitlement.ends_at)
    if _is_active_status(entitlement.status):
        validate_ai_product(entitlement.product, require_active=require_active_product)
        if not user_has_ai_capable_tool(entitlement.user, now=now):
            raise ValidationError({"user": "Active AI entitlement requires an active AI-capable Tool entitlement."})
    else:
        validate_ai_product(entitlement.product, require_active=False)
    return True


def create_tool_entitlement(
    *,
    user,
    product,
    status=CommercialEntitlementStatus.ACTIVE,
    starts_at=None,
    ends_at=None,
    source_item=None,
):
    entitlement = ToolEntitlement(
        user=user,
        product=product,
        status=status,
        starts_at=starts_at or timezone.now(),
        ends_at=ends_at,
        source_item=source_item,
    )
    validate_tool_entitlement(entitlement)
    entitlement.save()
    return entitlement


def create_storage_entitlement(
    *,
    user,
    capacity_bytes,
    usage_bytes=0,
    status=CommercialEntitlementStatus.ACTIVE,
    starts_at=None,
    ends_at=None,
    source_item=None,
):
    entitlement = StorageEntitlement(
        user=user,
        capacity_bytes=capacity_bytes,
        usage_bytes=usage_bytes,
        status=status,
        starts_at=starts_at or timezone.now(),
        ends_at=ends_at,
        source_item=source_item,
    )
    validate_storage_entitlement(entitlement)
    entitlement.save()
    return entitlement


def update_storage_entitlement(entitlement, **changes):
    for field, value in changes.items():
        if field not in {"capacity_bytes", "usage_bytes", "status", "starts_at", "ends_at", "source_item"}:
            raise ValidationError({field: "Unsupported storage entitlement update."})
        setattr(entitlement, field, value)
    validate_storage_entitlement(entitlement)
    entitlement.save(update_fields=[*changes.keys(), "updated_at"])
    return entitlement


def create_ai_entitlement(
    *,
    user,
    product,
    status=CommercialEntitlementStatus.ACTIVE,
    starts_at=None,
    ends_at=None,
    source_item=None,
):
    entitlement = AIEntitlement(
        user=user,
        product=product,
        status=status,
        starts_at=starts_at or timezone.now(),
        ends_at=ends_at,
        source_item=source_item,
    )
    validate_ai_entitlement(entitlement)
    entitlement.save()
    return entitlement


def activate_tool_entitlement(entitlement):
    entitlement.status = CommercialEntitlementStatus.ACTIVE
    validate_tool_entitlement(entitlement)
    entitlement.save(update_fields=["status", "updated_at"])
    return entitlement


def activate_storage_entitlement(entitlement):
    entitlement.status = CommercialEntitlementStatus.ACTIVE
    validate_storage_entitlement(entitlement)
    entitlement.save(update_fields=["status", "updated_at"])
    return entitlement


def activate_ai_entitlement(entitlement):
    entitlement.status = CommercialEntitlementStatus.ACTIVE
    validate_ai_entitlement(entitlement)
    entitlement.save(update_fields=["status", "updated_at"])
    return entitlement


def has_ai_access(user, now=None):
    if not user_has_ai_capable_tool(user, now=now):
        return False
    now = now or timezone.now()
    return AIEntitlement.objects.filter(
        user=user,
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
    ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)).exists()
