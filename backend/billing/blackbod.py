# backend/billing/blackbod.py
#
# Compatibility bridge from legacy Blackbòd subscriptions to the bonUP
# commercial Tool entitlement architecture. This is application access only;
# AI and Storage remain separate commercial capabilities.

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .commercial import has_tool, validate_tool_product
from .gates import get_user_subscription, is_trial_valid, normalize_blackbod_tier_slug, trial_end_for_start
from .models import CommercialEntitlementStatus, Product, ToolEntitlement, ToolEntitlementOrigin, UserSubscription

BLACKBOD_TOOL_SLUG = "blackbod"


@dataclass(frozen=True)
class LegacyBlackbodAccess:
    has_access: bool
    starts_at: object | None = None
    ends_at: object | None = None
    source: str | None = None


def get_blackbod_product():
    return Product.objects.get(slug=BLACKBOD_TOOL_SLUG, product_type=Product.ProductType.TOOL)


def get_legacy_blackbod_access(subscription, now=None):
    now = now or timezone.now()
    if subscription is None:
        return LegacyBlackbodAccess(False)

    if subscription.status == "trialing":
        if not is_trial_valid(subscription, now=now):
            return LegacyBlackbodAccess(False)
        starts_at = subscription.trial_start or subscription.current_period_start
        ends_at = subscription.trial_end or trial_end_for_start(starts_at)
        return LegacyBlackbodAccess(True, starts_at=starts_at, ends_at=ends_at, source="legacy_trial")

    if subscription.status != "active":
        return LegacyBlackbodAccess(False)

    if normalize_blackbod_tier_slug(subscription.plan.slug) is None:
        return LegacyBlackbodAccess(False)

    starts_at = subscription.current_period_start or now
    return LegacyBlackbodAccess(
        True,
        starts_at=starts_at,
        ends_at=subscription.current_period_end,
        source="legacy_paid",
    )


def has_legacy_blackbod_access(user, now=None):
    return get_legacy_blackbod_access(get_user_subscription(user), now=now).has_access


def has_blackbod_access(user, now=None):
    if has_tool(user, BLACKBOD_TOOL_SLUG, now=now):
        return True
    return has_legacy_blackbod_access(user, now=now)


def _active_blackbod_tool_entitlements(user):
    return ToolEntitlement.objects.filter(
        user=user,
        product__tool_metadata__tool_slug=BLACKBOD_TOOL_SLUG,
        status=CommercialEntitlementStatus.ACTIVE,
    )


def _current_blackbod_tool_entitlements(user, now=None):
    now = now or timezone.now()
    return _active_blackbod_tool_entitlements(user).filter(
        starts_at__lte=now,
    ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now))


def _legacy_blackbod_tool_entitlements(user):
    return _active_blackbod_tool_entitlements(user).filter(
        origin=ToolEntitlementOrigin.LEGACY_SUBSCRIPTION,
    )


def _current_native_blackbod_tool_entitlements(user, now=None):
    return _current_blackbod_tool_entitlements(user, now=now).exclude(
        origin=ToolEntitlementOrigin.LEGACY_SUBSCRIPTION,
    )


def _end_legacy_blackbod_tool_entitlements(user, ended_at):
    for entitlement in _legacy_blackbod_tool_entitlements(user).select_for_update():
        entitlement.ends_at = ended_at
        entitlement.status = CommercialEntitlementStatus.EXPIRED
        entitlement.save(update_fields=["ends_at", "status", "updated_at"])


@transaction.atomic
def sync_blackbod_tool_entitlement(user, now=None):
    now = now or timezone.now()
    product = get_blackbod_product()
    validate_tool_product(product, require_active=True)
    subscription = UserSubscription.objects.select_related("plan").filter(user=user).first()
    legacy_access = get_legacy_blackbod_access(subscription, now=now)

    if not legacy_access.has_access:
        _end_legacy_blackbod_tool_entitlements(user, now)
        return None

    native_current = _current_native_blackbod_tool_entitlements(user, now=now).order_by("starts_at", "id").first()
    if native_current is not None:
        _end_legacy_blackbod_tool_entitlements(user, now)
        return native_current

    current = list(_legacy_blackbod_tool_entitlements(user).select_for_update().order_by("starts_at", "id"))
    primary = current[0] if current else None
    for duplicate in current[1:]:
        duplicate.ends_at = now
        duplicate.status = CommercialEntitlementStatus.EXPIRED
        duplicate.save(update_fields=["ends_at", "status", "updated_at"])

    starts_at = legacy_access.starts_at or now
    ends_at = legacy_access.ends_at
    if ends_at is not None and ends_at <= starts_at:
        raise ValidationError({"ends_at": "Entitlement end must be after start."})

    if primary is None:
        return ToolEntitlement.objects.create(
            user=user,
            product=product,
            status=CommercialEntitlementStatus.ACTIVE,
            origin=ToolEntitlementOrigin.LEGACY_SUBSCRIPTION,
            starts_at=starts_at,
            ends_at=ends_at,
        )

    update_fields = []
    if primary.product_id != product.id:
        primary.product = product
        update_fields.append("product")
    if primary.status != CommercialEntitlementStatus.ACTIVE:
        primary.status = CommercialEntitlementStatus.ACTIVE
        update_fields.append("status")
    if primary.origin != ToolEntitlementOrigin.LEGACY_SUBSCRIPTION:
        primary.origin = ToolEntitlementOrigin.LEGACY_SUBSCRIPTION
        update_fields.append("origin")
    if primary.starts_at != starts_at:
        primary.starts_at = starts_at
        update_fields.append("starts_at")
    if primary.ends_at != ends_at:
        primary.ends_at = ends_at
        update_fields.append("ends_at")
    if update_fields:
        primary.save(update_fields=[*update_fields, "updated_at"])
    return primary
