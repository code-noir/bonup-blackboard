# backend/api/tests/test_blackbod_entitlements.py

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.api.tests.helpers import make_contract, make_user
from backend.billing.gates import (
    BLACKBOD_TRIAL_DAYS,
    can_access_template,
    can_create_business_entity,
    can_create_contract,
    can_create_session,
    consume_trial_contract,
    get_effective_blackbod_tier,
    increment_contracts_used,
    max_businesses,
    is_trial_valid,
    start_trial,
)
from backend.billing.models import SubscriptionPlan, UserSubscription


def plan(slug):
    return SubscriptionPlan.objects.get(slug=slug)


def subscribe(user, slug, status="active", **kwargs):
    defaults = {
        "user": user,
        "plan": plan(slug),
        "status": status,
        "billing_period": kwargs.pop("billing_period", "monthly"),
        "current_period_start": kwargs.pop("current_period_start", timezone.now()),
    }
    defaults.update(kwargs)
    return UserSubscription.objects.create(**defaults)


class BlackbodEffectiveTierTests(TestCase):
    def test_basic_resolves_to_basic(self):
        user = make_user("bb_basic", "bb_basic@example.com")
        subscribe(user, "basic")
        self.assertEqual(get_effective_blackbod_tier(user), "basic")

    def test_professional_resolves_to_professional(self):
        user = make_user("bb_professional", "bb_professional@example.com")
        subscribe(user, "professional")
        self.assertEqual(get_effective_blackbod_tier(user), "professional")

    def test_advanced_resolves_to_advanced(self):
        user = make_user("bb_advanced", "bb_advanced@example.com")
        subscribe(user, "advanced")
        self.assertEqual(get_effective_blackbod_tier(user), "advanced")

    def test_valid_trial_resolves_to_professional_entitlements(self):
        user = make_user("bb_trial", "bb_trial@example.com")
        start_trial(user)
        sub = UserSubscription.objects.get(user=user)
        self.assertEqual(sub.plan.slug, "trial")
        self.assertEqual(sub.status, "trialing")
        self.assertTrue(is_trial_valid(sub))
        self.assertEqual(get_effective_blackbod_tier(user), "professional")

    def test_trial_duration_is_exactly_14_days(self):
        user = make_user("bb_trial_duration", "bb_trial_duration@example.com")
        start_trial(user)
        sub = UserSubscription.objects.get(user=user)
        self.assertEqual(sub.trial_end - sub.trial_start, timedelta(days=BLACKBOD_TRIAL_DAYS))

    def test_expired_trial_does_not_resolve_to_professional(self):
        user = make_user("bb_trial_expired", "bb_trial_expired@example.com")
        start = timezone.now() - timedelta(days=15)
        subscribe(
            user,
            "trial",
            status="trialing",
            current_period_start=start,
            current_period_end=start + timedelta(days=14),
            trial_start=start,
            trial_end=start + timedelta(days=14),
        )
        self.assertIsNone(get_effective_blackbod_tier(user))

    def test_valid_trial_uses_professional_backend_gate_entitlements(self):
        user = make_user("bb_trial_gates", "bb_trial_gates.com")
        start_trial(user)

        session_allowed, _ = can_create_session(user)
        business_allowed, _ = can_create_business_entity(user)

        self.assertTrue(session_allowed)
        self.assertEqual(max_businesses(user), 1)
        self.assertTrue(business_allowed)

    def test_expired_trial_does_not_pass_backend_trial_gates(self):
        user = make_user("bb_expired_trial_gates", "bb_expired_trial_gates.com")
        start = timezone.now() - timedelta(days=15)
        subscribe(
            user,
            "trial",
            status="trialing",
            current_period_start=start,
            current_period_end=start + timedelta(days=14),
            trial_start=start,
            trial_end=start + timedelta(days=14),
        )

        session_allowed, _ = can_create_session(user)
        business_allowed, _ = can_create_business_entity(user)

        self.assertFalse(session_allowed)
        self.assertEqual(max_businesses(user), 0)
        self.assertFalse(business_allowed)

    def test_trial_expiration_does_not_delete_application_data(self):
        user = make_user("bb_trial_data", "bb_trial_data@example.com")
        contract = make_contract(user, "counterparty@example.com")
        start = timezone.now() - timedelta(days=15)
        sub = subscribe(
            user,
            "trial",
            status="trialing",
            current_period_start=start,
            current_period_end=start + timedelta(days=14),
            trial_start=start,
            trial_end=start + timedelta(days=14),
        )
        self.assertIsNone(get_effective_blackbod_tier(user))
        self.assertTrue(type(contract).objects.filter(id=contract.id).exists())
        sub.refresh_from_db()
        self.assertEqual(sub.status, "trialing")

    def test_anchor_does_not_resolve_to_advanced(self):
        user = make_user("bb_anchor", "bb_anchor@example.com")
        subscribe(user, "anchor")
        self.assertIsNone(get_effective_blackbod_tier(user))

    def test_special_plans_do_not_resolve_to_paid_blackbod_tiers(self):
        for slug in ["per_contract", "sol_member"]:
            user = make_user(f"bb_{slug}", f"bb_{slug}@example.com")
            status = "per_contract" if slug == "per_contract" else "active"
            subscribe(user, slug, status=status)
            self.assertIsNone(get_effective_blackbod_tier(user))

        test_plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="_test_unlimited",
            defaults={
                "display_name": "Test Unlimited",
                "price_monthly": Decimal("0.00"),
                "max_active_contracts": None,
                "max_live_sessions_per_month": None,
                "has_lifecycle": True,
                "has_notifications": True,
                "has_negotiation_prep": True,
                "all_templates": True,
                "excluded_categories": [],
                "has_sol": True,
                "ai_tier": "full",
                "has_priority_support": True,
                "has_early_access": True,
            },
        )
        user = make_user("bb_test_unlimited", "bb_test_unlimited@example.com")
        UserSubscription.objects.create(
            user=user,
            plan=test_plan,
            status="active",
            billing_period="monthly",
            current_period_start=timezone.now(),
        )
        self.assertIsNone(get_effective_blackbod_tier(user))

    def test_backend_tier_resolution_is_authoritative_not_stored_display(self):
        user = make_user("bb_authoritative", "bb_authoritative@example.com")
        start = timezone.now()
        subscribe(
            user,
            "trial",
            status="trialing",
            current_period_start=start,
            current_period_end=start + timedelta(days=14),
            trial_start=start,
            trial_end=start + timedelta(days=14),
        )
        self.assertEqual(UserSubscription.objects.get(user=user).plan.slug, "trial")
        self.assertEqual(get_effective_blackbod_tier(user), "professional")

    def test_legacy_slugs_resolve_intentionally(self):
        user = make_user("bb_legacy_starter", "bb_legacy_starter@example.com")
        subscribe(user, "starter")
        self.assertEqual(get_effective_blackbod_tier(user), "basic")

        user = make_user("bb_legacy_business", "bb_legacy_business@example.com")
        subscribe(user, "business")
        self.assertEqual(get_effective_blackbod_tier(user), "advanced")

    def test_development_bypasses_remain_intentional(self):
        user = make_user("bb_bypass", "bb_bypass@example.com")
        allowed, message = can_create_contract(user)
        self.assertTrue(allowed)
        self.assertEqual(message, "")
        self.assertTrue(can_access_template(user, object())[0])

        sub = subscribe(user, "basic")
        increment_contracts_used(user)
        consume_trial_contract(user)
        sub.refresh_from_db()
        self.assertEqual(sub.contracts_used_this_period, 0)
