# backend/api/tests/test_storage_capacity_foundation.py

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backend.billing.commercial import create_tool_entitlement
from backend.billing.models import (
    AIEntitlement,
    CommercialEntitlementStatus,
    Product,
    StorageCapacityGrant,
    StorageCapacityGrantOrigin,
    StorageEntitlement,
    StorageProductMetadata,
    SubscriptionPlan,
    ToolEntitlement,
    ToolEntitlementOrigin,
    UserSubscription,
)
from backend.billing.storage import (
    BLACKBOD_INCLUDED_AI_ALLOWANCE,
    BLACKBOD_INCLUDED_STORAGE_BYTES,
    GIB,
    LAUNCH_STORAGE_PRODUCTS,
    can_store_bytes,
    create_storage_capacity_grant,
    evaluate_storage_purchase_eligibility,
    get_entitled_storage_bytes,
    get_launch_storage_products,
    get_platform_storage_capacity_report,
    get_storage_capacity_snapshot,
)

from .helpers import make_user


def blackbod_product():
    return Product.objects.get(slug="blackbod")


def storage_product(slug="storage-8gb"):
    return Product.objects.get(slug=slug)


def grant(user, gib, origin=StorageCapacityGrantOrigin.PURCHASE, **kwargs):
    if origin == StorageCapacityGrantOrigin.PURCHASE and "product" not in kwargs:
        kwargs["product"] = storage_product(f"storage-{gib}gb")
    return create_storage_capacity_grant(
        user=user,
        capacity_bytes=gib * GIB,
        origin=origin,
        **kwargs,
    )


def subscribe(user, slug="advanced", status="active"):
    return UserSubscription.objects.create(
        user=user,
        plan=SubscriptionPlan.objects.get(slug=slug),
        status=status,
        billing_period="monthly",
        current_period_start=timezone.now(),
    )


