# backend/api/tests/test_blackbod_tool_bridge.py

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.billing.blackbod import (
    BLACKBOD_TOOL_SLUG,
    get_legacy_blackbod_access,
    has_blackbod_access,
    sync_blackbod_tool_entitlement,
)
from backend.billing.models import (
    AIEntitlement,
    CommercialEntitlementStatus,
    CustomerPackage,
    Product,
    StorageEntitlement,
    SubscriptionPlan,
    ToolEntitlement,
    ToolEntitlementOrigin,
    UserSubscription,
)

from .helpers import authed_client, make_user


def blackbod_product():
    return Product.objects.get(slug=BLACKBOD_TOOL_SLUG)


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


def create_test_unlimited_plan():
    plan_obj, _ = SubscriptionPlan.objects.get_or_create(
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
    return plan_obj


def create_tool_entitlement(
    user,
    *,
    status=CommercialEntitlementStatus.ACTIVE,
    origin=ToolEntitlementOrigin.NATIVE,
    starts_at=None,
    ends_at=None,
):
    return ToolEntitlement.objects.create(
        user=user,
        product=blackbod_product(),
        status=status,
        origin=origin,
        starts_at=starts_at or timezone.now(),
        ends_at=ends_at,
    )


class BlackbodBridgeAccessTests(TestCase):
    def test_active_legacy_basic_grants_blackbod_access(self):
        user = make_user("bridge_basic", "bridge_basic@example.com")
        subscribe(user, "basic")

        self.assertTrue(has_blackbod_access(user))

    def test_active_legacy_professional_grants_blackbod_access(self):
        user = make_user("bridge_professional", "bridge_professional@example.com")
        subscribe(user, "professional")

        self.assertTrue(has_blackbod_access(user))

    def test_active_legacy_advanced_grants_blackbod_access(self):
        user = make_user("bridge_advanced", "bridge_advanced@example.com")
        subscribe(user, "advanced")

        self.assertTrue(has_blackbod_access(user))

    def test_paid_legacy_tiers_sync_to_same_blackbod_tool_identity(self):
        product_ids = set()
        for slug in ["basic", "professional", "advanced"]:
            user = make_user(f"bridge_same_{slug}", f"bridge_same_{slug}@example.com")
            subscribe(user, slug)

            entitlement = sync_blackbod_tool_entitlement(user)

            self.assertEqual(entitlement.product.slug, BLACKBOD_TOOL_SLUG)
            self.assertEqual(entitlement.origin, ToolEntitlementOrigin.LEGACY_SUBSCRIPTION)
            product_ids.add(entitlement.product_id)
        self.assertEqual(product_ids, {blackbod_product().id})

    def test_no_subscription_status_does_not_grant_access(self):
        user = make_user("bridge_no_subscription", "bridge_no_subscription@example.com")
        subscribe(user, "advanced", status="no_subscription")

        self.assertFalse(has_blackbod_access(user))

    def test_cancelled_does_not_grant_access_under_existing_semantics(self):
        user = make_user("bridge_cancelled", "bridge_cancelled@example.com")
        subscribe(user, "basic", status="cancelled", current_period_end=timezone.now() + timedelta(days=20))

        self.assertFalse(has_blackbod_access(user))

    def test_past_due_does_not_grant_access_under_existing_semantics(self):
        user = make_user("bridge_past_due", "bridge_past_due@example.com")
        subscribe(user, "professional", status="past_due", current_period_end=timezone.now() + timedelta(days=20))

        self.assertFalse(has_blackbod_access(user))

    def test_per_contract_does_not_grant_general_blackbod_access(self):
        user = make_user("bridge_per_contract", "bridge_per_contract@example.com")
        subscribe(user, "per_contract", status="per_contract", billing_period="per_contract")

        self.assertFalse(has_blackbod_access(user))

    def test_valid_trial_grants_temporary_access(self):
        user = make_user("bridge_trial", "bridge_trial@example.com")
        start = timezone.now() - timedelta(days=1)
        end = start + timedelta(days=14)
        sub = subscribe(
            user,
            "trial",
            status="trialing",
            current_period_start=start,
            current_period_end=end,
            trial_start=start,
            trial_end=end,
        )

        legacy_access = get_legacy_blackbod_access(sub)

        self.assertTrue(has_blackbod_access(user))
        self.assertTrue(legacy_access.has_access)
        self.assertEqual(legacy_access.ends_at, end)

    def test_expired_trial_does_not_grant_current_access(self):
        user = make_user("bridge_expired_trial", "bridge_expired_trial@example.com")
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

        self.assertFalse(has_blackbod_access(user))

    def test_trial_sync_sets_tool_entitlement_end_to_trial_end(self):
        user = make_user("bridge_trial_end", "bridge_trial_end@example.com")
        start = timezone.now() - timedelta(days=1)
        end = start + timedelta(days=14)
        subscribe(
            user,
            "trial",
            status="trialing",
            current_period_start=start,
            current_period_end=end,
            trial_start=start,
            trial_end=end,
        )

        entitlement = sync_blackbod_tool_entitlement(user)

        self.assertEqual(entitlement.ends_at, end)
        self.assertEqual(entitlement.origin, ToolEntitlementOrigin.LEGACY_SUBSCRIPTION)

    def test_special_non_blackbod_plans_do_not_grant_access(self):
        cases = [
            ("per_contract", "per_contract", "per_contract"),
            ("sol_member", "active", "monthly"),
        ]
        for slug, status, billing_period in cases:
            user = make_user(f"bridge_special_{slug}", f"bridge_special_{slug}@example.com")
            subscribe(user, slug, status=status, billing_period=billing_period)
            self.assertFalse(has_blackbod_access(user))

        test_plan = create_test_unlimited_plan()
        user = make_user("bridge_special_test", "bridge_special_test@example.com")
        UserSubscription.objects.create(
            user=user,
            plan=test_plan,
            status="active",
            billing_period="monthly",
            current_period_start=timezone.now(),
        )
        self.assertFalse(has_blackbod_access(user))

    def test_user_me_exposes_read_only_has_blackbod_access(self):
        user = make_user("bridge_me", "bridge_me@example.com")
        subscribe(user, "basic")

        response = authed_client(user).get("/api/users/me/")

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["has_blackbod_access"], True)


