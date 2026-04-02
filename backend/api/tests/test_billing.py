# backend/api/tests/test_billing.py
#
# Tests for the Billing domain:
#   - Plan seeding (5 plans with correct values)
#   - Feature gates (can_create_contract, can_create_session, can_access_template,
#     get_ai_tier, has_feature, increment helpers)
#   - API endpoints (plans, subscription, invoices, usage)
#   - Gate integration: POST /api/contracts/, POST /api/sessions/, GET/retrieve /api/templates/

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.billing.models import Invoice, SubscriptionPlan, UserSubscription
from backend.billing.gates import (
    can_create_contract,
    can_create_session,
    can_access_template,
    consume_trial_contract,
    get_ai_tier,
    has_feature,
    increment_contracts_used,
    increment_sessions_used,
    start_trial,
)
from backend.contract_templates.models import ContractTemplate

from .helpers import authed_client, make_contract, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_plan(slug="business"):
    return SubscriptionPlan.objects.get(slug=slug)


def subscribe(user, plan_slug="business", billing_period="monthly", status="active"):
    plan = make_plan(plan_slug)
    return UserSubscription.objects.create(
        user=user,
        plan=plan,
        status=status,
        billing_period=billing_period,
        current_period_start=timezone.now(),
    )


def make_template(category="health_wellness", name="Test Template"):
    return ContractTemplate.objects.create(
        category=category,
        subcategory="general",
        name=name,
        description="A test template.",
        structure_type="ONE_TIME",
        is_active=True,
        tier_required="free",
    )


# ---------------------------------------------------------------------------
# Plan Seeding
# ---------------------------------------------------------------------------

class PlanSeedingTests(TestCase):

    def test_five_plans_seeded(self):
        self.assertEqual(SubscriptionPlan.objects.filter(is_active=True).count(), 5)

    def test_per_contract_plan(self):
        plan = SubscriptionPlan.objects.get(slug="per_contract")
        self.assertEqual(plan.price_monthly, Decimal("15.00"))
        self.assertIsNone(plan.price_yearly)
        self.assertEqual(plan.max_active_contracts, 1)
        self.assertEqual(plan.max_live_sessions_per_month, 0)
        self.assertTrue(plan.all_templates)
        self.assertFalse(plan.has_lifecycle)
        self.assertFalse(plan.has_notifications)
        self.assertFalse(plan.has_negotiation_prep)
        self.assertEqual(plan.ai_tier, "none")
        self.assertFalse(plan.has_priority_support)
        self.assertFalse(plan.has_early_access)

    def test_starter_plan(self):
        plan = SubscriptionPlan.objects.get(slug="starter")
        self.assertEqual(plan.price_monthly, Decimal("10.00"))
        self.assertEqual(plan.price_yearly, Decimal("100.00"))
        self.assertFalse(plan.all_templates)
        self.assertEqual(plan.templates_per_category, 1)
        self.assertEqual(plan.max_active_contracts, 3)
        self.assertEqual(plan.max_live_sessions_per_month, 1)
        self.assertTrue(plan.has_lifecycle)
        self.assertTrue(plan.has_notifications)
        self.assertTrue(plan.has_negotiation_prep)
        self.assertEqual(plan.ai_tier, "none")

    def test_professional_plan(self):
        plan = SubscriptionPlan.objects.get(slug="professional")
        self.assertEqual(plan.price_monthly, Decimal("83.00"))
        self.assertTrue(plan.all_templates)
        self.assertEqual(plan.excluded_categories, [])
        self.assertIsNone(plan.max_active_contracts)
        self.assertEqual(plan.max_live_sessions_per_month, 20)
        self.assertEqual(plan.ai_tier, "basic")

    def test_business_plan(self):
        plan = SubscriptionPlan.objects.get(slug="business")
        self.assertEqual(plan.price_monthly, Decimal("200.00"))
        self.assertTrue(plan.all_templates)
        self.assertIsNone(plan.max_active_contracts)
        self.assertEqual(plan.max_live_sessions_per_month, 60)
        self.assertEqual(plan.ai_tier, "advanced")

    def test_anchor_plan(self):
        plan = SubscriptionPlan.objects.get(slug="anchor")
        self.assertEqual(plan.price_monthly, Decimal("600.00"))
        self.assertTrue(plan.all_templates)
        self.assertIsNone(plan.max_active_contracts)
        self.assertIsNone(plan.max_live_sessions_per_month)
        self.assertEqual(plan.ai_tier, "full")
        self.assertTrue(plan.has_priority_support)
        self.assertTrue(plan.has_early_access)