class StorageCapacityFoundationTests(TestCase):
    def test_blackbod_included_storage_definition_is_8_gib(self):
        metadata = blackbod_product().tool_metadata

        self.assertEqual(GIB, 1024 ** 3)
        self.assertEqual(BLACKBOD_INCLUDED_STORAGE_BYTES, 8 * GIB)
        self.assertEqual(metadata.included_storage_bytes, 8 * GIB)
        self.assertEqual(metadata.included_ai_allowance, BLACKBOD_INCLUDED_AI_ALLOWANCE)
        self.assertEqual(metadata.included_ai_allowance, "starter")

    def test_storage_catalog_contains_launch_blocks_only(self):
        products = get_launch_storage_products()

        self.assertEqual(
            set(products.values_list("slug", flat=True)),
            {"storage-8gb", "storage-88gb", "storage-288gb"},
        )
        self.assertEqual(
            set(products.values_list("storage_metadata__capacity_bytes", flat=True)),
            {8 * GIB, 88 * GIB, 288 * GIB},
        )
        self.assertEqual(set(LAUNCH_STORAGE_PRODUCTS.values()), {8 * GIB, 88 * GIB, 288 * GIB})

    def test_storage_products_have_no_invented_price(self):
        for product in get_launch_storage_products():
            self.assertIsNone(product.monthly_price)
            self.assertIsNone(product.annual_price)

    def test_permanent_purchase_grant_has_no_expiration(self):
        user = make_user("storage_perm", "storage_perm@example.com")
        product = storage_product("storage-8gb")

        created = create_storage_capacity_grant(
            user=user,
            capacity_bytes=8 * GIB,
            origin=StorageCapacityGrantOrigin.PURCHASE,
            product=product,
        )

        self.assertIsNone(created.expires_at)

    def test_purchase_grant_with_expiration_is_rejected(self):
        user = make_user("storage_perm_reject", "storage_perm_reject@example.com")

        with self.assertRaises(ValidationError):
            create_storage_capacity_grant(
                user=user,
                capacity_bytes=8 * GIB,
                origin=StorageCapacityGrantOrigin.PURCHASE,
                expires_at=timezone.now() + timedelta(days=1),
            )

    def test_multiple_legitimate_grants_add_together(self):
        user = make_user("storage_add", "storage_add@example.com")
        grant(user, 8)
        grant(user, 88)

        self.assertEqual(get_entitled_storage_bytes(user), 96 * GIB)

    def test_entitled_bytes_include_blackbod_tool_capacity_and_grants(self):
        user = make_user("storage_entitled", "storage_entitled@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        grant(user, 88)

        self.assertEqual(get_entitled_storage_bytes(user), 96 * GIB)

    def test_remaining_bytes_are_calculated_from_entitled_minus_used(self):
        user = make_user("storage_remaining", "storage_remaining@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        StorageEntitlement.objects.create(user=user, capacity_bytes=8 * GIB, usage_bytes=3 * GIB)

        snapshot = get_storage_capacity_snapshot(user)

        self.assertEqual(snapshot.entitled_bytes, 8 * GIB)
        self.assertEqual(snapshot.used_bytes, 3 * GIB)
        self.assertEqual(snapshot.remaining_bytes, 5 * GIB)

    def test_can_store_bytes_allows_file_within_entitlement(self):
        user = make_user("storage_can_store", "storage_can_store@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        StorageEntitlement.objects.create(user=user, capacity_bytes=8 * GIB, usage_bytes=3 * GIB)

        result = can_store_bytes(user, 5 * GIB)

        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "within_entitlement")

    def test_can_store_bytes_rejects_file_exceeding_entitlement(self):
        user = make_user("storage_cannot_store", "storage_cannot_store@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        StorageEntitlement.objects.create(user=user, capacity_bytes=8 * GIB, usage_bytes=3 * GIB)

        result = can_store_bytes(user, 5 * GIB + 1)

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "exceeds_entitlement")

    def test_customer_with_substantial_unused_reserve_cannot_stockpile_large_block(self):
        user = make_user("storage_stockpile", "storage_stockpile@example.com")
        grant(user, 88)
        StorageEntitlement.objects.create(user=user, capacity_bytes=88 * GIB, usage_bytes=10 * GIB)

        result = evaluate_storage_purchase_eligibility(user, 288 * GIB)

        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "sufficient_reserve")
        self.assertEqual(result.maximum_purchase_bytes, 0)

    def test_customer_approaching_capacity_can_become_eligible(self):
        user = make_user("storage_eligible", "storage_eligible@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        StorageEntitlement.objects.create(user=user, capacity_bytes=8 * GIB, usage_bytes=7 * GIB)

        result = evaluate_storage_purchase_eligibility(user, 8 * GIB)

        self.assertTrue(result.eligible)
        self.assertEqual(result.reason, "capacity_needed")
        self.assertEqual(result.recommended_capacity_bytes, 8 * GIB)

    def test_active_blackbod_customer_can_proactively_purchase_ordinary_storage(self):
        user = make_user("storage_proactive", "storage_proactive@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        eight = evaluate_storage_purchase_eligibility(user, 8 * GIB)
        eighty_eight = evaluate_storage_purchase_eligibility(user, 88 * GIB)
        protected = evaluate_storage_purchase_eligibility(user, 288 * GIB)

        self.assertTrue(eight.eligible)
        self.assertEqual(eight.reason, "proactive_capacity_available")
        self.assertTrue(eighty_eight.eligible)
        self.assertEqual(eighty_eight.reason, "proactive_capacity_available")
        self.assertFalse(protected.eligible)
        self.assertEqual(protected.reason, "sufficient_reserve")

    def test_declared_upcoming_need_affects_protected_storage_eligibility(self):
        user = make_user("storage_declared", "storage_declared@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        without_need = evaluate_storage_purchase_eligibility(user, 288 * GIB)
        with_need = evaluate_storage_purchase_eligibility(user, 288 * GIB, declared_upcoming_need_bytes=70 * GIB)

        self.assertFalse(without_need.eligible)
        self.assertEqual(without_need.reason, "sufficient_reserve")
        self.assertTrue(with_need.eligible)
        self.assertEqual(with_need.recommended_capacity_bytes, 88 * GIB)

    def test_declared_legitimate_upcoming_need_can_authorize_capacity_before_upload(self):
        user = make_user("storage_need_before_upload", "storage_need_before_upload@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        result = evaluate_storage_purchase_eligibility(user, 88 * GIB, declared_upcoming_need_bytes=70 * GIB)

        self.assertTrue(result.eligible)
        self.assertEqual(result.used_bytes, 0)
        self.assertEqual(result.declared_upcoming_need_bytes, 70 * GIB)

    def test_repeated_288_gib_stockpiling_is_rejected_when_reserve_is_sufficient(self):
        user = make_user("storage_repeat_288", "storage_repeat_288@example.com")
        grant(user, 288)
        StorageEntitlement.objects.create(user=user, capacity_bytes=288 * GIB, usage_bytes=20 * GIB)

        result = evaluate_storage_purchase_eligibility(user, 288 * GIB)

        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "sufficient_reserve")
        self.assertEqual(result.eligible_capacity_bytes, ())

    def test_storage_products_remain_independent_of_blackbod(self):
        blackbod = blackbod_product()
        storage = storage_product("storage-8gb")

        self.assertEqual(blackbod.product_type, Product.ProductType.TOOL)
        self.assertEqual(storage.product_type, Product.ProductType.STORAGE)
        self.assertNotEqual(blackbod.id, storage.id)
        self.assertTrue(StorageProductMetadata.objects.filter(product=storage).exists())

    def test_storage_grant_does_not_create_ai_entitlement(self):
        user = make_user("storage_no_ai", "storage_no_ai@example.com")
        grant(user, 8)

        self.assertFalse(AIEntitlement.objects.filter(user=user).exists())

    def test_existing_native_blackbod_entitlement_semantics_remain_unchanged(self):
        user = make_user("storage_tool_semantics", "storage_tool_semantics@example.com")
        entitlement = create_tool_entitlement(user=user, product=blackbod_product())

        self.assertEqual(entitlement.origin, ToolEntitlementOrigin.NATIVE)
        self.assertTrue(ToolEntitlement.objects.filter(user=user, product=blackbod_product(), ends_at__isnull=True).exists())

    def test_catalog_seed_does_not_create_customer_storage_grants(self):
        user = make_user("storage_seed_no_grant", "storage_seed_no_grant@example.com")

        self.assertEqual(StorageCapacityGrant.objects.filter(user=user).count(), 0)
        self.assertEqual(StorageEntitlement.objects.filter(user=user).count(), 0)
        self.assertEqual(AIEntitlement.objects.filter(user=user).count(), 0)

    def test_platform_capacity_report_separates_entitlement_usage_and_physical_capacity(self):
        user = make_user("storage_platform_report", "storage_platform_report@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        StorageEntitlement.objects.create(user=user, capacity_bytes=8 * GIB, usage_bytes=2 * GIB)

        report = get_platform_storage_capacity_report()

        self.assertEqual(report.total_customer_entitled_bytes, 8 * GIB)
        self.assertEqual(report.total_customer_used_bytes, 2 * GIB)
        self.assertIsNone(report.physical_capacity_bytes)
    def test_blackbod_included_storage_is_counted_exactly_once(self):
        user = make_user("storage_once", "storage_once@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        self.assertEqual(get_entitled_storage_bytes(user), 8 * GIB)

    def test_storage_capacity_grant_has_no_included_tool_origin(self):
        self.assertNotIn("included_tool", StorageCapacityGrantOrigin.values)
        self.assertEqual(set(StorageCapacityGrantOrigin.values), {"purchase", "operator_adjustment"})

    def test_active_current_blackbod_tool_contributes_included_storage(self):
        user = make_user("storage_tool_active", "storage_tool_active@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        self.assertEqual(get_entitled_storage_bytes(user), 8 * GIB)

    def test_expired_blackbod_tool_contributes_no_included_storage(self):
        user = make_user("storage_tool_expired", "storage_tool_expired@example.com")
        now = timezone.now()
        ToolEntitlement.objects.create(
            user=user,
            product=blackbod_product(),
            starts_at=now - timedelta(days=2),
            ends_at=now - timedelta(days=1),
        )

        self.assertEqual(get_entitled_storage_bytes(user, now=now), 0)

    def test_future_blackbod_tool_contributes_no_included_storage(self):
        user = make_user("storage_tool_future", "storage_tool_future@example.com")
        now = timezone.now()
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), starts_at=now + timedelta(days=1))

        self.assertEqual(get_entitled_storage_bytes(user, now=now), 0)

    def test_inactive_blackbod_tool_contributes_no_included_storage(self):
        user = make_user("storage_tool_inactive", "storage_tool_inactive@example.com")
        ToolEntitlement.objects.create(
            user=user,
            product=blackbod_product(),
            status=CommercialEntitlementStatus.INACTIVE,
        )

        self.assertEqual(get_entitled_storage_bytes(user), 0)

    def test_user_without_blackbod_tool_receives_no_tool_included_storage(self):
        user = make_user("storage_no_tool", "storage_no_tool@example.com")

        self.assertEqual(get_entitled_storage_bytes(user), 0)

    def test_legacy_subscription_without_tool_entitlement_does_not_create_included_storage(self):
        user = make_user("storage_legacy_no_tool", "storage_legacy_no_tool@example.com")
        subscribe(user, "advanced", status="active")

        self.assertEqual(get_entitled_storage_bytes(user), 0)
        self.assertFalse(StorageCapacityGrant.objects.filter(user=user).exists())

    def test_storage_only_customer_can_store_against_purchase_without_blackbod(self):
        user = make_user("storage_only", "storage_only@example.com")
        grant(user, 8)

        self.assertEqual(get_entitled_storage_bytes(user), 8 * GIB)
        self.assertTrue(can_store_bytes(user, 8 * GIB).allowed)
        self.assertFalse(ToolEntitlement.objects.filter(user=user).exists())

    def test_unsupported_storage_purchase_block_is_rejected(self):
        user = make_user("storage_bad_block", "storage_bad_block@example.com")

        result = evaluate_storage_purchase_eligibility(user, 488 * GIB)

        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "unsupported_capacity")

    def test_negative_declared_upcoming_need_is_rejected(self):
        user = make_user("storage_negative_need", "storage_negative_need@example.com")

        with self.assertRaises(ValidationError):
            evaluate_storage_purchase_eligibility(user, 8 * GIB, declared_upcoming_need_bytes=-1)

    def test_can_store_bytes_exact_entitlement_boundary_is_allowed(self):
        user = make_user("storage_boundary", "storage_boundary@example.com")
        grant(user, 8)

        result = can_store_bytes(user, 8 * GIB)

        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "within_entitlement")

    def test_negative_incoming_bytes_is_rejected(self):
        user = make_user("storage_negative_incoming", "storage_negative_incoming@example.com")

        with self.assertRaises(ValidationError):
            can_store_bytes(user, -1)

    def test_purchase_grant_with_non_storage_product_is_rejected_by_service(self):
        user = make_user("storage_bad_product", "storage_bad_product@example.com")

        with self.assertRaises(ValidationError):
            create_storage_capacity_grant(
                user=user,
                capacity_bytes=8 * GIB,
                origin=StorageCapacityGrantOrigin.PURCHASE,
                product=blackbod_product(),
            )

    def test_storage_entitlement_capacity_bytes_is_not_added_to_entitlement(self):
        user = make_user("storage_ent_capacity_ignored", "storage_ent_capacity_ignored@example.com")
        StorageEntitlement.objects.create(user=user, capacity_bytes=288 * GIB, usage_bytes=1 * GIB)

        snapshot = get_storage_capacity_snapshot(user)

        self.assertEqual(snapshot.entitled_bytes, 0)
        self.assertEqual(snapshot.used_bytes, 1 * GIB)
        self.assertEqual(snapshot.remaining_bytes, 0)
