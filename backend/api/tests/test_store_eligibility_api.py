# backend/api/tests/test_store_eligibility_api.py

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from backend.billing.commercial import create_storage_entitlement, create_tool_entitlement
from backend.billing.models import (
    Product,
    StorageCapacityGrant,
    StoragePurchase,
    ToolEntitlement,
)
from backend.billing.storage import GIB

from .helpers import authed_client, make_user


ELIGIBILITY_URL = "/api/billing/store/eligibility/"
SUFFICIENT_RESERVE_MESSAGE = "You currently have enough available Vault storage. Additional permanent Storage becomes available as you approach your current capacity."


def blackbod_product():
    return Product.objects.get(slug="blackbod")


def eligibility_payload(tool_interval=None, storage_slugs=None, ai_slug=None):
    tools = []
    if tool_interval is not None:
        tools.append({"slug": "blackbod", "billing_interval": tool_interval})
    payload = {
        "tools": tools,
        "ai_product_slug": ai_slug,
    }
    if storage_slugs is not None:
        payload["storage_product_slugs"] = storage_slugs
    return payload


class StoreEligibilityAPITests(TestCase):
    def setUp(self):
        self.user = make_user("store_eligibility", "store_eligibility@example.com")
        self.client = authed_client(self.user)

    def post_eligibility(self, payload):
        return self.client.post(ELIGIBILITY_URL, payload, format="json")

    def assert_all_storage(self, response, *, eligible, code):
        self.assertEqual(set(response.data["storage"].keys()), {"storage-8gb", "storage-88gb", "storage-288gb"})
        for result in response.data["storage"].values():
            self.assertEqual(result["eligible"], eligible)
            self.assertEqual(result["code"], code)

    def test_authentication_required(self):
        response = APIClient().post(ELIGIBILITY_URL, eligibility_payload(), format="json")

        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_existing_blackbod_with_unused_included_storage_marks_storage_unavailable(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())

        response = self.post_eligibility(eligibility_payload())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_all_storage(response, eligible=False, code="sufficient_reserve")
        self.assertEqual(response.data["storage"]["storage-88gb"]["message"], SUFFICIENT_RESERVE_MESSAGE)

    def test_existing_blackbod_near_capacity_marks_storage_available(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())
        create_storage_entitlement(user=self.user, capacity_bytes=8 * GIB, usage_bytes=7 * GIB)

        response = self.post_eligibility(eligibility_payload())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_all_storage(response, eligible=True, code="capacity_needed")

    def test_new_customer_selecting_blackbod_keeps_initial_storage_available(self):
        response = self.post_eligibility(eligibility_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_all_storage(response, eligible=True, code="capacity_needed")
        self.assertFalse(ToolEntitlement.objects.filter(user=self.user).exists())

    def test_invalid_storage_products_are_reported_safely(self):
        response = self.post_eligibility(eligibility_payload(storage_slugs=["missing-storage", "blackbod"]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["storage"]["missing-storage"]["eligible"], False)
        self.assertEqual(response.data["storage"]["missing-storage"]["code"], "product_not_found")
        self.assertEqual(response.data["storage"]["blackbod"]["eligible"], False)
        self.assertEqual(response.data["storage"]["blackbod"]["code"], "invalid_product_kind")

    def test_unsupported_ai_selection_is_rejected(self):
        response = self.post_eligibility(eligibility_payload(ai_slug="ai-pro"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "unsupported_ai_product")

    def test_eligibility_endpoint_creates_no_commercial_records(self):
        response = self.post_eligibility(eligibility_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(StoragePurchase.objects.count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)
        self.assertEqual(ToolEntitlement.objects.count(), 0)

    def test_repeated_eligibility_calls_are_side_effect_free(self):
        payload = eligibility_payload(tool_interval="monthly")

        self.assertEqual(self.post_eligibility(payload).status_code, status.HTTP_200_OK)
        self.assertEqual(self.post_eligibility(payload).status_code, status.HTTP_200_OK)
        self.assertEqual(StoragePurchase.objects.count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)
        self.assertEqual(ToolEntitlement.objects.count(), 0)

    def test_included_blackbod_storage_is_not_double_counted_for_current_access(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())

        response = self.post_eligibility(eligibility_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_all_storage(response, eligible=False, code="sufficient_reserve")
        self.assertEqual(ToolEntitlement.objects.filter(user=self.user).count(), 1)
