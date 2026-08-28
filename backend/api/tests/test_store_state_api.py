# backend/api/tests/test_store_state_api.py

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from backend.billing.commercial import create_storage_entitlement, create_tool_entitlement
from backend.billing.models import (
    AIEntitlement,
    CustomerPackage,
    Product,
    StorageCapacityGrant,
    StorageEntitlement,
    StoragePurchase,
    ToolEntitlement,
)
from backend.billing.storage import GIB

from .helpers import authed_client, make_user


STORE_STATE_URL = "/api/billing/store/state/"


def blackbod_product():
    return Product.objects.get(slug="blackbod")


class StoreStateAPITests(TestCase):
    def setUp(self):
        self.user = make_user("store_state", "store_state@example.com")
        self.client = authed_client(self.user)

    def get_state(self):
        return self.client.get(STORE_STATE_URL)

    def test_authentication_required(self):
        response = APIClient().get(STORE_STATE_URL)

        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_active_blackbod_reports_active_and_not_purchasable(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())

        response = self.get_state()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        blackbod = response.data["tools"]["blackbod"]
        self.assertTrue(blackbod["active"])
        self.assertFalse(blackbod["purchasable"])

    def test_customer_without_blackbod_reports_purchasable(self):
        response = self.get_state()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        blackbod = response.data["tools"]["blackbod"]
        self.assertFalse(blackbod["active"])
        self.assertTrue(blackbod["purchasable"])
        self.assertEqual(blackbod["included_storage_bytes"], 0)
        self.assertEqual(blackbod["included_ai"], "")

    def test_active_blackbod_included_storage_matches_storage_snapshot(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())

        response = self.get_state()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        blackbod = response.data["tools"]["blackbod"]
        storage = response.data["storage"]
        self.assertEqual(blackbod["included_storage_bytes"], 8 * GIB)
        self.assertEqual(blackbod["included_storage_gib"], 8)
        self.assertEqual(blackbod["included_ai"], "starter")
        self.assertEqual(storage["entitled_bytes"], 8 * GIB)
        self.assertEqual(storage["used_bytes"], 0)
        self.assertEqual(storage["remaining_bytes"], 8 * GIB)

    def test_storage_entitlement_includes_active_tool_storage_once(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())
        create_storage_entitlement(user=self.user, capacity_bytes=8 * GIB, usage_bytes=7 * GIB)

        response = self.get_state()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tools"]["blackbod"]["included_storage_bytes"], 8 * GIB)
        self.assertEqual(response.data["storage"]["entitled_bytes"], 8 * GIB)
        self.assertEqual(response.data["storage"]["used_bytes"], 7 * GIB)
        self.assertEqual(response.data["storage"]["remaining_bytes"], 1 * GIB)

    def test_store_state_exposes_personalized_storage_eligibility(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())

        response = self.get_state()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data["storage"]["products"].keys()), {"storage-8gb", "storage-88gb", "storage-288gb"})
        for result in response.data["storage"]["products"].values():
            self.assertFalse(result["eligible"])
            self.assertEqual(result["code"], "sufficient_reserve")

    def test_store_state_creates_no_commercial_records(self):
        response = self.get_state()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CustomerPackage.objects.count(), 0)
        self.assertEqual(StoragePurchase.objects.count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)
        self.assertEqual(ToolEntitlement.objects.count(), 0)
        self.assertEqual(StorageEntitlement.objects.count(), 0)
        self.assertEqual(AIEntitlement.objects.count(), 0)

    def test_repeated_store_state_calls_are_side_effect_free(self):
        self.assertEqual(self.get_state().status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_state().status_code, status.HTTP_200_OK)

        self.assertEqual(StoragePurchase.objects.count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)
        self.assertEqual(ToolEntitlement.objects.count(), 0)
