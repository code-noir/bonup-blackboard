# backend/api/tests/test_store_quote_api.py

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
    Invoice,
    Product,
    ProductPrice,
    SubscriptionPlan,
    StorageCapacityGrant,
    StorageEntitlement,
    StoragePurchase,
    ToolEntitlement,
    UserSubscription,
)
from backend.billing.storage import GIB
from backend.payments.models import Payment

from .helpers import authed_client, make_user


QUOTE_URL = "/api/billing/quote/"


def blackbod_product():
    return Product.objects.get(slug="blackbod")


def storage_product(slug="storage-8gb"):
    return Product.objects.get(slug=slug)


def quote_payload(tool_interval=None, storage_slug=None, ai_slug=None):
    tools = []
    if tool_interval is not None:
        tools.append({"slug": "blackbod", "billing_interval": tool_interval})
    return {
        "tools": tools,
        "storage_product_slug": storage_slug,
        "ai_product_slug": ai_slug,
    }


def deactivate_one_time_prices(product):
    ProductPrice.objects.filter(
        product=product,
        price_type=ProductPrice.PriceType.ONE_TIME,
        active=True,
    ).update(active=False, effective_until=timezone.now() - timedelta(minutes=1))


class StoreQuoteAPITests(TestCase):
    def setUp(self):
        self.user = make_user("quote_user", "quote_user@example.com")
        self.client = authed_client(self.user)

    def post_quote(self, payload):
        return self.client.post(QUOTE_URL, payload, format="json")

    def assert_money_totals(self, response, *, monthly="0.00", annual="0.00", one_time="0.00", due_today="0.00", currency="USD"):
        self.assertEqual(response.data["currency"], currency)
        self.assertEqual(response.data["totals"]["recurring"]["monthly"], monthly)
        self.assertEqual(response.data["totals"]["recurring"]["annual"], annual)
        self.assertEqual(response.data["totals"]["one_time"], one_time)
        self.assertEqual(response.data["totals"]["due_today"], due_today)

    def test_authentication_required(self):
        response = APIClient().post(QUOTE_URL, quote_payload(tool_interval="monthly"), format="json")

        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_empty_quote_rejected(self):
        response = self.post_quote(quote_payload())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "empty_selection")

    def test_blackbod_monthly_quote(self):
        response = self.post_quote(quote_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_money_totals(response, monthly="49.00", due_today="49.00")
        item = response.data["items"][0]
        self.assertEqual(item["kind"], "tool")
        self.assertEqual(item["product_slug"], "blackbod")
        self.assertEqual(item["billing_interval"], "monthly")
        self.assertEqual(item["amount"], "49.00")
        self.assertEqual(item["included_storage_bytes"], 8 * GIB)
        self.assertEqual(item["included_ai"], "starter")

    def test_blackbod_annual_quote(self):
        response = self.post_quote(quote_payload(tool_interval="annual"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_money_totals(response, annual="490.00", due_today="490.00")
        self.assertEqual(response.data["items"][0]["billing_interval"], "annual")
        self.assertEqual(response.data["items"][0]["amount"], "490.00")

    def test_inactive_tool_product_rejected(self):
        product = blackbod_product()
        product.active = False
        product.save(update_fields=["active", "updated_at"])

        response = self.post_quote(quote_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "inactive_product")

    def test_missing_tool_interval_price_rejected(self):
        product = blackbod_product()
        product.monthly_price = None
        product.save(update_fields=["monthly_price", "updated_at"])

        response = self.post_quote(quote_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "missing_product_price")

    def test_storage_only_quote(self):
        response = self.post_quote(quote_payload(storage_slug="storage-8gb"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_money_totals(response, one_time="18.00", due_today="18.00")
        item = response.data["items"][0]
        self.assertEqual(item["kind"], "storage")
        self.assertEqual(item["product_slug"], "storage-8gb")
        self.assertEqual(item["amount"], "18.00")
        self.assertEqual(item["capacity_bytes"], 8 * GIB)
        self.assertEqual(item["eligibility"], {"eligible": True, "reason": "capacity_needed"})

    def test_blackbod_monthly_plus_storage_quote(self):
        response = self.post_quote(quote_payload(tool_interval="monthly", storage_slug="storage-88gb"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_money_totals(response, monthly="49.00", one_time="118.00", due_today="167.00")
        self.assertEqual([item["kind"] for item in response.data["items"]], ["tool", "storage"])

    def test_blackbod_annual_plus_storage_quote(self):
        response = self.post_quote(quote_payload(tool_interval="annual", storage_slug="storage-88gb"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_money_totals(response, annual="490.00", one_time="118.00", due_today="608.00")

    def test_recurring_and_one_time_totals_are_separated(self):
        response = self.post_quote(quote_payload(tool_interval="monthly", storage_slug="storage-288gb"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_money_totals(response, monthly="49.00", one_time="388.00", due_today="437.00")

    def test_client_authoritative_price_fields_are_rejected(self):
        payload = quote_payload(tool_interval="monthly")
        payload["tools"][0]["amount"] = "0.01"
        payload["totals"] = {"due_today": "0.01"}

        response = self.post_quote(payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_request")

    def test_invalid_product_slug_rejected(self):
        response = self.post_quote({
            "tools": [{"slug": "missing-tool", "billing_interval": "monthly"}],
            "storage_product_slug": None,
            "ai_product_slug": None,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "product_not_found")

    def test_wrong_product_kind_rejected(self):
        response = self.post_quote({
            "tools": [],
            "storage_product_slug": "blackbod",
            "ai_product_slug": None,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_product_kind")

    def test_wrong_product_kind_rejected_for_tool_slot(self):
        response = self.post_quote({
            "tools": [{"slug": "storage-8gb", "billing_interval": "monthly"}],
            "storage_product_slug": None,
            "ai_product_slug": None,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_product_kind")

    def test_inactive_storage_product_rejected(self):
        product = storage_product("storage-8gb")
        product.active = False
        product.save(update_fields=["active", "updated_at"])

        response = self.post_quote(quote_payload(storage_slug="storage-8gb"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "inactive_product")

    def test_missing_storage_price_rejected(self):
        deactivate_one_time_prices(storage_product("storage-8gb"))

        response = self.post_quote(quote_payload(storage_slug="storage-8gb"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "missing_product_price")

    def test_unsupported_billing_interval_rejected(self):
        response = self.post_quote({
            "tools": [{"slug": "blackbod", "billing_interval": "weekly"}],
            "storage_product_slug": None,
            "ai_product_slug": None,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "unsupported_billing_interval")

    def test_duplicate_tool_selection_rejected(self):
        response = self.post_quote({
            "tools": [
                {"slug": "blackbod", "billing_interval": "monthly"},
                {"slug": "blackbod", "billing_interval": "annual"},
            ],
            "storage_product_slug": None,
            "ai_product_slug": None,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "duplicate_tool")

    def test_unsupported_ai_product_rejected(self):
        response = self.post_quote(quote_payload(ai_slug="ai-pro"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "unsupported_ai_product")

    def test_ambiguous_storage_product_price_rejected_safely(self):
        ProductPrice.objects.create(
            product=storage_product("storage-8gb"),
            price_type=ProductPrice.PriceType.ONE_TIME,
            amount=Decimal("19.00"),
            currency="USD",
            active=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )

        response = self.post_quote(quote_payload(storage_slug="storage-8gb"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ambiguous_product_price")

    def test_incompatible_currencies_rejected(self):
        product = storage_product("storage-8gb")
        deactivate_one_time_prices(product)
        ProductPrice.objects.create(
            product=product,
            price_type=ProductPrice.PriceType.ONE_TIME,
            amount=Decimal("18.00"),
            currency="CAD",
            active=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )

        response = self.post_quote(quote_payload(tool_interval="monthly", storage_slug="storage-8gb"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "mixed_currency")

    def test_storage_eligibility_denial_surfaced(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())

        response = self.post_quote(quote_payload(storage_slug="storage-8gb"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "storage_ineligible")

    def test_repeated_identical_quote_calls_create_no_storage_purchase(self):
        payload = quote_payload(storage_slug="storage-8gb")

        self.assertEqual(self.post_quote(payload).status_code, status.HTTP_200_OK)
        self.assertEqual(self.post_quote(payload).status_code, status.HTTP_200_OK)
        self.assertEqual(StoragePurchase.objects.count(), 0)

    def test_repeated_identical_quote_calls_create_no_storage_capacity_grant(self):
        payload = quote_payload(storage_slug="storage-8gb")

        self.assertEqual(self.post_quote(payload).status_code, status.HTTP_200_OK)
        self.assertEqual(self.post_quote(payload).status_code, status.HTTP_200_OK)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)

    def test_quote_creates_no_tool_entitlement(self):
        response = self.post_quote(quote_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ToolEntitlement.objects.count(), 0)

    def test_quote_creates_no_commercial_mutations(self):
        response = self.post_quote(quote_payload(tool_interval="monthly", storage_slug="storage-88gb"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CustomerPackage.objects.count(), 0)
        self.assertEqual(StoragePurchase.objects.count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.count(), 0)
        self.assertEqual(ToolEntitlement.objects.count(), 0)
        self.assertEqual(StorageEntitlement.objects.count(), 0)
        self.assertEqual(AIEntitlement.objects.count(), 0)

    def test_included_blackbod_storage_comes_from_backend_metadata(self):
        product = blackbod_product()
        product.tool_metadata.included_storage_bytes = 12 * GIB
        product.tool_metadata.save(update_fields=["included_storage_bytes"])

        response = self.post_quote(quote_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["included_storage_bytes"], 12 * GIB)
        self.assertEqual(response.data["items"][0]["included_storage_gib"], 12)

    def test_existing_blackbod_entitlement_rejects_tool_purchase_quote(self):
        create_tool_entitlement(user=self.user, product=blackbod_product())

        response = self.post_quote(quote_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "tool_already_active")

    def test_existing_legacy_blackbod_subscription_rejects_tool_purchase_quote(self):
        plan = SubscriptionPlan.objects.get(slug="basic")
        UserSubscription.objects.create(
            user=self.user,
            plan=plan,
            status="active",
            billing_period="monthly",
            current_period_start=timezone.now() - timedelta(days=1),
        )

        response = self.post_quote(quote_payload(tool_interval="monthly"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "tool_already_active")

    def test_quote_creates_no_payment_records_or_invoices(self):
        response = self.post_quote(quote_payload(tool_interval="monthly", storage_slug="storage-88gb"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