# ---------------------------------------------------------------------------
# Feature Gates — can_create_contract
# ---------------------------------------------------------------------------

class CanCreateContractTests(TestCase):

    def setUp(self):
        self.user = make_user("u_cc", "u_cc@example.com")

    def test_no_subscription_blocked(self):
        allowed, msg = can_create_contract(self.user)
        self.assertFalse(allowed)
        self.assertIn("subscription", msg.lower())

    def test_cancelled_subscription_blocked(self):
        subscribe(self.user, "business", status="cancelled")
        allowed, msg = can_create_contract(self.user)
        self.assertFalse(allowed)

    def test_unlimited_plan_allowed(self):
        subscribe(self.user, "business")
        allowed, _ = can_create_contract(self.user)
        self.assertTrue(allowed)

    def test_per_contract_at_limit_blocked(self):
        sub = subscribe(self.user, "per_contract", billing_period="per_contract",
                        status="per_contract")
        sub.contracts_used_this_period = 1
        sub.save()
        allowed, msg = can_create_contract(self.user)
        self.assertFalse(allowed)
        self.assertIn("limit", msg.lower())

    def test_per_contract_under_limit_allowed(self):
        subscribe(self.user, "per_contract", billing_period="per_contract",
                  status="per_contract")
        allowed, _ = can_create_contract(self.user)
        self.assertTrue(allowed)

    def test_starter_at_limit_blocked(self):
        sub = subscribe(self.user, "starter")
        sub.contracts_used_this_period = 3
        sub.save()
        allowed, _ = can_create_contract(self.user)
        self.assertFalse(allowed)


# ---------------------------------------------------------------------------
# Feature Gates — can_create_session
# ---------------------------------------------------------------------------

class CanCreateSessionTests(TestCase):

    def setUp(self):
        self.user = make_user("u_cs", "u_cs@example.com")

    def test_no_subscription_blocked(self):
        allowed, msg = can_create_session(self.user)
        self.assertFalse(allowed)

    def test_per_contract_plan_blocked(self):
        subscribe(self.user, "per_contract", billing_period="per_contract",
                  status="per_contract")
        allowed, msg = can_create_session(self.user)
        self.assertFalse(allowed)
        self.assertIn("not included", msg.lower())

    def test_anchor_unlimited_allowed(self):
        subscribe(self.user, "anchor")
        allowed, _ = can_create_session(self.user)
        self.assertTrue(allowed)

    def test_professional_at_limit_blocked(self):
        sub = subscribe(self.user, "professional")
        sub.live_sessions_used_this_month = 20
        sub.save()
        allowed, msg = can_create_session(self.user)
        self.assertFalse(allowed)
        self.assertIn("limit", msg.lower())

    def test_professional_under_limit_allowed(self):
        sub = subscribe(self.user, "professional")
        sub.live_sessions_used_this_month = 19
        sub.save()
        allowed, _ = can_create_session(self.user)
        self.assertTrue(allowed)


# ---------------------------------------------------------------------------
# Feature Gates — can_access_template
# ---------------------------------------------------------------------------

class CanAccessTemplateTests(TestCase):

    def setUp(self):
        self.user = make_user("u_cat", "u_cat@example.com")
        self.hw_template = make_template("health_wellness", "HW Template")
        self.cs_template = make_template("creative_services", "CS Template")

    def test_no_subscription_blocked(self):
        allowed, _ = can_access_template(self.user, self.hw_template)
        self.assertFalse(allowed)

    def test_professional_allows_creative_services(self):
        subscribe(self.user, "professional")
        allowed, _ = can_access_template(self.user, self.cs_template)
        self.assertTrue(allowed)

    def test_professional_allowed_category(self):
        subscribe(self.user, "professional")
        allowed, _ = can_access_template(self.user, self.hw_template)
        self.assertTrue(allowed)

    def test_business_all_categories_allowed(self):
        subscribe(self.user, "business")
        allowed, _ = can_access_template(self.user, self.cs_template)
        self.assertTrue(allowed)

    def test_starter_allowed(self):
        subscribe(self.user, "starter")
        allowed, _ = can_access_template(self.user, self.hw_template)
        self.assertTrue(allowed)