class BlackbodEntitlementPriorityTests(TestCase):
    def test_current_tool_entitlement_grants_access_without_legacy_subscription(self):
        user = make_user("bridge_tool_current", "bridge_tool_current@example.com")
        create_tool_entitlement(user)

        self.assertTrue(has_blackbod_access(user))

    def test_expired_tool_entitlement_does_not_grant_access_without_legacy_fallback(self):
        user = make_user("bridge_tool_expired", "bridge_tool_expired@example.com")
        now = timezone.now()
        create_tool_entitlement(user, starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1))

        self.assertFalse(has_blackbod_access(user, now=now))

    def test_inactive_tool_entitlement_does_not_grant_access_without_legacy_fallback(self):
        user = make_user("bridge_tool_inactive", "bridge_tool_inactive@example.com")
        create_tool_entitlement(user, status=CommercialEntitlementStatus.INACTIVE)

        self.assertFalse(has_blackbod_access(user))

    def test_bridge_fallback_evaluates_legacy_when_no_current_tool_entitlement_exists(self):
        user = make_user("bridge_tool_fallback", "bridge_tool_fallback@example.com")
        now = timezone.now()
        create_tool_entitlement(user, starts_at=now - timedelta(days=3), ends_at=now - timedelta(days=2))
        subscribe(user, "professional")

        self.assertTrue(has_blackbod_access(user, now=now))


