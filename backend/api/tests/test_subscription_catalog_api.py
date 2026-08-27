# backend/api/tests/test_subscription_catalog_api.py

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from backend.billing.commercial import create_tool_entitlement
from backend.billing.models import (
    AIEntitlement,
    CustomerPackage,
    Product,
    ProductPrice,
    ProviderStorageCost,
    StorageCapacityGrant,
    StorageEntitlement,
    StoragePurchase,
    SubscriptionPlan,
    ToolEntitlement,
)
from backend.billing.storage import GIB

from .helpers import authed_client, make_user


CATALOG_URL = "/api/billing/catalog/"


def blackbod_product():
    return Product.objects.get(slug="blackbod")


def storage_product(slug):
    return Product.objects.get(slug=slug)


class SubscriptionCatalogAPITests(TestCase):
    def setUp(self):
        self.user = make_user("catalog_api", "catalog_api@example.com")
        self.client = authed_client(self.user)

    def get_catalog(self):
        response = self.client.get(CATALOG_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def storage_by_slug(self):
        return {item["slug"]: item for item in self.get_catalog()["storage"]}

    def test_authenticated_request_succeeds(self):
        response = self.client.get(CATALOG_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {"tools", "storage", "ai"})

    def test_anonymous_request_is_rejected(self):
        response = APIClient().get(CATALOG_URL)

        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_blackbod_appears_exactly_once_as_tool(self):
        tools = self.get_catalog()["tools"]

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["slug"], "blackbod")
        self.assertEqual(tools[0]["name"], "Blackbòd")
        self.assertEqual(tools[0]["product_type"], Product.ProductType.TOOL)
        self.assertTrue(tools[0]["active"])

    def test_blackbod_pricing_and_included_benefits_are_sourced(self):
        tool = self.get_catalog()["tools"][0]

        self.assertEqual(tool["pricing"]["monthly"], {"amount": "49.00", "currency": "USD"})
        self.assertEqual(tool["pricing"]["annual"], {"amount": "490.00", "currency": "USD"})
        self.assertEqual(tool["included_storage"], {"bytes": 8 * GIB, "gib": 8})
        self.assertEqual(tool["included_ai_allowance"], "starter")

    def test_storage_catalog_contains_exactly_three_launch_products(self):
        storage = self.get_catalog()["storage"]

        self.assertEqual([item["slug"] for item in storage], ["storage-8gb", "storage-88gb", "storage-288gb"])

    def test_storage_launch_prices_are_reported(self):
        storage = self.storage_by_slug()

        self.assertEqual(storage["storage-8gb"]["capacity"], {"bytes": 8 * GIB, "gib": 8})
        self.assertEqual(storage["storage-8gb"]["price"], {"type": "one_time", "amount": "18.00", "currency": "USD"})
        self.assertEqual(storage["storage-88gb"]["capacity"], {"bytes": 88 * GIB, "gib": 88})
        self.assertEqual(storage["storage-88gb"]["price"], {"type": "one_time", "amount": "118.00", "currency": "USD"})
        self.assertEqual(storage["storage-288gb"]["capacity"], {"bytes": 288 * GIB, "gib": 288})
        self.assertEqual(storage["storage-288gb"]["price"], {"type": "one_time", "amount": "388.00", "currency": "USD"})

    def test_ai_catalog_is_empty(self):
        self.assertEqual(self.get_catalog()["ai"], [])

    def test_inactive_storage_product_is_excluded(self):
        product = storage_product("storage-88gb")
        product.active = False
        product.save(update_fields=["active", "updated_at"])

        self.assertEqual([item["slug"] for item in self.get_catalog()["storage"]], ["storage-8gb", "storage-288gb"])

    def test_inactive_tool_product_is_excluded(self):
        product = blackbod_product()
        product.active = False
        product.save(update_fields=["active", "updated_at"])

        self.assertEqual(self.get_catalog()["tools"], [])

    def test_legacy_subscription_plans_are_not_emitted(self):
        catalog = self.get_catalog()
        emitted_slugs = {item["slug"] for item in catalog["tools"] + catalog["storage"]}
        legacy_plan_slugs = set(SubscriptionPlan.objects.values_list("slug", flat=True))

        self.assertFalse(emitted_slugs & legacy_plan_slugs)

    def test_catalog_request_creates_no_customer_commercial_records(self):
        self.client.get(CATALOG_URL)

        self.assertEqual(CustomerPackage.objects.count(), 0)
        self.assertEqual(StoragePurchase.objects.count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)
        self.assertEqual(ToolEntitlement.objects.count(), 0)
        self.assertEqual(StorageEntitlement.objects.count(), 0)
        self.assertEqual(AIEntitlement.objects.count(), 0)
        self.assertEqual(ProviderStorageCost.objects.count(), 0)

    def test_ambiguous_active_storage_price_returns_error(self):
        ProductPrice.objects.create(
            product=storage_product("storage-88gb"),
            price_type=ProductPrice.PriceType.ONE_TIME,
            amount=Decimal("119.00"),
            currency="USD",
            active=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.get(CATALOG_URL)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Ambiguous active ProductPrice", str(response.data["error"]))

    def test_current_user_eligibility_and_usage_do_not_remove_catalog_products(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())
        StorageEntitlement.objects.create(user=self.user, capacity_bytes=8 * GIB, usage_bytes=0)

        storage = self.get_catalog()["storage"]

        self.assertEqual([item["slug"] for item in storage], ["storage-8gb", "storage-88gb", "storage-288gb"])