# ---------------------------------------------------------------------------
# Feature Gates — get_ai_tier, has_feature, increment helpers
# ---------------------------------------------------------------------------

class MiscGateTests(TestCase):

    def setUp(self):
        self.user = make_user("u_mg", "u_mg@example.com")

    def test_get_ai_tier_no_subscription(self):
        self.assertEqual(get_ai_tier(self.user), "none")

    def test_get_ai_tier_anchor(self):
        subscribe(self.user, "anchor")
        self.assertEqual(get_ai_tier(self.user), "full")

    def test_get_ai_tier_professional(self):
        subscribe(self.user, "professional")
        self.assertEqual(get_ai_tier(self.user), "basic")

    def test_has_feature_no_subscription(self):
        self.assertFalse(has_feature(self.user, "lifecycle"))

    def test_has_feature_starter_has_lifecycle(self):
        subscribe(self.user, "starter")
        self.assertTrue(has_feature(self.user, "lifecycle"))
        self.assertTrue(has_feature(self.user, "notifications"))
        self.assertTrue(has_feature(self.user, "negotiation_prep"))

    def test_has_feature_per_contract_no_lifecycle(self):
        subscribe(self.user, "per_contract", billing_period="per_contract",
                  status="per_contract")
        self.assertFalse(has_feature(self.user, "lifecycle"))

    def test_has_feature_anchor_priority_support(self):
        subscribe(self.user, "anchor")
        self.assertTrue(has_feature(self.user, "priority_support"))
        self.assertTrue(has_feature(self.user, "early_access"))

    def test_increment_contracts_used(self):
        sub = subscribe(self.user, "starter")
        self.assertEqual(sub.contracts_used_this_period, 0)
        increment_contracts_used(self.user)
        sub.refresh_from_db()
        self.assertEqual(sub.contracts_used_this_period, 1)

    def test_increment_sessions_used(self):
        sub = subscribe(self.user, "business")
        self.assertEqual(sub.live_sessions_used_this_month, 0)
        increment_sessions_used(self.user)
        sub.refresh_from_db()
        self.assertEqual(sub.live_sessions_used_this_month, 1)


# ---------------------------------------------------------------------------
# API — GET /api/billing/plans/
# ---------------------------------------------------------------------------