class BlackbodSyncTests(TestCase):
    def test_sync_is_idempotent(self):
        user = make_user("bridge_sync_idem", "bridge_sync_idem@example.com")
        subscribe(user, "basic")

        first = sync_blackbod_tool_entitlement(user)
        second = sync_blackbod_tool_entitlement(user)

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            ToolEntitlement.objects.filter(
                user=user,
                product=blackbod_product(),
                status=CommercialEntitlementStatus.ACTIVE,
            ).count(),
            1,
        )

    def test_repeated_sync_does_not_create_duplicate_active_tool_entitlements(self):
        user = make_user("bridge_sync_dupes", "bridge_sync_dupes@example.com")
        subscribe(user, "advanced")
        create_tool_entitlement(user)

        sync_blackbod_tool_entitlement(user)
        sync_blackbod_tool_entitlement(user)

        self.assertEqual(
            ToolEntitlement.objects.filter(
                user=user,
                product=blackbod_product(),
                status=CommercialEntitlementStatus.ACTIVE,
            ).count(),
            1,
        )

    def test_native_entitlement_is_not_expired_by_legacy_no_subscription_sync(self):
        user = make_user("bridge_native_no_sub", "bridge_native_no_sub@example.com")
        native = create_tool_entitlement(user)
        subscribe(user, "advanced", status="no_subscription")

        result = sync_blackbod_tool_entitlement(user)
        native.refresh_from_db()

        self.assertIsNone(result)
        self.assertEqual(native.status, CommercialEntitlementStatus.ACTIVE)
        self.assertEqual(native.origin, ToolEntitlementOrigin.NATIVE)
        self.assertIsNone(native.ends_at)
        self.assertTrue(has_blackbod_access(user))

    def test_native_entitlement_is_not_expired_by_cancelled_legacy_sync(self):
        user = make_user("bridge_native_cancelled", "bridge_native_cancelled@example.com")
        native = create_tool_entitlement(user)
        subscribe(user, "basic", status="cancelled")

        result = sync_blackbod_tool_entitlement(user)
        native.refresh_from_db()

        self.assertIsNone(result)
        self.assertEqual(native.status, CommercialEntitlementStatus.ACTIVE)
        self.assertEqual(native.origin, ToolEntitlementOrigin.NATIVE)

    def test_native_entitlement_is_not_expired_by_past_due_legacy_sync(self):
        user = make_user("bridge_native_past_due", "bridge_native_past_due@example.com")
        native = create_tool_entitlement(user)
        subscribe(user, "professional", status="past_due")

        result = sync_blackbod_tool_entitlement(user)
        native.refresh_from_db()

        self.assertIsNone(result)
        self.assertEqual(native.status, CommercialEntitlementStatus.ACTIVE)
        self.assertEqual(native.origin, ToolEntitlementOrigin.NATIVE)

    def test_paid_legacy_plans_all_synchronize_to_blackbod_product(self):
        for slug in ["basic", "professional", "advanced"]:
            user = make_user(f"bridge_sync_{slug}", f"bridge_sync_{slug}@example.com")
            subscribe(user, slug)

            entitlement = sync_blackbod_tool_entitlement(user)

            self.assertEqual(entitlement.product, blackbod_product())
            self.assertEqual(entitlement.origin, ToolEntitlementOrigin.LEGACY_SUBSCRIPTION)
            self.assertEqual(entitlement.product.tool_metadata.tool_slug, BLACKBOD_TOOL_SLUG)

    def test_expired_legacy_access_ends_current_entitlement(self):
        user = make_user("bridge_sync_expired", "bridge_sync_expired@example.com")
        entitlement = create_tool_entitlement(user, origin=ToolEntitlementOrigin.LEGACY_SUBSCRIPTION)
        subscribe(user, "trial", status="trialing", current_period_start=timezone.now() - timedelta(days=20))

        result = sync_blackbod_tool_entitlement(user)
        entitlement.refresh_from_db()

        self.assertIsNone(result)
        self.assertEqual(entitlement.status, CommercialEntitlementStatus.EXPIRED)
        self.assertIsNotNone(entitlement.ends_at)

    def test_no_subscription_does_not_create_entitlement(self):
        user = make_user("bridge_sync_none", "bridge_sync_none@example.com")
        subscribe(user, "basic", status="no_subscription")

        result = sync_blackbod_tool_entitlement(user)

        self.assertIsNone(result)
        self.assertFalse(ToolEntitlement.objects.filter(user=user, product=blackbod_product()).exists())

    def test_native_entitlement_plus_qualifying_legacy_subscription_does_not_create_duplicate_access(self):
        user = make_user("bridge_native_plus_legacy", "bridge_native_plus_legacy@example.com")
        native = create_tool_entitlement(user)
        subscribe(user, "advanced")

        result = sync_blackbod_tool_entitlement(user)
        native.refresh_from_db()

        self.assertEqual(result.id, native.id)
        self.assertEqual(native.status, CommercialEntitlementStatus.ACTIVE)
        self.assertEqual(native.origin, ToolEntitlementOrigin.NATIVE)
        self.assertEqual(
            ToolEntitlement.objects.filter(
                user=user,
                product=blackbod_product(),
                status=CommercialEntitlementStatus.ACTIVE,
            ).count(),
            1,
        )
        self.assertFalse(
            ToolEntitlement.objects.filter(
                user=user,
                product=blackbod_product(),
                origin=ToolEntitlementOrigin.LEGACY_SUBSCRIPTION,
            ).exists()
        )

    def test_native_entitlement_remains_preferred_over_legacy_fallback(self):
        user = make_user("bridge_native_preferred", "bridge_native_preferred@example.com")
        native = create_tool_entitlement(user)
        subscribe(user, "basic", status="no_subscription")

        self.assertTrue(has_blackbod_access(user))
        self.assertEqual(native.origin, ToolEntitlementOrigin.NATIVE)

    def test_paid_sync_uses_known_billing_period_dates(self):
        user = make_user("bridge_sync_period", "bridge_sync_period@example.com")
        start = timezone.now() - timedelta(days=1)
        end = timezone.now() + timedelta(days=29)
        subscribe(user, "professional", current_period_start=start, current_period_end=end)

        entitlement = sync_blackbod_tool_entitlement(user)

        self.assertEqual(entitlement.starts_at, start)
        self.assertEqual(entitlement.ends_at, end)


