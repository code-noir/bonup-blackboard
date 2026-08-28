# backend/api/tests/test_stripe_billing.py
#
# Tests for the Stripe billing integration layer.
#
# All Stripe SDK calls are mocked — no real network calls are made.
# Tests are organised by layer:
#
#   StripeClientTests         — stripe_client.py
#   StripeServicesTests       — billing/services.py (unit)
#   CheckoutAPITests          — POST /api/billing/checkout/
#   PortalAPITests            — POST /api/billing/portal/
#   WebhookAPITests           — POST /api/billing/webhook/
#   SubscriptionGateLockTests — POST /api/billing/subscription/ locked when Stripe configured

import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from backend.billing.models import (
    Invoice,
    Product,
    StoreCheckout,
    StoreCheckoutStatus,
    StorageCapacityGrant,
    StoragePurchase,
    SubscriptionPlan,
    ToolEntitlement,
    UserSubscription,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(username="stripeuser"):
    return User.objects.create_user(username=username, password="pw", email=f"{username}@example.com")


def _make_plan(slug, **kwargs):
    defaults = dict(
        display_name=slug.title(),
        price_monthly=Decimal("19.00"),
        price_yearly=None,
        is_active=True,
        ai_tier="basic",
        excluded_categories=[],
    )
    defaults.update(kwargs)
    plan, _ = SubscriptionPlan.objects.get_or_create(slug=slug, defaults=defaults)
    return plan


def _make_sub(user, plan, status="active", stripe_customer_id="", stripe_subscription_id=""):
    return UserSubscription.objects.create(
        user=user,
        plan=plan,
        status=status,
        billing_period="monthly",
        current_period_start=timezone.now(),
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
    )


def _authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


STRIPE_SETTINGS = {
    "STRIPE_SECRET_KEY": "sk_test_fake",
    "STRIPE_WEBHOOK_SECRET": "whsec_fake",
    "STRIPE_PRICE_IDS": {
        "starter":      "price_starter",
        "professional": "price_pro",
        "business":     "price_biz",
        "anchor":       "price_anchor",
    },
}


# ---------------------------------------------------------------------------
# stripe_client.py
# ---------------------------------------------------------------------------

class StripeClientTests(TestCase):

    @override_settings(STRIPE_SECRET_KEY="sk_test_abc")
    def test_stripe_configured_true_when_key_present(self):
        from backend.billing.stripe_client import stripe_configured
        self.assertTrue(stripe_configured())

    @override_settings(STRIPE_SECRET_KEY="")
    def test_stripe_configured_false_when_key_empty(self):
        from backend.billing.stripe_client import stripe_configured
        self.assertFalse(stripe_configured())

    @override_settings(STRIPE_SECRET_KEY="sk_test_xyz")
    def test_get_stripe_sets_api_key(self):
        from backend.billing.stripe_client import get_stripe
        stripe = get_stripe()
        self.assertEqual(stripe.api_key, "sk_test_xyz")


# ---------------------------------------------------------------------------
# billing/services.py — unit tests with mocked Stripe
# ---------------------------------------------------------------------------

class StripeServicesTests(TestCase):

    def setUp(self):
        self.user = _make_user("svc_user")
        self.starter = _make_plan("starter", price_monthly=Decimal("19.00"))

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_get_or_create_customer_creates_new(self, mock_get_stripe):
        stripe = MagicMock()
        stripe.Customer.create.return_value = {"id": "cus_new123"}
        mock_get_stripe.return_value = stripe

        from backend.billing.services import get_or_create_stripe_customer
        cid = get_or_create_stripe_customer(self.user)

        self.assertEqual(cid, "cus_new123")
        stripe.Customer.create.assert_called_once()

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_get_or_create_customer_returns_existing(self, mock_get_stripe):
        stripe = MagicMock()
        mock_get_stripe.return_value = stripe
        _make_sub(self.user, self.starter, stripe_customer_id="cus_existing")

        from backend.billing.services import get_or_create_stripe_customer
        cid = get_or_create_stripe_customer(self.user)

        self.assertEqual(cid, "cus_existing")
        stripe.Customer.create.assert_not_called()

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_stripe_customer", return_value="cus_abc")
    @patch("backend.billing.services.get_stripe")
    def test_create_checkout_session_returns_session(self, mock_get_stripe, _mock_cust):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"url": "https://checkout.stripe.com/x"}
        mock_get_stripe.return_value = stripe

        from backend.billing.services import create_checkout_session
        session = create_checkout_session(
            user=self.user,
            plan_slug="starter",
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel",
        )

        self.assertEqual(session["url"], "https://checkout.stripe.com/x")
        stripe.checkout.Session.create.assert_called_once()

    @override_settings(**STRIPE_SETTINGS)
    def test_create_checkout_session_raises_for_invalid_plan(self):
        from backend.billing.services import create_checkout_session
        with self.assertRaises(ValueError):
            create_checkout_session(self.user, "sol_member", "http://s", "http://c")

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_create_portal_session(self, mock_get_stripe):
        stripe = MagicMock()
        stripe.billing_portal.Session.create.return_value = {"url": "https://billing.stripe.com/p"}
        mock_get_stripe.return_value = stripe
        _make_sub(self.user, self.starter, stripe_customer_id="cus_portal")

        from backend.billing.services import create_portal_session
        session = create_portal_session(self.user, return_url="https://app.example.com/billing")

        self.assertEqual(session["url"], "https://billing.stripe.com/p")

    def test_create_portal_session_raises_without_customer(self):
        from backend.billing.services import create_portal_session
        with self.assertRaises(ValueError):
            create_portal_session(self.user, return_url="https://app.example.com/billing")

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_handle_checkout_completed_creates_subscription(self, mock_get_stripe):
        stripe = MagicMock()
        stripe.Subscription.retrieve.return_value = {
            "id": "sub_abc",
            "status": "active",
            "current_period_start": int(time.time()),
            "current_period_end": int(time.time()) + 2592000,
            "metadata": {"bonup_user_id": str(self.user.id), "plan_slug": "starter"},
        }
        mock_get_stripe.return_value = stripe

        from backend.billing.services import handle_checkout_completed
        handle_checkout_completed({
            "id": "cs_abc",
            "subscription": "sub_abc",
            "customer": "cus_abc",
            "metadata": {"bonup_user_id": str(self.user.id), "plan_slug": "starter"},
        })

        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.slug, "basic")
        self.assertEqual(sub.status, "active")
        self.assertEqual(sub.stripe_subscription_id, "sub_abc")

    def test_handle_checkout_completed_no_op_on_missing_metadata(self):
        """checkout.session.completed with no metadata must not raise."""
        from backend.billing.services import handle_checkout_completed
        handle_checkout_completed({"id": "cs_bad"})  # should not raise
        self.assertFalse(UserSubscription.objects.filter(user=self.user).exists())

    @override_settings(**STRIPE_SETTINGS)
    def test_handle_subscription_updated_syncs_status(self):
        _make_sub(self.user, self.starter, stripe_subscription_id="sub_upd")

        from backend.billing.services import handle_subscription_updated
        handle_subscription_updated({
            "id": "sub_upd",
            "status": "past_due",
            "customer": "cus_x",
            "current_period_start": int(time.time()),
            "current_period_end": int(time.time()) + 2592000,
            "metadata": {"bonup_user_id": str(self.user.id), "plan_slug": "starter"},
            "items": {"data": [{"price": {"id": "price_starter"}}]},
        })

        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "past_due")

    @override_settings(**STRIPE_SETTINGS)
    def test_handle_subscription_deleted_sets_cancelled(self):
        _make_sub(self.user, self.starter, stripe_subscription_id="sub_del",
                  stripe_customer_id="cus_del")

        from backend.billing.services import handle_subscription_deleted
        handle_subscription_deleted({
            "id": "sub_del",
            "metadata": {"bonup_user_id": str(self.user.id)},
        })

        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "cancelled")

    @override_settings(**STRIPE_SETTINGS)
    def test_handle_invoice_paid_creates_invoice_record(self):
        _make_sub(self.user, self.starter, stripe_customer_id="cus_inv")

        from backend.billing.services import handle_invoice_paid
        handle_invoice_paid({
            "id": "in_abc",
            "customer": "cus_inv",
            "amount_paid": 1900,
            "currency": "usd",
            "description": "Blackboard Starter",
        })

        inv = Invoice.objects.get(stripe_invoice_id="in_abc")
        self.assertEqual(inv.amount, Decimal("19.00"))
        self.assertEqual(inv.status, "paid")

    @override_settings(**STRIPE_SETTINGS)
    def test_handle_invoice_payment_failed_sets_past_due(self):
        _make_sub(self.user, self.starter, stripe_customer_id="cus_fail")

        from backend.billing.services import handle_invoice_payment_failed
        handle_invoice_payment_failed({"id": "in_fail", "customer": "cus_fail"})

        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "past_due")


