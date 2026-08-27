# backend/api/tests/test_storage_commerce_foundation.py

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from backend.billing.blackbod import has_blackbod_access
from backend.billing.commercial import create_tool_entitlement
from backend.billing.models import (
    AIEntitlement,
    Product,
    ProductPrice,
    ProviderStorageCost,
    StorageCapacityGrant,
    StorageCapacityGrantOrigin,
    StorageEntitlement,
    StorageProductMetadata,
    StoragePurchase,
    StoragePurchaseStatus,
    SubscriptionPlan,
    ToolEntitlement,
    UserSubscription,
)
from backend.billing.storage import (
    GIB,
    can_store_bytes,
    create_storage_capacity_grant,
    evaluate_storage_purchase_eligibility,
    get_entitled_storage_bytes,
)
from backend.billing.storage_commerce import (
    complete_storage_purchase,
    create_storage_purchase,
    fail_storage_purchase,
    get_storage_economics_report,
    get_storage_purchase_report,
    refund_storage_purchase,
)

from .helpers import make_user


def blackbod_product():
    return Product.objects.get(slug="blackbod")


def storage_product(slug="storage-8gb"):
    return Product.objects.get(slug=slug)


def deactivate_current_one_time_prices(product):
    ProductPrice.objects.filter(
        product=product,
        price_type=ProductPrice.PriceType.ONE_TIME,
        active=True,
    ).update(active=False, effective_until=timezone.now() - timedelta(minutes=1))


def add_price(
    product,
    amount="120.00",
    currency="USD",
    price_type=ProductPrice.PriceType.ONE_TIME,
    active=True,
    effective_from=None,
    effective_until=None,
    deactivate_existing=True,
):
    if deactivate_existing and price_type == ProductPrice.PriceType.ONE_TIME:
        deactivate_current_one_time_prices(product)
    return ProductPrice.objects.create(
        product=product,
        price_type=price_type,
        amount=Decimal(amount),
        currency=currency,
        active=active,
        effective_from=effective_from or timezone.now() - timedelta(minutes=1),
        effective_until=effective_until,
    )


def make_eligible_user(username="storage_buyer", email="storage_buyer@example.com"):
    user = make_user(username, email)
    create_tool_entitlement(user=user, product=blackbod_product())
    StorageEntitlement.objects.create(user=user, capacity_bytes=8 * GIB, usage_bytes=7 * GIB)
    return user


def create_pending_purchase(user=None, product=None, amount="120.00"):
    user = user or make_eligible_user()
    product = product or storage_product("storage-8gb")
    add_price(product, amount)
    return create_storage_purchase(user=user, product=product)


class ProductPriceFoundationTests(TestCase):
    def test_one_time_monthly_and_annual_price_types_are_supported(self):
        self.assertIn(ProductPrice.PriceType.ONE_TIME, ProductPrice.PriceType.values)
        self.assertIn(ProductPrice.PriceType.MONTHLY, ProductPrice.PriceType.values)
        self.assertIn(ProductPrice.PriceType.ANNUAL, ProductPrice.PriceType.values)

    def test_exactly_one_active_one_time_price_resolves_successfully(self):
        user = make_eligible_user("one_price", "one_price@example.com")
        product = storage_product("storage-8gb")
        price = add_price(product, "120.00")

        purchase = create_storage_purchase(user=user, product=product)

        self.assertEqual(purchase.product_price, price)
        self.assertEqual(purchase.price_amount_snapshot, Decimal("120.00"))

    def test_inactive_one_time_price_is_rejected_for_purchase(self):
        user = make_eligible_user("inactive_price", "inactive_price@example.com")
        product = storage_product("storage-8gb")
        add_price(product, active=False)

        with self.assertRaises(ValidationError):
            create_storage_purchase(user=user, product=product)

    def test_no_active_one_time_price_rejects_purchase(self):
        user = make_eligible_user("no_price", "no_price@example.com")
        product = storage_product("storage-8gb")
        deactivate_current_one_time_prices(product)

        with self.assertRaises(ValidationError):
            create_storage_purchase(user=user, product=product)

    def test_monthly_and_annual_prices_do_not_satisfy_storage_purchase_price_requirement(self):
        user = make_eligible_user("recurring_price", "recurring_price@example.com")
        product = storage_product("storage-8gb")
        deactivate_current_one_time_prices(product)
        add_price(product, price_type=ProductPrice.PriceType.MONTHLY)
        add_price(product, price_type=ProductPrice.PriceType.ANNUAL)

        with self.assertRaises(ValidationError):
            create_storage_purchase(user=user, product=product)

    def test_overlapping_active_one_time_prices_reject_purchase_as_ambiguous(self):
        user = make_eligible_user("ambiguous_price", "ambiguous_price@example.com")
        product = storage_product("storage-8gb")
        add_price(product, "120.00", effective_from=timezone.now() - timedelta(days=2))
        add_price(product, "130.00", effective_from=timezone.now() - timedelta(days=1), deactivate_existing=False)

        with self.assertRaisesMessage(ValidationError, "Ambiguous active ProductPrice"):
            create_storage_purchase(user=user, product=product)

    def test_future_price_does_not_conflict_with_current_price(self):
        user = make_eligible_user("future_price", "future_price@example.com")
        product = storage_product("storage-8gb")
        current_price = add_price(product, "120.00", effective_from=timezone.now() - timedelta(days=1))
        add_price(product, "130.00", effective_from=timezone.now() + timedelta(days=1), deactivate_existing=False)

        purchase = create_storage_purchase(user=user, product=product)

        self.assertEqual(purchase.product_price, current_price)
        self.assertEqual(purchase.price_amount_snapshot, Decimal("120.00"))

    def test_expired_price_does_not_conflict_with_current_price(self):
        user = make_eligible_user("expired_price", "expired_price@example.com")
        product = storage_product("storage-8gb")
        add_price(
            product,
            "110.00",
            effective_from=timezone.now() - timedelta(days=3),
            effective_until=timezone.now() - timedelta(days=2),
        )
        current_price = add_price(product, "120.00", effective_from=timezone.now() - timedelta(days=1))

        purchase = create_storage_purchase(user=user, product=product)

        self.assertEqual(purchase.product_price, current_price)
        self.assertEqual(purchase.price_amount_snapshot, Decimal("120.00"))


