# backend/billing/storage.py
#
# Deterministic storage capacity accounting for customer entitlement,
# customer usage, and future platform capacity reporting. Provider
# provisioning and financial ledgers are intentionally outside this module.

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .commercial import has_tool, validate_storage_product
from .models import (
    CommercialEntitlementStatus,
    Product,
    StorageCapacityGrant,
    StorageCapacityGrantOrigin,
    StorageCapacityGrantStatus,
    StorageEntitlement,
    StorageProductMetadata,
    ToolEntitlement,
)

GIB = 1024 ** 3
BLACKBOD_TOOL_SLUG = "blackbod"
BLACKBOD_INCLUDED_STORAGE_BYTES = 8 * GIB
BLACKBOD_INCLUDED_AI_ALLOWANCE = "starter"
LAUNCH_STORAGE_PRODUCTS = {
    "storage-8gb": 8 * GIB,
    "storage-88gb": 88 * GIB,
    "storage-288gb": 288 * GIB,
}
LAUNCH_PROACTIVE_STORAGE_CAPACITY_BYTES = frozenset({
    LAUNCH_STORAGE_PRODUCTS["storage-8gb"],
    LAUNCH_STORAGE_PRODUCTS["storage-88gb"],
})
STORAGE_RESERVE_BYTES = 8 * GIB


@dataclass(frozen=True)
class StorageCapacitySnapshot:
    entitled_bytes: int
    used_bytes: int
    remaining_bytes: int


@dataclass(frozen=True)
class StoragePurchaseEligibility:
    eligible: bool
    reason: str
    entitled_bytes: int
    used_bytes: int
    remaining_bytes: int
    declared_upcoming_need_bytes: int
    recommended_capacity_bytes: int | None
    maximum_purchase_bytes: int
    eligible_capacity_bytes: tuple[int, ...]


@dataclass(frozen=True)
class StorageWriteCheck:
    allowed: bool
    reason: str
    entitled_bytes: int
    used_bytes: int
    remaining_bytes: int
    incoming_bytes: int


@dataclass(frozen=True)
class PlatformStorageCapacityReport:
    total_customer_entitled_bytes: int
    total_customer_used_bytes: int
    physical_capacity_bytes: int | None = None


def validate_non_negative_bytes(value, field_name):
    if value < 0:
        raise ValidationError({field_name: "Byte values cannot be negative."})
    return True


def current_storage_capacity_grants(user=None, now=None):
    now = now or timezone.now()
    qs = StorageCapacityGrant.objects.filter(
        status=StorageCapacityGrantStatus.ACTIVE,
        granted_at__lte=now,
    ).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
    if user is not None:
        qs = qs.filter(user=user)
    return qs


def get_active_tool_included_storage_bytes(user, now=None):
    now = now or timezone.now()
    result = ToolEntitlement.objects.filter(
        user=user,
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
        product__tool_metadata__included_storage_bytes__gt=0,
    ).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)
    ).aggregate(total=models.Sum("product__tool_metadata__included_storage_bytes"))
    return result["total"] or 0


def get_granted_storage_capacity_bytes(user, now=None):
    result = current_storage_capacity_grants(user=user, now=now).aggregate(total=models.Sum("capacity_bytes"))
    return result["total"] or 0


def get_entitled_storage_bytes(user, now=None):
    return get_active_tool_included_storage_bytes(user, now=now) + get_granted_storage_capacity_bytes(user, now=now)


def get_used_storage_bytes(user, now=None):
    now = now or timezone.now()
    entitlement = StorageEntitlement.objects.filter(
        user=user,
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
    ).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)
    ).order_by("-starts_at").first()
    return entitlement.usage_bytes if entitlement else 0


def get_storage_capacity_snapshot(user, now=None):
    entitled_bytes = get_entitled_storage_bytes(user, now=now)
    used_bytes = get_used_storage_bytes(user, now=now)
    return StorageCapacitySnapshot(
        entitled_bytes=entitled_bytes,
        used_bytes=used_bytes,
        remaining_bytes=max(0, entitled_bytes - used_bytes),
    )