class BlackbodSeparationTests(TestCase):
    def test_blackbod_tool_access_does_not_create_storage_entitlement(self):
        user = make_user("bridge_storage_sep", "bridge_storage_sep@example.com")
        subscribe(user, "basic")

        sync_blackbod_tool_entitlement(user)

        self.assertFalse(StorageEntitlement.objects.filter(user=user).exists())

    def test_blackbod_tool_access_does_not_create_ai_entitlement(self):
        user = make_user("bridge_ai_sep", "bridge_ai_sep@example.com")
        subscribe(user, "advanced")

        sync_blackbod_tool_entitlement(user)

        self.assertFalse(AIEntitlement.objects.filter(user=user).exists())

    def test_native_sync_protection_does_not_create_storage_or_ai_entitlements(self):
        user = make_user("bridge_native_sep", "bridge_native_sep@example.com")
        create_tool_entitlement(user)
        subscribe(user, "professional", status="cancelled")

        sync_blackbod_tool_entitlement(user)

        self.assertFalse(StorageEntitlement.objects.filter(user=user).exists())
        self.assertFalse(AIEntitlement.objects.filter(user=user).exists())

    def test_signup_creates_no_tool_entitlement_or_customer_package(self):
        user = make_user("bridge_signup", "bridge_signup@example.com")

        self.assertFalse(ToolEntitlement.objects.filter(user=user).exists())
        self.assertFalse(CustomerPackage.objects.filter(user=user).exists())
        self.assertFalse(UserSubscription.objects.filter(user=user).exists())