# ---------------------------------------------------------------------------
# CheckoutSessionAPIView
# ---------------------------------------------------------------------------

class CheckoutAPITests(TestCase):

    def setUp(self):
        self.user = _make_user("checkout_user")
        self.client = _authed_client(self.user)

    def payload(self, tool_interval=None, storage_slug=None, **extra):
        tools = []
        if tool_interval:
            tools.append({"slug": "blackbod", "billing_interval": tool_interval})
        data = {"tools": tools, "storage_product_slug": storage_slug, "ai_product_slug": None}
        data.update(extra)
        return data

    def assert_checkout_line_item(self, stripe, index, *, recurring=False, amount=None):
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        line = kwargs["line_items"][index]
        price_data = line["price_data"]
        if amount is not None:
            self.assertEqual(price_data["unit_amount"], amount)
        if recurring:
            self.assertIn("recurring", price_data)
        else:
            self.assertNotIn("recurring", price_data)

    def test_authentication_required(self):
        response = APIClient().post("/api/billing/checkout/", self.payload(tool_interval="monthly"), format="json")
        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    @override_settings(**STRIPE_SETTINGS)
    def test_empty_selection_rejected(self):
        response = self.client.post("/api/billing/checkout/", self.payload(), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "empty_selection")

    @override_settings(**STRIPE_SETTINGS, FRONTEND_URL="https://app.example.com")
    @patch("backend.billing.services.get_or_create_store_stripe_customer", return_value="cus_store")
    @patch("backend.billing.services.get_stripe")
    def test_checkout_requotes_and_returns_checkout_url(self, mock_get_stripe, _mock_customer):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"id": "cs_store", "url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe

        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="monthly"), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["checkout_url"], "https://checkout.stripe.com/go")
        checkout = StoreCheckout.objects.get(stripe_checkout_session_id="cs_store")
        self.assertEqual(checkout.quote_snapshot["totals"]["due_today"], "49.00")
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs["success_url"], "https://app.example.com/store/payment/success?session_id={CHECKOUT_SESSION_ID}")
        self.assertEqual(kwargs["metadata"], {"bonup_checkout_id": str(checkout.id)})

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_store_stripe_customer", return_value="cus_store")
    @patch("backend.billing.services.get_stripe")
    def test_client_supplied_prices_cannot_influence_stripe_amount(self, mock_get_stripe, _mock_customer):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"id": "cs_amount", "url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe
        payload = self.payload(storage_slug="storage-8gb", totals={"due_today": "0.01"})

        response = self.client.post("/api/billing/checkout/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        stripe.checkout.Session.create.assert_not_called()

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_store_stripe_customer", return_value="cus_store")
    @patch("backend.billing.services.get_stripe")
    def test_storage_only_creates_payment_mode_checkout(self, mock_get_stripe, _mock_customer):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"id": "cs_storage", "url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe

        response = self.client.post("/api/billing/checkout/", self.payload(storage_slug="storage-8gb"), format="json")

        self.assertEqual(response.status_code, 201)
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "payment")
        self.assertIn("payment_intent_data", kwargs)
        self.assert_checkout_line_item(stripe, 0, recurring=False, amount=1800)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_store_stripe_customer", return_value="cus_store")
    @patch("backend.billing.services.get_stripe")
    def test_blackbod_monthly_creates_subscription_mode_checkout(self, mock_get_stripe, _mock_customer):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"id": "cs_monthly", "url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe

        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="monthly"), format="json")

        self.assertEqual(response.status_code, 201)
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(kwargs["line_items"][0]["price_data"]["recurring"], {"interval": "month"})
        self.assert_checkout_line_item(stripe, 0, recurring=True, amount=4900)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_store_stripe_customer", return_value="cus_store")
    @patch("backend.billing.services.get_stripe")
    def test_blackbod_annual_creates_subscription_mode_checkout(self, mock_get_stripe, _mock_customer):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"id": "cs_annual", "url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe

        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="annual"), format="json")

        self.assertEqual(response.status_code, 201)
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(kwargs["line_items"][0]["price_data"]["recurring"], {"interval": "year"})
        self.assert_checkout_line_item(stripe, 0, recurring=True, amount=49000)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_store_stripe_customer", return_value="cus_store")
    @patch("backend.billing.services.get_stripe")
    def test_blackbod_plus_storage_creates_subscription_mode_mixed_cart(self, mock_get_stripe, _mock_customer):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"id": "cs_mixed", "url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe

        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="monthly", storage_slug="storage-8gb"), format="json")

        self.assertEqual(response.status_code, 201)
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(len(kwargs["line_items"]), 2)
        self.assert_checkout_line_item(stripe, 0, recurring=True, amount=4900)
        self.assert_checkout_line_item(stripe, 1, recurring=False, amount=1800)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_already_active_blackbod_rejected(self, mock_get_stripe):
        ToolEntitlement.objects.create(user=self.user, product=Product.objects.get(slug="blackbod"))
        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="monthly"), format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "tool_already_active")
        mock_get_stripe.assert_not_called()

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_ineligible_protected_storage_rejected(self, mock_get_stripe):
        ToolEntitlement.objects.create(user=self.user, product=Product.objects.get(slug="blackbod"))
        response = self.client.post("/api/billing/checkout/", self.payload(storage_slug="storage-288gb"), format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "storage_ineligible")
        mock_get_stripe.assert_not_called()

    @override_settings(STRIPE_SECRET_KEY="")
    def test_checkout_503_when_stripe_not_configured(self):
        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="monthly"), format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "payment_checkout_not_configured")
        self.assertEqual(response.data["detail"], "Payment checkout is not configured yet.")

    @override_settings(STRIPE_SECRET_KEY="sk_live_never_for_store_checkout")
    def test_checkout_rejects_live_secret_key(self):
        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="monthly"), format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "payment_checkout_not_configured")

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_store_stripe_customer", return_value="cus_store")
    @patch("backend.billing.services.get_stripe")
    def test_checkout_creation_does_not_fulfill_commercial_resources(self, mock_get_stripe, _mock_customer):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"id": "cs_no_fulfill", "url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe

        response = self.client.post("/api/billing/checkout/", self.payload(tool_interval="monthly", storage_slug="storage-8gb"), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ToolEntitlement.objects.filter(user=self.user).count(), 0)
        self.assertEqual(StoragePurchase.objects.filter(user=self.user).count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.filter(user=self.user).count(), 0)