class StoragePurchaseSnapshotTests(TestCase):
    def test_purchase_snapshots_exact_price_and_currency(self):
        user = make_eligible_user("snapshot_price", "snapshot_price@example.com")
        product = storage_product("storage-8gb")
        add_price(product, "120.00", currency="CAD")

        purchase = create_storage_purchase(user=user, product=product)

        self.assertEqual(purchase.price_amount_snapshot, Decimal("120.00"))
        self.assertEqual(purchase.currency_snapshot, "CAD")

    def test_later_product_price_deactivation_does_not_change_historical_purchase(self):
        user = make_eligible_user("snapshot_deactivated_price", "snapshot_deactivated_price@example.com")
        product = storage_product("storage-8gb")
        price = add_price(product, "120.00")
        purchase = create_storage_purchase(user=user, product=product)

        price.active = False
        price.save(update_fields=["active", "updated_at"])
        purchase.refresh_from_db()

        self.assertEqual(purchase.product_price, price)
        self.assertEqual(purchase.price_amount_snapshot, Decimal("120.00"))

    def test_later_product_price_change_does_not_change_historical_purchase(self):
        user = make_eligible_user("snapshot_later_price", "snapshot_later_price@example.com")
        product = storage_product("storage-8gb")
        price = add_price(product, "120.00")
        purchase = create_storage_purchase(user=user, product=product)

        price.amount = Decimal("150.00")
        price.save(update_fields=["amount", "updated_at"])
        purchase.refresh_from_db()

        self.assertEqual(purchase.price_amount_snapshot, Decimal("120.00"))

    def test_purchase_snapshots_exact_storage_capacity(self):
        user = make_eligible_user("snapshot_capacity", "snapshot_capacity@example.com")
        product = storage_product("storage-8gb")
        add_price(product)

        purchase = create_storage_purchase(user=user, product=product)

        self.assertEqual(purchase.capacity_bytes_snapshot, 8 * GIB)
        self.assertEqual(purchase.capacity_label_snapshot, product.name)

    def test_later_storage_metadata_change_does_not_change_purchase_history(self):
        user = make_eligible_user("snapshot_later_capacity", "snapshot_later_capacity@example.com")
        product = storage_product("storage-8gb")
        add_price(product)
        purchase = create_storage_purchase(user=user, product=product)

        product.storage_metadata.capacity_bytes = 88 * GIB
        product.storage_metadata.save(update_fields=["capacity_bytes"])
        purchase.refresh_from_db()

        self.assertEqual(purchase.capacity_bytes_snapshot, 8 * GIB)

    def test_completed_purchase_retains_immutable_price_and_capacity_snapshots(self):
        user = make_eligible_user("snapshot_completed", "snapshot_completed@example.com")
        product = storage_product("storage-8gb")
        price = add_price(product, "120.00")
        completed = complete_storage_purchase(create_storage_purchase(user=user, product=product))

        price.amount = Decimal("150.00")
        price.save(update_fields=["amount", "updated_at"])
        product.storage_metadata.capacity_bytes = 88 * GIB
        product.storage_metadata.save(update_fields=["capacity_bytes"])
        completed.refresh_from_db()

        self.assertEqual(completed.price_amount_snapshot, Decimal("120.00"))
        self.assertEqual(completed.capacity_bytes_snapshot, 8 * GIB)
        self.assertEqual(completed.capacity_grant.capacity_bytes, 8 * GIB)