def can_store_bytes(user, incoming_bytes, now=None):
    validate_non_negative_bytes(incoming_bytes, "incoming_bytes")
    snapshot = get_storage_capacity_snapshot(user, now=now)
    allowed = snapshot.used_bytes + incoming_bytes <= snapshot.entitled_bytes
    return StorageWriteCheck(
        allowed=allowed,
        reason="within_entitlement" if allowed else "exceeds_entitlement",
        entitled_bytes=snapshot.entitled_bytes,
        used_bytes=snapshot.used_bytes,
        remaining_bytes=snapshot.remaining_bytes,
        incoming_bytes=incoming_bytes,
    )


def evaluate_storage_purchase_eligibility(
    user,
    requested_capacity_bytes,
    declared_upcoming_need_bytes=0,
    now=None,
):
    validate_non_negative_bytes(requested_capacity_bytes, "requested_capacity_bytes")
    validate_non_negative_bytes(declared_upcoming_need_bytes, "declared_upcoming_need_bytes")

    snapshot = get_storage_capacity_snapshot(user, now=now)
    projected_required_bytes = snapshot.used_bytes + declared_upcoming_need_bytes
    target_bytes = projected_required_bytes + STORAGE_RESERVE_BYTES
    needed_extra_bytes = max(0, target_bytes - snapshot.entitled_bytes)
    launch_capacities = tuple(sorted(LAUNCH_STORAGE_PRODUCTS.values()))
    eligible_capacities = tuple(capacity for capacity in launch_capacities if capacity >= needed_extra_bytes)
    recommended_capacity_bytes = eligible_capacities[0] if eligible_capacities else None

    if requested_capacity_bytes not in launch_capacities:
        return StoragePurchaseEligibility(
            eligible=False,
            reason="unsupported_capacity",
            entitled_bytes=snapshot.entitled_bytes,
            used_bytes=snapshot.used_bytes,
            remaining_bytes=snapshot.remaining_bytes,
            declared_upcoming_need_bytes=declared_upcoming_need_bytes,
            recommended_capacity_bytes=recommended_capacity_bytes,
            maximum_purchase_bytes=eligible_capacities[-1] if eligible_capacities else 0,
            eligible_capacity_bytes=eligible_capacities,
        )

    if needed_extra_bytes == 0:
        if has_tool(user, BLACKBOD_TOOL_SLUG, now=now) and requested_capacity_bytes in LAUNCH_PROACTIVE_STORAGE_CAPACITY_BYTES:
            return StoragePurchaseEligibility(
                eligible=True,
                reason="proactive_capacity_available",
                entitled_bytes=snapshot.entitled_bytes,
                used_bytes=snapshot.used_bytes,
                remaining_bytes=snapshot.remaining_bytes,
                declared_upcoming_need_bytes=declared_upcoming_need_bytes,
                recommended_capacity_bytes=None,
                maximum_purchase_bytes=max(LAUNCH_PROACTIVE_STORAGE_CAPACITY_BYTES),
                eligible_capacity_bytes=tuple(sorted(LAUNCH_PROACTIVE_STORAGE_CAPACITY_BYTES)),
            )
        return StoragePurchaseEligibility(
            eligible=False,
            reason="sufficient_reserve",
            entitled_bytes=snapshot.entitled_bytes,
            used_bytes=snapshot.used_bytes,
            remaining_bytes=snapshot.remaining_bytes,
            declared_upcoming_need_bytes=declared_upcoming_need_bytes,
            recommended_capacity_bytes=None,
            maximum_purchase_bytes=0,
            eligible_capacity_bytes=(),
        )

    if requested_capacity_bytes < needed_extra_bytes:
        return StoragePurchaseEligibility(
            eligible=False,
            reason="requested_capacity_too_small",
            entitled_bytes=snapshot.entitled_bytes,
            used_bytes=snapshot.used_bytes,
            remaining_bytes=snapshot.remaining_bytes,
            declared_upcoming_need_bytes=declared_upcoming_need_bytes,
            recommended_capacity_bytes=recommended_capacity_bytes,
            maximum_purchase_bytes=eligible_capacities[-1] if eligible_capacities else 0,
            eligible_capacity_bytes=eligible_capacities,
        )

    return StoragePurchaseEligibility(
        eligible=True,
        reason="capacity_needed",
        entitled_bytes=snapshot.entitled_bytes,
        used_bytes=snapshot.used_bytes,
        remaining_bytes=snapshot.remaining_bytes,
        declared_upcoming_need_bytes=declared_upcoming_need_bytes,
        recommended_capacity_bytes=recommended_capacity_bytes,
        maximum_purchase_bytes=eligible_capacities[-1] if eligible_capacities else requested_capacity_bytes,
        eligible_capacity_bytes=eligible_capacities,
    )


