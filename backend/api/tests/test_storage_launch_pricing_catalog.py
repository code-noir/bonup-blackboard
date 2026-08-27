# backend/api/tests/test_storage_launch_pricing_catalog.py

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backend.billing.commercial import create_tool_entitlement
from backend.billing.models import (
    AIEntitlement,
    CustomerPackage,
    Product,
    ProductPrice,
    ProviderStorageCost,
    StorageCapacityGrant,
    StorageEntitlement,
    StorageProductMetadata,
    StoragePurchase,
    ToolEntitlement,
)
from backend.billing.storage import (
    GIB,
    evaluate_storage_purchase_eligibility,
    get_storage_capacity_snapshot,
)
from backend.billing.storage_commerce import get_storage_catalog

from .helpers import make_user


def blackbod_product():
    return Product.objects.get(slug="blackbod")


def storage_product(slug):
    return Product.objects.get(slug=slug)


def catalog_by_slug():
    return {item.product_slug: item for item in get_storage_catalog()}


class StorageLaunchPricingCatalogTests(TestCase):
    def test_catalog_contains_exactly_three_launch_storage_products(self):
        catalog = get_storage_catalog()

        self.assertEqual([item.product_slug for item in catalog], ["storage-8gb", "storage-88gb", "storage-288gb"])

    def test_launch_prices_are_one_time_usd(self):
        catalog = catalog_by_slug()

        self.assertEqual(catalog["storage-8gb"].amount, Decimal("18.00"))
        self.assertEqual(catalog["storage-8gb"].currency, "USD")
        self.assertEqual(catalog["storage-8gb"].price_type, ProductPrice.PriceType.ONE_TIME)
        self.assertEqual(catalog["storage-88gb"].amount, Decimal("118.00"))
        self.assertEqual(catalog["storage-88gb"].currency, "USD")
        self.assertEqual(catalog["storage-88gb"].price_type, ProductPrice.PriceType.ONE_TIME)
        self.assertEqual(catalog["storage-288gb"].amount, Decimal("388.00"))
        self.assertEqual(catalog["storage-288gb"].currency, "USD")
        self.assertEqual(catalog["storage-288gb"].price_type, ProductPrice.PriceType.ONE_TIME)

    def test_catalog_is_sorted_by_capacity(self):
        catalog = get_storage_catalog()

        self.assertEqual([item.capacity_gib for item in catalog], [8, 88, 288])
        self.assertEqual([item.capacity_bytes for item in catalog], [8 * GIB, 88 * GIB, 288 * GIB])

    def test_inactive_product_is_excluded(self):
        product = storage_product("storage-88gb")
        product.active = False
        product.save(update_fields=["active", "updated_at"])

        self.assertEqual([item.product_slug for item in get_storage_catalog()], ["storage-8gb", "storage-288gb"])

    def test_missing_storage_metadata_is_excluded(self):
        StorageProductMetadata.objects.filter(product=storage_product("storage-88gb")).delete()

        self.assertEqual([item.product_slug for item in get_storage_catalog()], ["storage-8gb", "storage-288gb"])

    def test_missing_active_one_time_price_is_excluded(self):
        ProductPrice.objects.filter(
            product=storage_product("storage-88gb"),
            price_type=ProductPrice.PriceType.ONE_TIME,
            currency="USD",
        ).update(active=False, effective_until=timezone.now() - timedelta(minutes=1))

        self.assertEqual([item.product_slug for item in get_storage_catalog()], ["storage-8gb", "storage-288gb"])

    def test_ambiguous_active_price_raises_validation_error(self):
        product = storage_product("storage-88gb")
        ProductPrice.objects.create(
            product=product,
            price_type=ProductPrice.PriceType.ONE_TIME,
            amount=Decimal("119.00"),
            currency="USD",
            active=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )

        with self.assertRaisesMessage(ValidationError, "Ambiguous active ProductPrice"):
            get_storage_catalog()

    def test_monthly_and_annual_prices_do_not_qualify(self):
        product = storage_product("storage-88gb")
        ProductPrice.objects.filter(product=product, price_type=ProductPrice.PriceType.ONE_TIME).update(
            active=False,
            effective_until=timezone.now() - timedelta(minutes=1),
        )
        ProductPrice.objects.create(
            product=product,
            price_type=ProductPrice.PriceType.MONTHLY,
            amount=Decimal("8.00"),
            currency="USD",
            active=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )
        ProductPrice.objects.create(
            product=product,
            price_type=ProductPrice.PriceType.ANNUAL,
            amount=Decimal("80.00"),
            currency="USD",
            active=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual([item.product_slug for item in get_storage_catalog()], ["storage-8gb", "storage-288gb"])

    def test_catalog_read_creates_no_customer_commerce_records(self):
        get_storage_catalog()

        self.assertEqual(StoragePurchase.objects.count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)
        self.assertEqual(CustomerPackage.objects.count(), 0)

    def test_blackbod_included_storage_remains_independent(self):
        user = make_user("catalog_blackbod", "catalog_blackbod@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        get_storage_catalog()
        snapshot = get_storage_capacity_snapshot(user)

        self.assertEqual(snapshot.entitled_bytes, 8 * GIB)
        self.assertEqual(snapshot.used_bytes, 0)
        self.assertEqual(snapshot.remaining_bytes, 8 * GIB)
        self.assertEqual(StorageCapacityGrant.objects.filter(user=user).count(), 0)

    def test_storage_purchase_eligibility_remains_separate_from_catalog(self):
        user = make_user("catalog_eligibility", "catalog_eligibility@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        catalog = get_storage_catalog()
        eligibility = evaluate_storage_purchase_eligibility(user, 88 * GIB)

        self.assertEqual(len(catalog), 3)
        self.assertFalse(eligibility.eligible)
        self.assertEqual(eligibility.reason, "sufficient_reserve")

    def test_catalog_read_creates_no_entitlements_or_provider_costs(self):
        get_storage_catalog()

        self.assertEqual(ProviderStorageCost.objects.count(), 0)
        self.assertEqual(StorageEntitlement.objects.count(), 0)
        self.assertEqual(AIEntitlement.objects.count(), 0)
        self.assertEqual(ToolEntitlement.objects.count(), 0)