class StoragePurchaseEligibilityTests(TestCase):
    def test_ineligible_customer_cannot_create_storage_purchase(self):
        user = make_user("stockpile_purchase", "stockpile_purchase@example.com")
        create_storage_capacity_grant(
            user=user,
            capacity_bytes=88 * GIB,
            origin=StorageCapacityGrantOrigin.PURCHASE,
            product=storage_product("storage-88gb"),
        )
        StorageEntitlement.objects.create(user=user, capacity_bytes=88 * GIB, usage_bytes=10 * GIB)
        product = storage_product("storage-288gb")
        add_price(product)

        with self.assertRaises(ValidationError):
            create_storage_purchase(user=user, product=product)

    def test_eligible_customer_can_create_pending_purchase(self):
        user = make_eligible_user("eligible_pending", "eligible_pending@example.com")
        product = storage_product("storage-8gb")
        add_price(product)

        purchase = create_storage_purchase(user=user, product=product)

        self.assertEqual(purchase.status, StoragePurchaseStatus.PENDING)
        self.assertIsNone(purchase.capacity_grant)

    def test_declared_upcoming_need_participates_in_purchase_eligibility(self):
        user = make_user("declared_purchase", "declared_purchase@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        product = storage_product("storage-88gb")
        add_price(product)

        purchase = create_storage_purchase(user=user, product=product, declared_upcoming_need_bytes=70 * GIB)

        self.assertEqual(purchase.status, StoragePurchaseStatus.PENDING)
        self.assertEqual(purchase.capacity_bytes_snapshot, 88 * GIB)

    def test_unsupported_storage_block_is_rejected(self):
        user = make_eligible_user("unsupported_product", "unsupported_product@example.com")
        product = Product.objects.create(slug="storage-488gb", name="Storage +488 GiB", product_type=Product.ProductType.STORAGE)
        StorageProductMetadata.objects.create(product=product, capacity_bytes=488 * GIB)
        add_price(product)

        with self.assertRaises(ValidationError):
            create_storage_purchase(user=user, product=product)

    def test_inactive_storage_product_is_rejected(self):
        user = make_eligible_user("inactive_storage_product", "inactive_storage_product@example.com")
        product = storage_product("storage-8gb")
        product.active = False
        product.save(update_fields=["active", "updated_at"])
        add_price(product)

        with self.assertRaises(ValidationError):
            create_storage_purchase(user=user, product=product)


class StoragePurchaseCompletionTests(TestCase):
    def test_pending_purchase_creates_no_grant(self):
        purchase = create_pending_purchase()

        self.assertFalse(StorageCapacityGrant.objects.filter(user=purchase.user).exists())

    def test_completed_purchase_creates_one_permanent_purchase_origin_grant(self):
        purchase = create_pending_purchase()

        completed = complete_storage_purchase(purchase)

        self.assertEqual(completed.status, StoragePurchaseStatus.COMPLETED)
        self.assertIsNotNone(completed.capacity_grant)
        self.assertEqual(completed.capacity_grant.origin, StorageCapacityGrantOrigin.PURCHASE)
        self.assertEqual(completed.capacity_grant.capacity_bytes, completed.capacity_bytes_snapshot)
        self.assertIsNone(completed.capacity_grant.expires_at)
        self.assertEqual(StorageCapacityGrant.objects.filter(user=completed.user).count(), 1)

    def test_repeated_completion_is_idempotent(self):
        purchase = complete_storage_purchase(create_pending_purchase())
        first_grant_id = purchase.capacity_grant_id

        second = complete_storage_purchase(purchase)

        self.assertEqual(second.capacity_grant_id, first_grant_id)
        self.assertEqual(StorageCapacityGrant.objects.filter(user=second.user).count(), 1)

    def test_failed_purchase_creates_no_grant(self):
        purchase = create_pending_purchase()

        failed = fail_storage_purchase(purchase)

        self.assertEqual(failed.status, StoragePurchaseStatus.FAILED)
        self.assertIsNone(failed.capacity_grant)
        self.assertFalse(StorageCapacityGrant.objects.filter(user=failed.user).exists())

    def test_completed_failed_purchase_is_rejected(self):
        purchase = fail_storage_purchase(create_pending_purchase())

        with self.assertRaises(ValidationError):
            complete_storage_purchase(purchase)

    def test_refund_does_not_delete_or_revoke_capacity_grant(self):
        purchase = complete_storage_purchase(create_pending_purchase())
        grant_id = purchase.capacity_grant_id

        refunded = refund_storage_purchase(purchase)

        self.assertEqual(refunded.status, StoragePurchaseStatus.REFUNDED)
        self.assertEqual(refunded.capacity_grant_id, grant_id)
        self.assertTrue(StorageCapacityGrant.objects.filter(id=grant_id).exists())


class StorageCommerceAuditProtectionTests(TestCase):
    def test_product_price_referenced_by_historical_purchase_cannot_be_deleted(self):
        purchase = create_pending_purchase()

        with self.assertRaises(ProtectedError):
            purchase.product_price.delete()

    def test_product_referenced_by_historical_purchase_cannot_be_deleted(self):
        purchase = create_pending_purchase()

        with self.assertRaises(ProtectedError):
            purchase.product.delete()

    def test_user_with_storage_purchase_history_cannot_be_deleted(self):
        purchase = create_pending_purchase()

        with self.assertRaises(ProtectedError):
            purchase.user.delete()

    def test_user_with_storage_capacity_grant_history_cannot_be_deleted(self):
        user = make_user("grant_protected_user", "grant_protected_user@example.com")
        create_storage_capacity_grant(
            user=user,
            capacity_bytes=8 * GIB,
            origin=StorageCapacityGrantOrigin.PURCHASE,
            product=storage_product("storage-8gb"),
        )

        with self.assertRaises(ProtectedError):
            user.delete()

    def test_linked_storage_capacity_grant_cannot_be_deleted(self):
        purchase = complete_storage_purchase(create_pending_purchase())

        with self.assertRaises(ProtectedError):
            purchase.capacity_grant.delete()


class StoragePurchaseSeparationTests(TestCase):
    def test_storage_purchase_does_not_create_tool_entitlement(self):
        user = make_eligible_user("purchase_no_tool", "purchase_no_tool@example.com")
        initial_count = ToolEntitlement.objects.filter(user=user).count()

        create_pending_purchase(user=user)

        self.assertEqual(ToolEntitlement.objects.filter(user=user).count(), initial_count)

    def test_storage_purchase_does_not_create_ai_entitlement(self):
        purchase = create_pending_purchase()

        self.assertFalse(AIEntitlement.objects.filter(user=purchase.user).exists())

    def test_storage_only_user_supported_after_completed_purchase(self):
        user = make_user("purchase_storage_only", "purchase_storage_only@example.com")
        product = storage_product("storage-8gb")
        add_price(product)
        eligibility = evaluate_storage_purchase_eligibility(user, 8 * GIB)
        self.assertTrue(eligibility.eligible)

        completed = complete_storage_purchase(create_storage_purchase(user=user, product=product))

        self.assertEqual(get_entitled_storage_bytes(user), 8 * GIB)
        self.assertTrue(can_store_bytes(user, 8 * GIB).allowed)
        self.assertIsNotNone(completed.capacity_grant)
        self.assertFalse(ToolEntitlement.objects.filter(user=user).exists())


class StorageRevenueReportingTests(TestCase):
    def test_completed_purchase_contributes_revenue_and_capacity(self):
        complete_storage_purchase(create_pending_purchase(amount="120.00"))

        report = get_storage_purchase_report()

        self.assertEqual(report.completed_storage_purchase_count, 1)
        self.assertEqual(report.completed_storage_revenue, Decimal("120.00"))
        self.assertEqual(report.completed_capacity_sold_bytes, 8 * GIB)

    def test_pending_and_failed_purchases_do_not_contribute_revenue(self):
        create_pending_purchase(user=make_eligible_user("pending_rev", "pending_rev@example.com"), amount="120.00")
        fail_storage_purchase(create_pending_purchase(user=make_eligible_user("failed_rev", "failed_rev@example.com"), amount="130.00"))

        report = get_storage_purchase_report()

        self.assertEqual(report.completed_storage_purchase_count, 0)
        self.assertEqual(report.completed_storage_revenue, Decimal("0.00"))
        self.assertEqual(report.pending_purchase_count, 1)

    def test_refunded_purchase_reported_separately(self):
        refund_storage_purchase(complete_storage_purchase(create_pending_purchase(amount="120.00")))

        report = get_storage_purchase_report()

        self.assertEqual(report.completed_storage_purchase_count, 0)
        self.assertEqual(report.refunded_purchase_count, 1)

    def test_historical_price_snapshots_drive_revenue(self):
        user = make_eligible_user("historical_revenue", "historical_revenue@example.com")
        product = storage_product("storage-8gb")
        price = add_price(product, "120.00")
        purchase = create_storage_purchase(user=user, product=product)
        price.amount = Decimal("150.00")
        price.save(update_fields=["amount", "updated_at"])
        complete_storage_purchase(purchase)

        report = get_storage_purchase_report()

        self.assertEqual(report.completed_storage_revenue, Decimal("120.00"))


class StorageEconomicsTests(TestCase):
    def test_economics_report_uses_canonical_entitlement_and_separate_usage(self):
        user = make_eligible_user("econ_canonical", "econ_canonical@example.com")
        complete_storage_purchase(create_pending_purchase(user=user, amount="120.00"))

        report = get_storage_economics_report()

        self.assertEqual(report.completed_storage_revenue, Decimal("120.00"))
        self.assertEqual(report.completed_capacity_sold_bytes, 8 * GIB)
        self.assertEqual(report.total_customer_entitled_bytes, 16 * GIB)
        self.assertEqual(report.total_customer_used_bytes, 7 * GIB)

    def test_provider_cost_and_gross_margin_are_none_when_absent(self):
        report = get_storage_economics_report()

        self.assertIsNone(report.provider_cost_total_or_none)
        self.assertIsNone(report.gross_margin_or_none)
        self.assertIsNone(report.physical_capacity_bytes_or_none)

    def test_negative_gross_margin_is_returned_when_provider_cost_exceeds_revenue(self):
        now = timezone.now()
        ProviderStorageCost.objects.create(
            provider="imported-provider",
            period_start=now - timedelta(days=30),
            period_end=now,
            amount=Decimal("150.00"),
            currency="USD",
        )
        complete_storage_purchase(create_pending_purchase(amount="120.00"))

        report = get_storage_economics_report()

        self.assertEqual(report.provider_cost_total_or_none, Decimal("150.00"))
        self.assertEqual(report.gross_margin_or_none, Decimal("-30.00"))

    def test_real_provider_storage_cost_rows_contribute_deterministic_cost(self):
        now = timezone.now()
        ProviderStorageCost.objects.create(
            provider="imported-provider",
            period_start=now - timedelta(days=30),
            period_end=now,
            amount=Decimal("40.00"),
            currency="USD",
            physical_capacity_bytes=100 * GIB,
            stored_bytes=20 * GIB,
        )
        complete_storage_purchase(create_pending_purchase(amount="120.00"))

        report = get_storage_economics_report()

        self.assertEqual(report.provider_cost_total_or_none, Decimal("40.00"))
        self.assertEqual(report.physical_capacity_bytes_or_none, 100 * GIB)
        self.assertEqual(report.gross_margin_or_none, Decimal("80.00"))


class StorageCommerceLegacyTests(TestCase):
    def test_blackbod_access_semantics_unchanged(self):
        user = make_eligible_user("commerce_blackbod", "commerce_blackbod@example.com")

        self.assertTrue(has_blackbod_access(user))

    def test_legacy_user_subscription_untouched_by_storage_purchase(self):
        user = make_eligible_user("commerce_legacy", "commerce_legacy@example.com")
        subscription = UserSubscription.objects.create(
            user=user,
            plan=SubscriptionPlan.objects.get(slug="advanced"),
            status="no_subscription",
            billing_period="monthly",
            current_period_start=timezone.now(),
        )

        create_pending_purchase(user=user)
        subscription.refresh_from_db()

        self.assertEqual(subscription.plan.slug, "advanced")
        self.assertEqual(subscription.status, "no_subscription")

    def test_phase_4_anti_stockpiling_behavior_preserved(self):
        user = make_user("commerce_stockpile", "commerce_stockpile@example.com")
        create_storage_capacity_grant(
            user=user,
            capacity_bytes=288 * GIB,
            origin=StorageCapacityGrantOrigin.PURCHASE,
            product=storage_product("storage-288gb"),
        )
        StorageEntitlement.objects.create(user=user, capacity_bytes=288 * GIB, usage_bytes=20 * GIB)

        result = evaluate_storage_purchase_eligibility(user, 288 * GIB)

        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "sufficient_reserve")