class PlanListAPITests(TestCase):

    def setUp(self):
        self.user = make_user("u_pl", "u_pl@example.com")
        self.client = authed_client(self.user)

    def test_returns_five_plans(self):
        r = self.client.get("/api/billing/plans/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 5)

    def test_plan_has_expected_fields(self):
        r = self.client.get("/api/billing/plans/")
        slugs = {p["slug"] for p in r.data}
        self.assertIn("anchor", slugs)
        plan = next(p for p in r.data if p["slug"] == "anchor")
        self.assertTrue(plan["has_priority_support"])
        self.assertTrue(plan["has_early_access"])
        self.assertEqual(plan["ai_tier"], "full")


# ---------------------------------------------------------------------------
# API — GET/POST/DELETE /api/billing/subscription/
# ---------------------------------------------------------------------------

class SubscriptionAPITests(TestCase):

    def setUp(self):
        self.user = make_user("u_sub", "u_sub@example.com")
        self.client = authed_client(self.user)

    def test_get_no_subscription_returns_null(self):
        r = self.client.get("/api/billing/subscription/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["subscription"])

    def test_post_creates_subscription(self):
        r = self.client.post(
            "/api/billing/subscription/",
            {"plan_slug": "starter", "billing_period": "monthly"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["plan"]["slug"], "starter")
        self.assertEqual(r.data["status"], "active")

    def test_post_invalid_plan_returns_404(self):
        r = self.client.post(
            "/api/billing/subscription/",
            {"plan_slug": "nonexistent"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_post_missing_plan_slug_returns_400(self):
        r = self.client.post("/api/billing/subscription/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_post_changes_existing_plan(self):
        subscribe(self.user, "starter")
        r = self.client.post(
            "/api/billing/subscription/",
            {"plan_slug": "business"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["plan"]["slug"], "business")

    def test_get_returns_subscription_after_create(self):
        subscribe(self.user, "business")
        r = self.client.get("/api/billing/subscription/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["plan"]["slug"], "business")

    def test_delete_cancels_subscription(self):
        subscribe(self.user, "business")
        r = self.client.delete("/api/billing/subscription/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "cancelled")
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "cancelled")

    def test_delete_no_subscription_returns_404(self):
        r = self.client.delete("/api/billing/subscription/")
        self.assertEqual(r.status_code, 404)

    def test_per_contract_subscription_status(self):
        r = self.client.post(
            "/api/billing/subscription/",
            {"plan_slug": "per_contract", "billing_period": "per_contract"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "per_contract")


# ---------------------------------------------------------------------------
# API — GET /api/billing/invoices/
# ---------------------------------------------------------------------------

class InvoiceAPITests(TestCase):

    def setUp(self):
        self.user = make_user("u_inv", "u_inv@example.com")
        self.client = authed_client(self.user)

    def test_empty_invoice_list(self):
        r = self.client.get("/api/billing/invoices/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(r.data["results"], [])

    def test_invoice_appears_in_list(self):
        sub = subscribe(self.user, "business")
        Invoice.objects.create(
            user=self.user,
            subscription=sub,
            amount=Decimal("200.00"),
            currency="USD",
            status="paid",
            description="Monthly charge",
        )
        r = self.client.get("/api/billing/invoices/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["amount"], "200.00")
        self.assertEqual(r.data["results"][0]["status"], "paid")

    def test_invoices_paginated(self):
        sub = subscribe(self.user, "business")
        for i in range(25):
            Invoice.objects.create(
                user=self.user,
                subscription=sub,
                amount=Decimal("10.00"),
                status="paid",
            )
        r = self.client.get("/api/billing/invoices/?page=1")
        self.assertEqual(r.data["count"], 25)
        self.assertEqual(len(r.data["results"]), 20)
        r2 = self.client.get("/api/billing/invoices/?page=2")
        self.assertEqual(len(r2.data["results"]), 5)


# ---------------------------------------------------------------------------
# API — GET /api/billing/usage/
# ---------------------------------------------------------------------------

class UsageAPITests(TestCase):

    def setUp(self):
        self.user = make_user("u_us", "u_us@example.com")
        self.client = authed_client(self.user)

    def test_no_subscription_returns_null(self):
        r = self.client.get("/api/billing/usage/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["subscription"])

    def test_usage_returns_counters(self):
        sub = subscribe(self.user, "professional")
        sub.contracts_used_this_period = 5
        sub.live_sessions_used_this_month = 3
        sub.save()
        r = self.client.get("/api/billing/usage/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["contracts_used"], 5)
        self.assertEqual(r.data["sessions_used_this_month"], 3)
        self.assertEqual(r.data["contracts_limit"], None)
        self.assertEqual(r.data["sessions_limit_per_month"], 20)


# ---------------------------------------------------------------------------
# Gate Integration — POST /api/contracts/
# ---------------------------------------------------------------------------

class ContractGateIntegrationTests(TestCase):

    def setUp(self):
        self.user = make_user("u_cgx", "u_cgx@example.com")
        self.client = authed_client(self.user)

    def test_no_subscription_blocks_contract_creation(self):
        r = self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertIn("subscription", r.data["error"].lower())

    def test_business_subscription_allows_contract_creation(self):
        subscribe(self.user, "business")
        r = self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

    def test_starter_at_limit_blocks_contract_creation(self):
        sub = subscribe(self.user, "starter")
        sub.contracts_used_this_period = 3
        sub.save()
        r = self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_contract_creation_increments_counter(self):
        sub = subscribe(self.user, "business")
        self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        sub.refresh_from_db()
        self.assertEqual(sub.contracts_used_this_period, 1)


# ---------------------------------------------------------------------------
# Gate Integration — POST /api/sessions/
# ---------------------------------------------------------------------------

class SessionGateIntegrationTests(TestCase):

    def setUp(self):
        self.user = make_user("u_sgx", "u_sgx@example.com")
        self.other = make_user("u_sgx_other", "u_sgx_other@example.com")
        self.client = authed_client(self.user)
        self.contract = make_contract(self.user, self.other.email)

    def test_no_subscription_blocks_session_creation(self):
        r = self.client.post(
            "/api/sessions/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_per_contract_plan_blocks_session_creation(self):
        subscribe(self.user, "per_contract", billing_period="per_contract",
                  status="per_contract")
        r = self.client.post(
            "/api/sessions/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertIn("not included", r.data["error"].lower())

    def test_business_plan_allows_session_creation(self):
        subscribe(self.user, "business")
        r = self.client.post(
            "/api/sessions/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

    def test_session_creation_increments_counter(self):
        sub = subscribe(self.user, "business")
        self.client.post(
            "/api/sessions/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )
        sub.refresh_from_db()
        self.assertEqual(sub.live_sessions_used_this_month, 1)


# ---------------------------------------------------------------------------
# Gate Integration — GET /api/templates/ and GET /api/templates/<id>/
# ---------------------------------------------------------------------------

class TemplateGateIntegrationTests(TestCase):

    def setUp(self):
        self.user = make_user("u_tgx", "u_tgx@example.com")
        self.client = authed_client(self.user)
        self.hw = make_template("health_wellness", "HW Template Gate")
        self.cs = make_template("creative_services", "CS Template Gate")

    def test_no_subscription_returns_empty_list(self):
        r = self.client.get("/api/templates/")
        self.assertEqual(r.status_code, 200)
        names = [t["name"] for t in r.data]
        self.assertNotIn("HW Template Gate", names)
        self.assertNotIn("CS Template Gate", names)

    def test_business_plan_sees_all_templates(self):
        subscribe(self.user, "business")
        r = self.client.get("/api/templates/")
        self.assertEqual(r.status_code, 200)
        names = [t["name"] for t in r.data]
        self.assertIn("HW Template Gate", names)
        self.assertIn("CS Template Gate", names)

    def test_professional_sees_all_templates(self):
        subscribe(self.user, "professional")
        r = self.client.get("/api/templates/")
        self.assertEqual(r.status_code, 200)
        names = [t["name"] for t in r.data]
        self.assertIn("HW Template Gate", names)
        self.assertIn("CS Template Gate", names)

    def test_detail_allowed_for_professional(self):
        subscribe(self.user, "professional")
        r = self.client.get(f"/api/templates/{self.cs.id}/")
        self.assertEqual(r.status_code, 200)

    def test_detail_allowed_for_accessible_template(self):
        subscribe(self.user, "professional")
        r = self.client.get(f"/api/templates/{self.hw.id}/")
        self.assertEqual(r.status_code, 200)

    def test_detail_blocked_no_subscription(self):
        r = self.client.get(f"/api/templates/{self.hw.id}/")
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Trial — start_trial / consume_trial_contract gates
# ---------------------------------------------------------------------------

class TrialGateTests(TestCase):

    def setUp(self):
        self.user = make_user("u_tr", "u_tr@example.com")

    def test_start_trial_creates_subscription(self):
        start_trial(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "trialing")
        self.assertEqual(sub.plan.slug, "business")
        self.assertEqual(sub.billing_period, "monthly")
        self.assertEqual(sub.trial_contracts_remaining, 1)

    def test_start_trial_idempotent(self):
        start_trial(self.user)
        start_trial(self.user)
        self.assertEqual(UserSubscription.objects.filter(user=self.user).count(), 1)

    def test_trial_allows_first_contract(self):
        start_trial(self.user)
        allowed, _ = can_create_contract(self.user)
        self.assertTrue(allowed)

    def test_trial_blocks_when_remaining_zero(self):
        start_trial(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        sub.trial_contracts_remaining = 0
        sub.save()
        allowed, msg = can_create_contract(self.user)
        self.assertFalse(allowed)
        self.assertIn("trial", msg.lower())

    def test_consume_decrements_remaining(self):
        start_trial(self.user)
        consume_trial_contract(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.trial_contracts_remaining, 0)

    def test_consume_transitions_to_no_subscription(self):
        start_trial(self.user)
        consume_trial_contract(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "no_subscription")

    def test_consume_noop_for_non_trialing_user(self):
        subscribe(self.user, "business")
        consume_trial_contract(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "active")

    def test_no_subscription_status_blocks_contract(self):
        start_trial(self.user)
        consume_trial_contract(self.user)
        allowed, _ = can_create_contract(self.user)
        self.assertFalse(allowed)


# ---------------------------------------------------------------------------
# Trial — registration auto-creates trial
# ---------------------------------------------------------------------------

class TrialRegistrationTests(TestCase):

    def test_registration_creates_trial_subscription(self):
        r = authed_client(make_user("dummy_reg", "dummy_reg@example.com")).post(
            "/api/users/register/",
            {
                "username": "trialuser",
                "email": "trialuser@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        # Registration is open (AllowAny) so use an unauthenticated client
        from rest_framework.test import APIClient
        client = APIClient()
        r = client.post(
            "/api/users/register/",
            {
                "username": "trialuser2",
                "email": "trialuser2@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username="trialuser2")
        sub = UserSubscription.objects.get(user=user)
        self.assertEqual(sub.status, "trialing")
        self.assertEqual(sub.plan.slug, "business")
        self.assertEqual(sub.trial_contracts_remaining, 1)

    def test_registered_user_can_create_one_contract(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.post(
            "/api/users/register/",
            {
                "username": "trialcreate",
                "email": "trialcreate@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username="trialcreate")
        authed = authed_client(user)
        r = authed.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

    def test_registered_user_blocked_after_trial_contract(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.post(
            "/api/users/register/",
            {
                "username": "trialexpiry",
                "email": "trialexpiry@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username="trialexpiry")
        authed = authed_client(user)
        # First contract uses the trial
        authed.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        # Second contract should be blocked
        r = authed.post(
            "/api/contracts/",
            {"counterparty_email": "other2@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_trial_status_after_expiry(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.post(
            "/api/users/register/",
            {
                "username": "trialstatus",
                "email": "trialstatus@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username="trialstatus")
        authed = authed_client(user)
        # Use the trial contract
        authed.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        sub = UserSubscription.objects.get(user=user)
        self.assertEqual(sub.status, "no_subscription")
        self.assertEqual(sub.trial_contracts_remaining, 0)


# ---------------------------------------------------------------------------
# Trial — GET /api/billing/trial/ endpoint
# ---------------------------------------------------------------------------

class TrialAPITests(TestCase):

    def setUp(self):
        self.user = make_user("u_tapi", "u_tapi@example.com")
        self.client = authed_client(self.user)

    def test_trial_endpoint_no_subscription(self):
        r = self.client.get("/api/billing/trial/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_trial"])
        self.assertFalse(r.data["trial_expired"])
        self.assertEqual(r.data["trial_contracts_remaining"], 0)
        self.assertIsNone(r.data["plan"])

    def test_trial_endpoint_active_trial(self):
        start_trial(self.user)
        r = self.client.get("/api/billing/trial/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_trial"])
        self.assertFalse(r.data["trial_expired"])
        self.assertEqual(r.data["trial_contracts_remaining"], 1)
        self.assertEqual(r.data["plan"], "business")
        self.assertEqual(r.data["status"], "trialing")

    def test_trial_endpoint_after_expiry(self):
        start_trial(self.user)
        consume_trial_contract(self.user)
        r = self.client.get("/api/billing/trial/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_trial"])
        self.assertTrue(r.data["trial_expired"])
        self.assertEqual(r.data["trial_contracts_remaining"], 0)
        self.assertEqual(r.data["status"], "no_subscription")

    def test_trial_endpoint_active_subscription_not_trial(self):
        subscribe(self.user, "business")
        r = self.client.get("/api/billing/trial/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_trial"])
        self.assertFalse(r.data["trial_expired"])
        self.assertEqual(r.data["plan"], "business")