def create_storage_capacity_grant(
    *,
    user,
    capacity_bytes,
    origin,
    product=None,
    source_item=None,
    granted_at=None,
    expires_at=None,
    status=StorageCapacityGrantStatus.ACTIVE,
    reason="",
    metadata=None,
):
    grant = StorageCapacityGrant(
        user=user,
        capacity_bytes=capacity_bytes,
        origin=origin,
        product=product,
        source_item=source_item,
        granted_at=granted_at or timezone.now(),
        expires_at=expires_at,
        status=status,
        reason=reason,
        metadata=metadata or {},
    )
    validate_storage_capacity_grant(grant)
    grant.save()
    return grant


def validate_storage_capacity_grant(grant):
    if grant.capacity_bytes <= 0:
        raise ValidationError({"capacity_bytes": "Storage capacity grants must be positive."})
    if grant.origin not in StorageCapacityGrantOrigin.values:
        raise ValidationError({"origin": "Unsupported storage capacity grant origin."})
    if grant.origin == StorageCapacityGrantOrigin.PURCHASE and grant.product_id is None:
        raise ValidationError({"product": "Purchased storage capacity requires a Storage product."})
    if grant.product_id is not None:
        validate_storage_product(grant.product, require_active=False)
    if grant.origin == StorageCapacityGrantOrigin.PURCHASE and grant.expires_at is not None:
        raise ValidationError({"expires_at": "Purchased storage capacity must not expire."})
    if grant.expires_at is not None and grant.expires_at <= grant.granted_at:
        raise ValidationError({"expires_at": "Grant expiration must be after grant time."})
    return True


def get_launch_storage_products():
    return Product.objects.filter(
        slug__in=LAUNCH_STORAGE_PRODUCTS.keys(),
        product_type=Product.ProductType.STORAGE,
    ).select_related("storage_metadata").order_by("storage_metadata__capacity_bytes")


def get_platform_storage_capacity_report(now=None):
    now = now or timezone.now()
    active_user_ids = set(ToolEntitlement.objects.filter(
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
        product__tool_metadata__included_storage_bytes__gt=0,
    ).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)
    ).values_list("user_id", flat=True))
    active_user_ids.update(current_storage_capacity_grants(now=now).values_list("user_id", flat=True))

    total_entitled = 0
    total_used = 0
    user_model = ToolEntitlement._meta.get_field("user").remote_field.model
    for user in user_model.objects.filter(id__in=active_user_ids):
        snapshot = get_storage_capacity_snapshot(user, now=now)
        total_entitled += snapshot.entitled_bytes
        total_used += snapshot.used_bytes

    return PlatformStorageCapacityReport(
        total_customer_entitled_bytes=total_entitled,
        total_customer_used_bytes=total_used,
        physical_capacity_bytes=None,
    )


def user_has_blackbod_included_storage(user, now=None):
    return has_tool(user, BLACKBOD_TOOL_SLUG, now=now)