# ---------------------------------------------------------------------------
# BillingPortalAPIView
# ---------------------------------------------------------------------------

class PortalAPITests(TestCase):

    def setUp(self):
        self.user = _make_user("portal_user")
        self.client = _authed_client(self.user)
        plan = _make_plan("starter")
        _make_sub(self.user, plan, stripe_customer_id="cus_portal")

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_portal_returns_portal_url(self, mock_get_stripe):
        stripe = MagicMock()
        stripe.billing_portal.Session.create.return_value = {"url": "https://billing.stripe.com/p"}
        mock_get_stripe.return_value = stripe

        resp = self.client.post("/api/billing/portal/", {
            "return_url": "https://app.example.com/billing",
        }, format="json")

        self.assertEqual(resp.status_code, 201)
        self.assertIn("portal_url", resp.data)

    @override_settings(**STRIPE_SETTINGS)
    def test_portal_400_without_return_url(self):
        resp = self.client.post("/api/billing/portal/", {}, format="json")
        self.assertEqual(resp.status_code, 400)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_portal_503_when_stripe_not_configured(self):
        resp = self.client.post("/api/billing/portal/", {
            "return_url": "https://app.example.com/billing",
        }, format="json")
        self.assertEqual(resp.status_code, 503)


# ---------------------------------------------------------------------------
# WebhookAPIView and Store checkout fulfillment
# ---------------------------------------------------------------------------

class WebhookAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user("wh_store_user")

    def payload(self, tool_interval=None, storage_slug=None):
        tools = []
        if tool_interval:
            tools.append({"slug": "blackbod", "billing_interval": tool_interval})
        return {"tools": tools, "storage_product_slug": storage_slug, "ai_product_slug": None}

    def make_checkout(self, selection, session_id="cs_paid", customer_id="cus_paid"):
        from backend.billing.store_quote import build_store_quote
        quote = build_store_quote(user=self.user, selection=selection)
        return StoreCheckout.objects.create(
            user=self.user,
            status=StoreCheckoutStatus.CHECKOUT_CREATED,
            currency=quote["currency"],
            recurring_amount_snapshot=Decimal(quote["totals"]["recurring"]["monthly"]) + Decimal(quote["totals"]["recurring"]["annual"]),
            one_time_amount_snapshot=Decimal(quote["totals"]["one_time"]),
            due_today_snapshot=Decimal(quote["totals"]["due_today"]),
            selection_snapshot=selection,
            quote_snapshot=quote,
            stripe_checkout_session_id=session_id,
            stripe_customer_id=customer_id,
        )

    def stripe_session(self, checkout, *, payment_status="paid", mode="payment", subscription=None, payment_intent="pi_paid"):
        return {
            "id": checkout.stripe_checkout_session_id,
            "status": "complete",
            "mode": mode,
            "payment_status": payment_status,
            "customer": checkout.stripe_customer_id,
            "payment_intent": payment_intent,
            "subscription": subscription,
            "metadata": {"bonup_checkout_id": str(checkout.id)},
        }

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_invalid_signature_rejected(self, mock_get_stripe):
        stripe = MagicMock()
        import stripe as real_stripe
        stripe.Webhook.construct_event.side_effect = real_stripe.error.SignatureVerificationError("bad sig", "fake_sig")
        mock_get_stripe.return_value = stripe

        response = self.client.post(
            "/api/billing/webhook/",
            data=json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=fake,v1=fake",
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_valid_stripe_event_accepted(self, mock_get_stripe):
        stripe = MagicMock()
        stripe.Webhook.construct_event.return_value = {"type": "payment_intent.created", "data": {"object": {"id": "pi_x"}}}
        mock_get_stripe.return_value = stripe

        response = self.client.post(
            "/api/billing/webhook/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )

        self.assertEqual(response.status_code, 200)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_missing_webhook_secret_rejected(self, mock_get_stripe):
        with self.settings(STRIPE_WEBHOOK_SECRET=""):
            response = self.client.post(
                "/api/billing/webhook/",
                data=json.dumps({"type": "payment_intent.created", "data": {"object": {}}}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        mock_get_stripe.assert_not_called()

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_unpaid_state_does_not_fulfill(self, mock_get_stripe):
        checkout = self.make_checkout(self.payload(storage_slug="storage-8gb"), session_id="cs_unpaid")
        stripe = MagicMock()
        stripe.checkout.Session.retrieve.return_value = self.stripe_session(checkout, payment_status="unpaid")
        mock_get_stripe.return_value = stripe

        from backend.billing.services import fulfill_store_checkout_session
        fulfill_store_checkout_session("cs_unpaid")

        checkout.refresh_from_db()
        self.assertEqual(checkout.status, StoreCheckoutStatus.FAILED)
        self.assertEqual(StoragePurchase.objects.filter(user=self.user).count(), 0)
        self.assertEqual(StorageCapacityGrant.objects.filter(user=self.user).count(), 0)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_successful_blackbod_payment_creates_one_canonical_entitlement(self, mock_get_stripe):
        checkout = self.make_checkout(self.payload(tool_interval="monthly"), session_id="cs_tool")
        stripe = MagicMock()
        stripe.checkout.Session.retrieve.return_value = self.stripe_session(
            checkout,
            mode="subscription",
            subscription={"id": "sub_tool", "status": "active", "current_period_start": int(time.time()), "current_period_end": int(time.time()) + 2592000},
        )
        mock_get_stripe.return_value = stripe

        from backend.billing.services import fulfill_store_checkout_session
        fulfill_store_checkout_session("cs_tool")
        fulfill_store_checkout_session("cs_tool")

        checkout.refresh_from_db()
        self.assertEqual(checkout.status, StoreCheckoutStatus.FULFILLED)
        self.assertEqual(ToolEntitlement.objects.filter(user=self.user, product__slug="blackbod").count(), 1)
        self.assertEqual(UserSubscription.objects.get(user=self.user).stripe_subscription_id, "sub_tool")

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_successful_storage_payment_creates_exactly_one_purchase_and_grant(self, mock_get_stripe):
        checkout = self.make_checkout(self.payload(storage_slug="storage-8gb"), session_id="cs_storage_paid")
        stripe = MagicMock()
        stripe.checkout.Session.retrieve.return_value = self.stripe_session(checkout)
        mock_get_stripe.return_value = stripe

        from backend.billing.services import fulfill_store_checkout_session
        fulfill_store_checkout_session("cs_storage_paid")
        fulfill_store_checkout_session("cs_storage_paid")

        checkout.refresh_from_db()
        self.assertEqual(checkout.status, StoreCheckoutStatus.FULFILLED)
        self.assertEqual(StoragePurchase.objects.filter(user=self.user).count(), 1)
        self.assertEqual(StorageCapacityGrant.objects.filter(user=self.user).count(), 1)
        purchase = StoragePurchase.objects.get(user=self.user)
        self.assertEqual(purchase.capacity_grant_id, StorageCapacityGrant.objects.get(user=self.user).id)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_mixed_checkout_fulfills_tool_and_storage_once(self, mock_get_stripe):
        checkout = self.make_checkout(self.payload(tool_interval="annual", storage_slug="storage-8gb"), session_id="cs_mixed_paid")
        stripe = MagicMock()
        stripe.checkout.Session.retrieve.return_value = self.stripe_session(
            checkout,
            mode="subscription",
            subscription={"id": "sub_mixed", "status": "active", "current_period_start": int(time.time()), "current_period_end": int(time.time()) + 31536000},
        )
        mock_get_stripe.return_value = stripe

        from backend.billing.services import fulfill_store_checkout_session
        fulfill_store_checkout_session("cs_mixed_paid")
        fulfill_store_checkout_session("cs_mixed_paid")

        self.assertEqual(ToolEntitlement.objects.filter(user=self.user, product__slug="blackbod").count(), 1)
        self.assertEqual(StoragePurchase.objects.filter(user=self.user).count(), 1)
        self.assertEqual(StorageCapacityGrant.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserSubscription.objects.get(user=self.user).billing_period, "yearly")

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_webhook_for_unknown_checkout_is_safe(self, mock_get_stripe):
        stripe = MagicMock()
        stripe.checkout.Session.retrieve.return_value = {
            "id": "cs_unknown",
            "status": "complete",
            "payment_status": "paid",
            "customer": "cus_unknown",
            "metadata": {"bonup_checkout_id": "999999"},
        }
        mock_get_stripe.return_value = stripe

        from backend.billing.services import fulfill_store_checkout_session
        result = fulfill_store_checkout_session("cs_unknown")

        self.assertIsNone(result)
        self.assertEqual(StoreCheckout.objects.count(), 0)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_webhook_dispatches_store_checkout_completed(self, mock_get_stripe):
        checkout = self.make_checkout(self.payload(storage_slug="storage-8gb"), session_id="cs_dispatch")
        session = self.stripe_session(checkout)
        stripe = MagicMock()
        stripe.Webhook.construct_event.return_value = {"type": "checkout.session.completed", "data": {"object": session}}
        stripe.checkout.Session.retrieve.return_value = session
        mock_get_stripe.return_value = stripe

        response = self.client.post(
            "/api/billing/webhook/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(StoragePurchase.objects.filter(user=self.user).count(), 1)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    @patch("backend.billing.services.handle_invoice_paid")
    def test_webhook_dispatches_invoice_paid(self, mock_handler, mock_get_stripe):
        stripe = MagicMock()
        stripe.Webhook.construct_event.return_value = {
            "type": "invoice.paid",
            "data": {"object": {"id": "in_x", "customer": "cus_x"}},
        }
        mock_get_stripe.return_value = stripe

        response = self.client.post(
            "/api/billing/webhook/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )

        self.assertEqual(response.status_code, 200)
        mock_handler.assert_called_once()


class CheckoutStatusAPITests(TestCase):
    def setUp(self):
        self.user = _make_user("status_user")
        self.other = _make_user("status_other")
        self.client = _authed_client(self.user)
        from backend.billing.store_quote import build_store_quote
        selection = {"tools": [], "storage_product_slug": "storage-8gb", "ai_product_slug": None}
        quote = build_store_quote(user=self.user, selection=selection)
        self.checkout = StoreCheckout.objects.create(
            user=self.user,
            status=StoreCheckoutStatus.FULFILLED,
            currency="USD",
            one_time_amount_snapshot=Decimal("18.00"),
            due_today_snapshot=Decimal("18.00"),
            selection_snapshot=selection,
            quote_snapshot=quote,
            stripe_checkout_session_id="cs_status",
            stripe_customer_id="cus_secretish",
        )

    def test_checkout_owner_can_retrieve_safe_status(self):
        response = self.client.get("/api/billing/checkout/cs_status/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "fulfilled")
        self.assertEqual(response.data["items"][0]["kind"], "storage")

    def test_other_customer_cannot_retrieve_status(self):
        client = _authed_client(self.other)
        response = client.get("/api/billing/checkout/cs_status/status/")
        self.assertEqual(response.status_code, 404)

    def test_status_response_contains_no_secret_or_raw_stripe_data(self):
        response = self.client.get("/api/billing/checkout/cs_status/status/")
        payload = json.dumps(response.data, default=str)
        self.assertNotIn("cus_secretish", payload)
        self.assertNotIn("stripe", payload.lower())


# ---------------------------------------------------------------------------
# SubscriptionAPIView gate lock
# ---------------------------------------------------------------------------

class SubscriptionGateLockTests(TestCase):

    def setUp(self):
        self.user = _make_user("gate_user")
        self.client = _authed_client(self.user)
        _make_plan("basic")

    @override_settings(**STRIPE_SETTINGS)
    def test_subscription_post_blocked_when_stripe_configured(self):
        resp = self.client.post("/api/billing/subscription/", {
            "plan_slug": "basic",
            "billing_period": "monthly",
        }, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("checkout_url", resp.data)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_subscription_post_allowed_when_stripe_not_configured(self):
        resp = self.client.post("/api/billing/subscription/", {
            "plan_slug": "basic",
            "billing_period": "monthly",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
