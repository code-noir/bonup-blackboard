# backend/api/tests/test_billing.py
#
# Tests for the Billing domain:
#   - Plan seeding (5 plans with correct values)
#   - Feature gates (can_create_contract, can_create_session, can_access_template,
#     get_ai_tier, has_feature, increment helpers)
#   - API endpoints (plans, subscription, invoices, usage)
#   - Gate integration: POST /api/contracts/, POST /api/sessions/, GET/retrieve /api/templates/

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.billing.models import Invoice, SubscriptionPlan, UserSubscription
from backend.billing.gates import (
    can_create_contract,
    can_create_session,
    can_access_template,
    can_create_sol,
    can_create_business_entity,
    consume_trial_contract,
    get_ai_tier,
    has_feature,
    increment_contracts_used,
    increment_sessions_used,
    max_businesses,
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

    def test_six_active_plans_seeded(self):
        self.assertEqual(SubscriptionPlan.objects.filter(is_active=True).count(), 6)

    def test_sol_member_plan(self):
        plan = SubscriptionPlan.objects.get(slug="sol_member")
        self.assertEqual(plan.display_name, "Sol Member")
        self.assertEqual(plan.price_monthly, Decimal("10.00"))
        self.assertIsNone(plan.price_yearly)
        self.assertEqual(plan.max_active_contracts, 3)
        self.assertEqual(plan.max_live_sessions_per_month, 1)
        self.assertTrue(plan.has_lifecycle)
        self.assertTrue(plan.has_notifications)
        self.assertTrue(plan.has_negotiation_prep)
        self.assertFalse(plan.all_templates)
        self.assertEqual(plan.templates_per_category, 1)
        self.assertTrue(plan.has_sol)
        self.assertEqual(plan.ai_tier, "none")
        self.assertFalse(plan.has_priority_support)
        self.assertFalse(plan.has_early_access)

    def test_trial_plan(self):
        plan = SubscriptionPlan.objects.get(slug="trial")
        self.assertEqual(plan.display_name, "Blackbòd Trial")
        self.assertEqual(plan.price_monthly, Decimal("0.00"))
        self.assertIsNone(plan.price_yearly)
        self.assertIsNone(plan.max_active_contracts)
        self.assertEqual(plan.max_live_sessions_per_month, 20)
        self.assertTrue(plan.has_lifecycle)
        self.assertTrue(plan.has_notifications)
        self.assertTrue(plan.has_negotiation_prep)
        self.assertTrue(plan.all_templates)
        self.assertTrue(plan.has_sol)
        self.assertEqual(plan.ai_tier, "basic")
        self.assertFalse(plan.has_priority_support)
        self.assertFalse(plan.has_early_access)

    def test_per_contract_plan(self):
        plan = SubscriptionPlan.objects.get(slug="per_contract")
        self.assertEqual(plan.price_monthly, Decimal("25.00"))
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

    def test_basic_plan(self):
        plan = SubscriptionPlan.objects.get(slug="basic")
        self.assertEqual(plan.display_name, "Blackbòd Basic")
        self.assertEqual(plan.price_monthly, Decimal("19.00"))
        self.assertEqual(plan.price_yearly, Decimal("100.00"))
        self.assertFalse(plan.all_templates)
        self.assertEqual(plan.templates_per_category, 1)
        # Unlimited personal contracts — confirmed commercial rule
        self.assertIsNone(plan.max_active_contracts)
        self.assertEqual(plan.max_live_sessions_per_month, 1)
        self.assertTrue(plan.has_lifecycle)
        self.assertTrue(plan.has_notifications)
        self.assertTrue(plan.has_negotiation_prep)
        self.assertEqual(plan.ai_tier, "none")
        self.assertFalse(plan.has_sol)

    def test_professional_plan(self):
        plan = SubscriptionPlan.objects.get(slug="professional")
        self.assertEqual(plan.display_name, "Blackbòd Professional")
        self.assertEqual(plan.price_monthly, Decimal("149.00"))
        self.assertTrue(plan.all_templates)
        self.assertEqual(plan.excluded_categories, [])
        self.assertIsNone(plan.max_active_contracts)
        self.assertEqual(plan.max_live_sessions_per_month, 20)
        self.assertEqual(plan.ai_tier, "basic")
        # Sol manager starts at Pro — confirmed commercial rule
        self.assertTrue(plan.has_sol)

    def test_advanced_plan(self):
        plan = SubscriptionPlan.objects.get(slug="advanced")
        self.assertEqual(plan.price_monthly, Decimal("399.00"))
        self.assertTrue(plan.all_templates)
        self.assertIsNone(plan.max_active_contracts)
        self.assertEqual(plan.max_live_sessions_per_month, 60)
        self.assertEqual(plan.ai_tier, "advanced")

    def test_anchor_plan_is_legacy_inactive(self):
        plan = SubscriptionPlan.objects.get(slug="anchor")
        self.assertEqual(plan.display_name, "Blackboard Enterprise (Legacy)")
        self.assertFalse(plan.is_active)
        self.assertEqual(plan.price_monthly, Decimal("999.00"))
        self.assertTrue(plan.all_templates)
        self.assertIsNone(plan.max_active_contracts)
        self.assertIsNone(plan.max_live_sessions_per_month)
        self.assertEqual(plan.ai_tier, "full")
        self.assertTrue(plan.has_priority_support)
        self.assertTrue(plan.has_early_access)
        self.assertTrue(plan.has_sol)


# ---------------------------------------------------------------------------
# Feature Gates — can_create_contract
# ---------------------------------------------------------------------------

class CanCreateContractTests(TestCase):

    def setUp(self):
        self.user = make_user("u_cc", "u_cc@example.com")

    def test_no_subscription_allowed_without_creating_subscription(self):
        allowed, msg = can_create_contract(self.user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")
        self.assertFalse(UserSubscription.objects.filter(user=self.user).exists())

    def test_inactive_subscription_allowed_without_resetting_subscription(self):
        sub = subscribe(self.user, "business", status="cancelled")
        allowed, msg = can_create_contract(self.user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")
        sub.refresh_from_db()
        self.assertEqual(sub.status, "cancelled")

    def test_existing_contract_with_inactive_subscription_still_allowed(self):
        sub = subscribe(self.user, "business", status="cancelled")
        make_contract(self.user, "counterparty@example.com")
        allowed, msg = can_create_contract(self.user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")
        sub.refresh_from_db()
        self.assertEqual(sub.status, "cancelled")

    def test_per_contract_at_limit_allowed_in_build_mode(self):
        sub = subscribe(self.user, "per_contract", billing_period="per_contract",
                        status="per_contract")
        sub.contracts_used_this_period = 1
        sub.save()
        allowed, msg = can_create_contract(self.user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_starter_usage_limit_not_enforced_in_build_mode(self):
        sub = subscribe(self.user, "starter")
        sub.contracts_used_this_period = 100
        sub.save()
        allowed, msg = can_create_contract(self.user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")


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

    def test_no_subscription_allowed(self):
        allowed, _ = can_access_template(self.user, self.hw_template)
        self.assertTrue(allowed)

    def test_inactive_subscription_status_allowed(self):
        subscribe(self.user, "business", status="no_subscription")
        allowed, _ = can_access_template(self.user, self.hw_template)
        self.assertTrue(allowed)

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

    def test_has_feature_no_subscription_allows_lifecycle_build_flow(self):
        self.assertTrue(has_feature(self.user, "lifecycle"))
        self.assertTrue(has_feature(self.user, "negotiation_prep"))

    def test_has_feature_starter_has_lifecycle(self):
        subscribe(self.user, "starter")
        self.assertTrue(has_feature(self.user, "lifecycle"))
        self.assertTrue(has_feature(self.user, "notifications"))
        self.assertTrue(has_feature(self.user, "negotiation_prep"))

    def test_has_feature_per_contract_allows_lifecycle_build_flow(self):
        subscribe(self.user, "per_contract", billing_period="per_contract",
                  status="per_contract")
        self.assertTrue(has_feature(self.user, "lifecycle"))
        self.assertTrue(has_feature(self.user, "negotiation_prep"))

    def test_has_feature_anchor_priority_support(self):
        subscribe(self.user, "anchor")
        self.assertTrue(has_feature(self.user, "priority_support"))
        self.assertTrue(has_feature(self.user, "early_access"))

    def test_increment_contracts_used_noop_in_build_mode(self):
        sub = subscribe(self.user, "starter")
        self.assertEqual(sub.contracts_used_this_period, 0)
        increment_contracts_used(self.user)
        sub.refresh_from_db()
        self.assertEqual(sub.contracts_used_this_period, 0)

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

    def test_returns_six_active_plans(self):
        r = self.client.get("/api/billing/plans/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 6)

    def test_plan_has_expected_fields(self):
        r = self.client.get("/api/billing/plans/")
        slugs = {p["slug"] for p in r.data}
        self.assertIn("advanced", slugs)
        self.assertNotIn("anchor", slugs)
        plan = next(p for p in r.data if p["slug"] == "advanced")
        self.assertFalse(plan["has_priority_support"])
        self.assertFalse(plan["has_early_access"])
        self.assertEqual(plan["ai_tier"], "advanced")


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
            {"plan_slug": "basic", "billing_period": "monthly"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["plan"]["slug"], "basic")
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
        subscribe(self.user, "basic")
        r = self.client.post(
            "/api/billing/subscription/",
            {"plan_slug": "advanced"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["plan"]["slug"], "advanced")

    def test_get_returns_subscription_after_create(self):
        subscribe(self.user, "advanced")
        r = self.client.get("/api/billing/subscription/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["plan"]["slug"], "advanced")

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

    def test_no_subscription_allows_contract_creation(self):
        r = self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

    def test_business_subscription_allows_contract_creation(self):
        subscribe(self.user, "business")
        r = self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

    def test_starter_allows_contracts_past_old_limit(self):
        """Starter is unlimited — the old limit of 3 no longer applies."""
        sub = subscribe(self.user, "starter")
        sub.contracts_used_this_period = 10
        sub.save()
        r = self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)

    def test_contract_creation_does_not_mutate_billing_counter_in_build_mode(self):
        sub = subscribe(self.user, "business")
        self.client.post(
            "/api/contracts/",
            {"counterparty_email": "other@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        sub.refresh_from_db()
        self.assertEqual(sub.contracts_used_this_period, 0)


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

    def test_no_subscription_sees_all_templates(self):
        r = self.client.get("/api/templates/")
        self.assertEqual(r.status_code, 200)
        names = [t["name"] for t in r.data]
        self.assertIn("HW Template Gate", names)
        self.assertIn("CS Template Gate", names)

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

    def test_detail_allowed_no_subscription(self):
        r = self.client.get(f"/api/templates/{self.hw.id}/")
        self.assertEqual(r.status_code, 200)


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
        self.assertEqual(sub.plan.slug, "trial")
        self.assertEqual(sub.billing_period, "monthly")
        self.assertEqual(sub.trial_contracts_remaining, 0)

    def test_start_trial_idempotent(self):
        start_trial(self.user)
        start_trial(self.user)
        self.assertEqual(UserSubscription.objects.filter(user=self.user).count(), 1)

    def test_trial_allows_first_contract(self):
        start_trial(self.user)
        allowed, _ = can_create_contract(self.user)
        self.assertTrue(allowed)

    def test_trial_remaining_zero_still_allows_contract_build_flow(self):
        start_trial(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        sub.trial_contracts_remaining = 0
        sub.save()
        allowed, msg = can_create_contract(self.user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_consume_does_not_decrement_remaining_in_build_mode(self):
        start_trial(self.user)
        consume_trial_contract(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.trial_contracts_remaining, 0)

    def test_consume_does_not_transition_to_no_subscription_in_build_mode(self):
        start_trial(self.user)
        consume_trial_contract(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "trialing")

    def test_consume_noop_for_non_trialing_user(self):
        subscribe(self.user, "business")
        consume_trial_contract(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, "active")

    def test_no_subscription_status_allows_contract_build_flow(self):
        start_trial(self.user)
        sub = UserSubscription.objects.get(user=self.user)
        sub.status = "no_subscription"
        sub.save(update_fields=["status"])
        allowed, msg = can_create_contract(self.user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")


# ---------------------------------------------------------------------------
# Trial — registration auto-creates trial
# ---------------------------------------------------------------------------

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
        self.assertEqual(r.data["trial_contracts_remaining"], 0)
        self.assertEqual(r.data["plan"], "trial")
        self.assertEqual(r.data["status"], "trialing")

    def test_trial_endpoint_after_expiry(self):
        start = timezone.now() - timedelta(days=15)
        plan = SubscriptionPlan.objects.get(slug="trial")
        UserSubscription.objects.create(
            user=self.user,
            plan=plan,
            status="trialing",
            billing_period="monthly",
            current_period_start=start,
            current_period_end=start + timedelta(days=14),
            trial_start=start,
            trial_end=start + timedelta(days=14),
        )
        r = self.client.get("/api/billing/trial/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_trial"])
        self.assertTrue(r.data["trial_expired"])
        self.assertFalse(r.data["is_trial_valid"])
        self.assertIsNone(r.data["effective_blackbod_tier"])
        self.assertEqual(r.data["trial_contracts_remaining"], 0)
        self.assertEqual(r.data["status"], "trialing")

    def test_trial_endpoint_active_subscription_not_trial(self):
        subscribe(self.user, "business")
        r = self.client.get("/api/billing/trial/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_trial"])
        self.assertFalse(r.data["trial_expired"])
        self.assertEqual(r.data["plan"], "business")


# ---------------------------------------------------------------------------
# Sol Manager Eligibility — confirmed commercial rule: Pro or higher
# ---------------------------------------------------------------------------

class SolManagerEligibilityTests(TestCase):
    """
    Sol manager creation requires a paid Pro or higher subscription.
    Confirmed plan eligibility:
      professional (Pro)     ✅
      business               ✅
      anchor (Enterprise)    ✅
      starter                ❌
      sol_member             ❌
      per_contract (PAYG)    ❌
      trialing               ❌  (free trial — not a paid subscription)
      no subscription        ❌
    """

    SOL_URL = "/api/sol/"
    SOL_PAYLOAD = {
        "name": "Test Sol",
        "frequency": "monthly",
        "contribution_amount": "100.00",
        "start_date": "2026-06-01",
    }

    def _make_manager(self, slug, status="active", billing_period="monthly"):
        user = make_user(f"mgr_{slug}", f"mgr_{slug}@example.com")
        plan = SubscriptionPlan.objects.get(slug=slug)
        UserSubscription.objects.create(
            user=user,
            plan=plan,
            status=status,
            billing_period=billing_period,
            current_period_start=timezone.now(),
        )
        return user

    def test_professional_can_create_sol(self):
        user = self._make_manager("professional")
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 201)

    def test_business_can_create_sol(self):
        user = self._make_manager("business")
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 201)

    def test_anchor_can_create_sol(self):
        user = self._make_manager("anchor")
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 201)

    def test_starter_cannot_create_sol(self):
        user = self._make_manager("starter")
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 403)

    def test_sol_member_cannot_create_sol(self):
        user = self._make_manager("sol_member")
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 403)

    def test_per_contract_cannot_create_sol(self):
        user = self._make_manager("per_contract", status="per_contract",
                                  billing_period="per_contract")
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 403)

    def test_trialing_cannot_create_sol(self):
        """Free trial (trialing status) does not qualify as a paid Pro+ subscription."""
        user = make_user("mgr_trial", "mgr_trial@example.com")
        start_trial(user)  # puts user on the trial plan with trialing status
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 403)

    def test_no_subscription_cannot_create_sol(self):
        user = make_user("mgr_nosub", "mgr_nosub@example.com")
        r = authed_client(user).post(self.SOL_URL, self.SOL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Business Entity Limits — confirmed commercial model
# ---------------------------------------------------------------------------

class BusinessEntityLimitTests(TestCase):
    """
    Confirmed per-plan business entity limits:
      starter       → 0
      professional  → 1
      business      → 4
      anchor        → 35
    """

    def _user_on_plan(self, slug, status="active"):
        user = make_user(f"biz_{slug}", f"biz_{slug}@example.com")
        plan = SubscriptionPlan.objects.get(slug=slug)
        UserSubscription.objects.create(
            user=user,
            plan=plan,
            status=status,
            billing_period="monthly",
            current_period_start=timezone.now(),
        )
        return user

    def test_starter_entity_limit_is_zero(self):
        user = self._user_on_plan("starter")
        self.assertEqual(max_businesses(user), 0)
        allowed, _ = can_create_business_entity(user)
        self.assertFalse(allowed)

    def test_professional_entity_limit_is_one(self):
        user = self._user_on_plan("professional")
        self.assertEqual(max_businesses(user), 1)
        allowed, _ = can_create_business_entity(user)
        self.assertTrue(allowed)

    def test_business_entity_limit_is_four(self):
        user = self._user_on_plan("business")
        self.assertEqual(max_businesses(user), 4)
        allowed, _ = can_create_business_entity(user)
        self.assertTrue(allowed)

    def test_anchor_entity_limit_is_thirty_five(self):
        user = self._user_on_plan("anchor")
        self.assertEqual(max_businesses(user), 35)
        allowed, _ = can_create_business_entity(user)
        self.assertTrue(allowed)

    def test_sol_member_entity_limit_is_zero(self):
        user = self._user_on_plan("sol_member")
        self.assertEqual(max_businesses(user), 0)
        allowed, _ = can_create_business_entity(user)
        self.assertFalse(allowed)


# ---------------------------------------------------------------------------
# Trial Compatibility — time-based trial in build mode
# ---------------------------------------------------------------------------

class FreeTierContractLimitTests(TestCase):
    """
    The 14-day trial is time-based and does not consume or delete contract data.
    The legacy trial_contracts_remaining field is retained for compatibility but is no longer consumed in build mode.
    """

    def test_trial_counter_is_not_used_for_entitlement(self):
        """
        Trial entitlement is time-based, not a per-contract counter.
        """
        user = make_user("free_entity", "free_entity@example.com")
        start_trial(user)
        sub = UserSubscription.objects.get(user=user)
        self.assertEqual(sub.trial_contracts_remaining, 0)

    def test_trial_second_contract_allowed_in_build_mode(self):
        """Contract creation remains bypassed during Blackboard build mode."""
        user = make_user("free_second", "free_second@example.com")
        start_trial(user)
        client = authed_client(user)
        # First contract (personal context)
        r1 = client.post(
            "/api/contracts/",
            {"counterparty_email": "a@example.com", "structure_type": "ONE_TIME",
             "entity_type": "personal"},
            format="json",
        )
        self.assertEqual(r1.status_code, 201)
        # Second contract is allowed in Blackboard build mode.
        r2 = client.post(
            "/api/contracts/",
            {"counterparty_email": "b@example.com", "structure_type": "ONE_TIME",
             "entity_type": "personal"},
            format="json",
        )
        self.assertEqual(r2.status_code, 201)

    def test_trial_gate_does_not_block_entity_context_in_build_mode(self):
        user = make_user("free_bypass", "free_bypass@example.com")
        start_trial(user)
        consume_trial_contract(user)
        allowed, msg = can_create_contract(user)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")


# ---------------------------------------------------------------------------
# Webhook security
# ---------------------------------------------------------------------------

class WebhookSecurityTests(TestCase):
    """
    POST /api/billing/webhook/

    Confirm that the webhook endpoint rejects requests safely when the Stripe
    webhook secret is not configured, and rejects requests with an invalid
    signature when it is configured.
    """

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.url = "/api/billing/webhook/"

    def test_webhook_rejected_when_secret_not_configured(self):
        """
        When STRIPE_WEBHOOK_SECRET is empty the endpoint must return 503 and
        must not process any payload.
        """
        import json
        from unittest.mock import patch

        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"bonup_user_id": "1", "plan_slug": "business"}}},
        })

        with patch("django.conf.settings.STRIPE_WEBHOOK_SECRET", ""):
            r = self.client.post(
                self.url,
                data=payload,
                content_type="application/json",
            )

        self.assertEqual(r.status_code, 503)
        self.assertIn("error", r.json())

    def test_webhook_rejected_on_invalid_signature(self):
        """
        When STRIPE_WEBHOOK_SECRET is set but the Stripe-Signature header is
        missing or wrong, the endpoint must return 400.
        """
        import json
        from unittest.mock import patch

        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {}},
        })

        with patch("django.conf.settings.STRIPE_WEBHOOK_SECRET", "whsec_test_secret"):
            r = self.client.post(
                self.url,
                data=payload,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="bad_signature",
            )

        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())
