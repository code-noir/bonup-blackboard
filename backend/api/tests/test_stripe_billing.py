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
from rest_framework.test import APIClient

from backend.billing.models import Invoice, SubscriptionPlan, UserSubscription

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
        self.assertEqual(sub.plan.slug, "starter")
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
        _make_plan("starter")
        _make_plan("professional")
        _make_plan("business")
        _make_plan("anchor")

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_or_create_stripe_customer", return_value="cus_co")
    @patch("backend.billing.services.get_stripe")
    def test_checkout_returns_checkout_url(self, mock_get_stripe, _cust):
        stripe = MagicMock()
        stripe.checkout.Session.create.return_value = {"url": "https://checkout.stripe.com/go"}
        mock_get_stripe.return_value = stripe

        resp = self.client.post("/api/billing/checkout/", {
            "plan_slug": "starter",
            "success_url": "https://app.example.com/success",
            "cancel_url": "https://app.example.com/cancel",
        }, format="json")

        self.assertEqual(resp.status_code, 201)
        self.assertIn("checkout_url", resp.data)

    @override_settings(**STRIPE_SETTINGS)
    def test_checkout_rejects_missing_plan(self):
        resp = self.client.post("/api/billing/checkout/", {
            "success_url": "https://x.com/s",
            "cancel_url": "https://x.com/c",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    @override_settings(**STRIPE_SETTINGS)
    def test_checkout_rejects_invalid_plan(self):
        resp = self.client.post("/api/billing/checkout/", {
            "plan_slug": "sol_member",
            "success_url": "https://x.com/s",
            "cancel_url": "https://x.com/c",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_checkout_503_when_stripe_not_configured(self):
        resp = self.client.post("/api/billing/checkout/", {
            "plan_slug": "starter",
            "success_url": "https://x.com/s",
            "cancel_url": "https://x.com/c",
        }, format="json")
        self.assertEqual(resp.status_code, 503)


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
# WebhookAPIView
# ---------------------------------------------------------------------------

class WebhookAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()  # unauthenticated — webhook is public

    def _post_event(self, event_type, data_object, settings_override=None):
        payload = json.dumps({"type": event_type, "data": {"object": data_object}})
        override = settings_override or {**STRIPE_SETTINGS, "STRIPE_WEBHOOK_SECRET": ""}
        with self.settings(**override):
            return self.client.post(
                "/api/billing/webhook/",
                data=payload,
                content_type="application/json",
            )

    def test_webhook_returns_200_for_known_event(self):
        user = _make_user("wh_user")
        plan = _make_plan("starter")
        _make_sub(user, plan, stripe_customer_id="cus_wh")

        resp = self._post_event("invoice.payment_failed", {
            "id": "in_wh", "customer": "cus_wh",
        })
        self.assertEqual(resp.status_code, 200)

    def test_webhook_returns_200_for_unknown_event(self):
        resp = self._post_event("payment_intent.created", {})
        self.assertEqual(resp.status_code, 200)

    def test_webhook_400_for_invalid_json(self):
        with self.settings(**{**STRIPE_SETTINGS, "STRIPE_WEBHOOK_SECRET": ""}):
            resp = self.client.post(
                "/api/billing/webhook/",
                data="not-json",
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)

    @override_settings(**STRIPE_SETTINGS)
    @patch("backend.billing.services.get_stripe")
    def test_webhook_validates_signature_when_secret_set(self, mock_get_stripe):
        stripe = MagicMock()
        # Simulate signature failure
        import stripe as real_stripe
        stripe.Webhook.construct_event.side_effect = real_stripe.error.SignatureVerificationError(
            "bad sig", "fake_sig"
        )
        mock_get_stripe.return_value = stripe

        resp = self.client.post(
            "/api/billing/webhook/",
            data=json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=fake,v1=fake",
        )
        self.assertEqual(resp.status_code, 400)

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

        resp = self.client.post(
            "/api/billing/webhook/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        self.assertEqual(resp.status_code, 200)
        mock_handler.assert_called_once()


# ---------------------------------------------------------------------------
# SubscriptionAPIView gate lock
# ---------------------------------------------------------------------------

class SubscriptionGateLockTests(TestCase):

    def setUp(self):
        self.user = _make_user("gate_user")
        self.client = _authed_client(self.user)
        _make_plan("starter")

    @override_settings(**STRIPE_SETTINGS)
    def test_subscription_post_blocked_when_stripe_configured(self):
        resp = self.client.post("/api/billing/subscription/", {
            "plan_slug": "starter",
            "billing_period": "monthly",
        }, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("checkout_url", resp.data)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_subscription_post_allowed_when_stripe_not_configured(self):
        resp = self.client.post("/api/billing/subscription/", {
            "plan_slug": "starter",
            "billing_period": "monthly",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
