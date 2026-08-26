# backend/api/tests/test_commercial_packages.py

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from backend.billing.commercial import (
    activate_package,
    create_customer_package,
    create_ai_entitlement,
    create_storage_entitlement,
    create_tool_entitlement,
    get_storage_entitlement,
    has_ai_access,
    has_tool,
    update_storage_entitlement,
    validate_ai_entitlement,
    validate_package,
    validate_storage_entitlement,
    validate_tool_entitlement,
)
from backend.billing.gates import can_create_contract
from backend.billing.models import (
    AIEntitlement,
    AIProductMetadata,
    CommercialEntitlementStatus,
    CustomerPackage,
    PackageItem,
    Product,
    StorageEntitlement,
    StorageProductMetadata,
    SubscriptionPlan,
    ToolEntitlement,
    ToolProductMetadata,
    UserSubscription,
)

from .helpers import authed_client, make_user


def blackbod_product():
    return Product.objects.get(slug="blackbod")


def create_tool_product(slug="tool-basic", ai_capable=False, active=True, with_metadata=True):
    product = Product.objects.create(
        slug=slug,
        name="Tool",
        product_type=Product.ProductType.TOOL,
        active=active,
    )
    if with_metadata:
        ToolProductMetadata.objects.create(product=product, tool_slug=slug, ai_capable=ai_capable)
    return product


def create_storage_product(slug="storage-small", capacity_bytes=1024, active=True, with_metadata=True):
    product = Product.objects.create(
        slug=slug,
        name="Storage",
        product_type=Product.ProductType.STORAGE,
        active=active,
        monthly_price=Decimal("5.00"),
        annual_price=Decimal("50.00"),
    )
    if with_metadata:
        StorageProductMetadata.objects.create(product=product, capacity_bytes=capacity_bytes)
    return product


def create_ai_product(slug="ai-assist", active=True, with_metadata=True):
    product = Product.objects.create(
        slug=slug,
        name="AI Assist",
        product_type=Product.ProductType.AI,
        active=active,
        monthly_price=None,
        annual_price=None,
    )
    if with_metadata:
        AIProductMetadata.objects.create(product=product, service_level="")
    return product


def inactive_status():
    return CommercialEntitlementStatus.INACTIVE


def expired_status():
    return CommercialEntitlementStatus.EXPIRED


class ProductFoundationTests(TestCase):

    def test_product_slug_is_unique(self):
        Product.objects.create(slug="duplicate", name="One", product_type=Product.ProductType.TOOL)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(slug="duplicate", name="Two", product_type=Product.ProductType.TOOL)

    def test_product_types_include_tool_storage_and_ai(self):
        values = {choice[0] for choice in Product.ProductType.choices}
        self.assertIn(Product.ProductType.TOOL, values)
        self.assertIn(Product.ProductType.STORAGE, values)
        self.assertIn(Product.ProductType.AI, values)


class PackageFoundationTests(TestCase):

    def test_user_can_have_package_containing_blackbod(self):
        user = make_user("pkg_blackbod", "pkg_blackbod@example.com")
        package = CustomerPackage.objects.create(user=user, billing_interval=CustomerPackage.BillingInterval.MONTHLY)
        PackageItem.objects.create(package=package, product=blackbod_product())

        self.assertTrue(validate_package(package))

    def test_storage_only_active_package_accepted(self):
        user = make_user("pkg_storage", "pkg_storage@example.com")
        package = CustomerPackage.objects.create(user=user, billing_interval=CustomerPackage.BillingInterval.MONTHLY)
        PackageItem.objects.create(package=package, product=create_storage_product())

        self.assertEqual(activate_package(package).status, CustomerPackage.Status.ACTIVE)

    def test_create_customer_package_service_accepts_storage_only_active_package(self):
        user = make_user("pkg_service_storage", "pkg_service_storage@example.com")

        package = create_customer_package(
            user=user,
            status=CustomerPackage.Status.ACTIVE,
            products=[create_storage_product("service-storage")],
        )

        self.assertEqual(package.status, CustomerPackage.Status.ACTIVE)
        self.assertEqual(list(package.items.values_list("product__product_type", flat=True)), [Product.ProductType.STORAGE])

    def test_create_customer_package_service_rejects_inactive_product_activation(self):
        user = make_user("pkg_service_inactive", "pkg_service_inactive@example.com")

        with self.assertRaises(ValidationError):
            create_customer_package(
                user=user,
                status=CustomerPackage.Status.ACTIVE,
                products=[create_tool_product("service-inactive-tool", active=False)],
            )

    def test_create_customer_package_service_preserves_one_active_package_per_user(self):
        user = make_user("pkg_service_active", "pkg_service_active@example.com")
        create_customer_package(user=user, status=CustomerPackage.Status.ACTIVE, products=[blackbod_product()])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_customer_package(user=user, status=CustomerPackage.Status.ACTIVE, products=[create_storage_product("service-second-storage")])

    def test_package_cannot_contain_duplicate_product(self):
        user = make_user("pkg_duplicate", "pkg_duplicate@example.com")
        package = CustomerPackage.objects.create(user=user)
        product = blackbod_product()
        PackageItem.objects.create(package=package, product=product)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PackageItem.objects.create(package=package, product=product)

    def test_monthly_interval_works(self):
        user = make_user("pkg_monthly", "pkg_monthly@example.com")
        package = CustomerPackage.objects.create(user=user, billing_interval=CustomerPackage.BillingInterval.MONTHLY)

        self.assertEqual(package.billing_interval, CustomerPackage.BillingInterval.MONTHLY)

    def test_annual_interval_works(self):
        user = make_user("pkg_annual", "pkg_annual@example.com")
        package = CustomerPackage.objects.create(user=user, billing_interval=CustomerPackage.BillingInterval.ANNUAL)

        self.assertEqual(package.billing_interval, CustomerPackage.BillingInterval.ANNUAL)

    def test_second_active_package_for_same_user_rejected(self):
        user = make_user("pkg_active", "pkg_active@example.com")
        CustomerPackage.objects.create(user=user, status=CustomerPackage.Status.ACTIVE)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerPackage.objects.create(user=user, status=CustomerPackage.Status.ACTIVE)

    def test_inactive_product_rejected_when_activating_package(self):
        user = make_user("pkg_inactive", "pkg_inactive@example.com")
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=create_tool_product("inactive-tool", active=False))

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_package_tool_without_required_metadata_rejected(self):
        user = make_user("pkg_tool_meta", "pkg_tool_meta@example.com")
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=create_tool_product("tool-no-meta", with_metadata=False))

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_package_storage_without_required_metadata_rejected(self):
        user = make_user("pkg_storage_meta", "pkg_storage_meta@example.com")
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=create_storage_product("storage-no-meta", with_metadata=False))

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_package_ai_without_required_metadata_rejected(self):
        user = make_user("pkg_ai_meta", "pkg_ai_meta@example.com")
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=create_ai_product("ai-no-meta", with_metadata=False))

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_package_ai_without_ai_capable_tool_rejected(self):
        user = make_user("pkg_ai_no_tool", "pkg_ai_no_tool@example.com")
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=create_ai_product())

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_package_ai_with_blackbod_accepted(self):
        user = make_user("pkg_ai_blackbod", "pkg_ai_blackbod@example.com")
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=blackbod_product())
        PackageItem.objects.create(package=package, product=create_ai_product())

        self.assertEqual(activate_package(package).status, CustomerPackage.Status.ACTIVE)


class BlackbodCommercialProductTests(TestCase):

    def test_blackbod_is_represented_as_one_tool(self):
        product = blackbod_product()

        self.assertEqual(product.name, "Blackbòd")
        self.assertEqual(product.product_type, Product.ProductType.TOOL)
        self.assertTrue(product.active)

    def test_no_basic_professional_advanced_distinction_exists_in_product_model(self):
        self.assertFalse(Product.objects.filter(slug__in=["basic", "professional", "advanced"]).exists())

    def test_blackbod_tool_metadata_is_ai_capable(self):
        metadata = blackbod_product().tool_metadata

        self.assertEqual(metadata.tool_slug, "blackbod")
        self.assertTrue(metadata.ai_capable)


class ToolEntitlementTimeTests(TestCase):

    def test_future_tool_start_returns_false(self):
        user = make_user("tool_future", "tool_future@example.com")
        now = timezone.now()
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), starts_at=now + timedelta(days=1))

        self.assertFalse(has_tool(user, "blackbod", now=now))

    def test_expired_tool_returns_false(self):
        user = make_user("tool_expired", "tool_expired@example.com")
        now = timezone.now()
        ToolEntitlement.objects.create(
            user=user,
            product=blackbod_product(),
            starts_at=now - timedelta(days=2),
            ends_at=now - timedelta(days=1),
        )

        self.assertFalse(has_tool(user, "blackbod", now=now))

    def test_tool_null_ends_at_is_current_when_active(self):
        user = make_user("tool_null_end", "tool_null_end@example.com")
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), ends_at=None)

        self.assertTrue(has_tool(user, "blackbod"))

    def test_inactive_tool_returns_false(self):
        user = make_user("tool_inactive", "tool_inactive@example.com")
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), status=inactive_status())

        self.assertFalse(has_tool(user, "blackbod"))

    def test_multiple_historical_tool_entitlements_do_not_block_current_lookup(self):
        user = make_user("tool_history", "tool_history@example.com")
        now = timezone.now()
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), starts_at=now - timedelta(days=5), ends_at=now - timedelta(days=4))
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), status=expired_status(), starts_at=now - timedelta(days=3), ends_at=now - timedelta(days=2))
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), starts_at=now - timedelta(minutes=1), ends_at=None)

        self.assertTrue(has_tool(user, "blackbod", now=now))


class StorageCommercialTests(TestCase):

    def test_independent_storage_entitlement_works(self):
        user = make_user("storage_ent", "storage_ent@example.com")
        entitlement = create_storage_entitlement(user=user, capacity_bytes=2048, usage_bytes=128)

        self.assertEqual(get_storage_entitlement(user), entitlement)

    def test_future_storage_start_returns_none(self):
        user = make_user("storage_future", "storage_future@example.com")
        now = timezone.now()
        StorageEntitlement.objects.create(user=user, capacity_bytes=100, starts_at=now + timedelta(days=1))

        self.assertIsNone(get_storage_entitlement(user, now=now))

    def test_expired_storage_returns_none(self):
        user = make_user("storage_expired", "storage_expired@example.com")
        now = timezone.now()
        StorageEntitlement.objects.create(user=user, capacity_bytes=100, starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1))

        self.assertIsNone(get_storage_entitlement(user, now=now))

    def test_storage_null_ends_at_is_current_when_active(self):
        user = make_user("storage_null_end", "storage_null_end@example.com")
        entitlement = create_storage_entitlement(user=user, capacity_bytes=100, ends_at=None)

        self.assertEqual(get_storage_entitlement(user), entitlement)

    def test_inactive_storage_ignored(self):
        user = make_user("storage_inactive", "storage_inactive@example.com")
        StorageEntitlement.objects.create(user=user, capacity_bytes=100, status=inactive_status())

        self.assertIsNone(get_storage_entitlement(user))

    def test_one_active_storage_entitlement_allowed(self):
        user = make_user("storage_one", "storage_one@example.com")
        entitlement = create_storage_entitlement(user=user, capacity_bytes=100)

        self.assertEqual(get_storage_entitlement(user), entitlement)

    def test_second_active_storage_entitlement_rejected_by_service(self):
        user = make_user("storage_second_service", "storage_second_service@example.com")
        create_storage_entitlement(user=user, capacity_bytes=100)

        with self.assertRaises(ValidationError):
            create_storage_entitlement(user=user, capacity_bytes=200)

    def test_second_active_storage_entitlement_rejected_by_database(self):
        user = make_user("storage_second_db", "storage_second_db@example.com")
        StorageEntitlement.objects.create(user=user, capacity_bytes=100)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StorageEntitlement.objects.create(user=user, capacity_bytes=200)

    def test_historical_inactive_storage_does_not_prevent_new_active(self):
        user = make_user("storage_old_inactive", "storage_old_inactive@example.com")
        StorageEntitlement.objects.create(user=user, capacity_bytes=100, status=inactive_status())
        active = create_storage_entitlement(user=user, capacity_bytes=200)

        self.assertEqual(get_storage_entitlement(user), active)

    def test_historical_expired_storage_does_not_prevent_new_active(self):
        user = make_user("storage_old_expired", "storage_old_expired@example.com")
        StorageEntitlement.objects.create(user=user, capacity_bytes=100, status=expired_status())
        active = create_storage_entitlement(user=user, capacity_bytes=200)

        self.assertEqual(get_storage_entitlement(user), active)

    def test_get_storage_entitlement_is_unambiguous(self):
        user = make_user("storage_unambiguous", "storage_unambiguous@example.com")
        StorageEntitlement.objects.create(user=user, capacity_bytes=100, status=inactive_status())
        active = create_storage_entitlement(user=user, capacity_bytes=200)

        self.assertEqual(get_storage_entitlement(user), active)

    def test_usage_greater_than_capacity_rejected(self):
        user = make_user("storage_over", "storage_over@example.com")
        with self.assertRaises(ValidationError):
            create_storage_entitlement(user=user, capacity_bytes=100, usage_bytes=101)

    def test_negative_capacity_rejected(self):
        user = make_user("storage_capacity", "storage_capacity@example.com")
        with self.assertRaises(ValidationError):
            create_storage_entitlement(user=user, capacity_bytes=-1, usage_bytes=0)

    def test_negative_usage_rejected(self):
        user = make_user("storage_usage", "storage_usage@example.com")
        with self.assertRaises(ValidationError):
            create_storage_entitlement(user=user, capacity_bytes=100, usage_bytes=-1)

    def test_usage_helper_does_not_silently_exceed_capacity(self):
        user = make_user("storage_helper", "storage_helper@example.com")
        entitlement = create_storage_entitlement(user=user, capacity_bytes=100, usage_bytes=50)

        with self.assertRaises(ValidationError):
            entitlement.add_usage(51)

    def test_update_storage_entitlement_validates_capacity(self):
        user = make_user("storage_update", "storage_update@example.com")
        entitlement = create_storage_entitlement(user=user, capacity_bytes=100, usage_bytes=50)

        with self.assertRaises(ValidationError):
            update_storage_entitlement(entitlement, capacity_bytes=40)


class AICommercialTests(TestCase):

    def test_future_ai_start_returns_false(self):
        user = make_user("ai_future", "ai_future@example.com")
        now = timezone.now()
        create_tool_entitlement(user=user, product=blackbod_product())
        AIEntitlement.objects.create(user=user, product=create_ai_product(), starts_at=now + timedelta(days=1))

        self.assertFalse(has_ai_access(user, now=now))

    def test_expired_ai_returns_false(self):
        user = make_user("ai_expired", "ai_expired@example.com")
        now = timezone.now()
        create_tool_entitlement(user=user, product=blackbod_product())
        AIEntitlement.objects.create(user=user, product=create_ai_product(), starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1))

        self.assertFalse(has_ai_access(user, now=now))

    def test_ai_null_ends_at_is_current_when_valid(self):
        user = make_user("ai_null_end", "ai_null_end@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        create_ai_entitlement(user=user, product=create_ai_product(), ends_at=None)

        self.assertTrue(has_ai_access(user))

    def test_ai_with_no_tool_rejected(self):
        user = make_user("ai_no_tool", "ai_no_tool@example.com")

        with self.assertRaises(ValidationError):
            create_ai_entitlement(user=user, product=create_ai_product())

    def test_ai_with_expired_tool_rejected(self):
        user = make_user("ai_expired_tool", "ai_expired_tool@example.com")
        now = timezone.now()
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1))

        with self.assertRaises(ValidationError):
            create_ai_entitlement(user=user, product=create_ai_product())

    def test_ai_with_future_tool_rejected(self):
        user = make_user("ai_future_tool", "ai_future_tool@example.com")
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), starts_at=timezone.now() + timedelta(days=1))

        with self.assertRaises(ValidationError):
            create_ai_entitlement(user=user, product=create_ai_product())

    def test_ai_with_inactive_tool_rejected(self):
        user = make_user("ai_inactive_tool", "ai_inactive_tool@example.com")
        ToolEntitlement.objects.create(user=user, product=blackbod_product(), status=inactive_status())

        with self.assertRaises(ValidationError):
            create_ai_entitlement(user=user, product=create_ai_product())

    def test_ai_with_non_ai_capable_tool_rejected(self):
        user = make_user("ai_plain_tool", "ai_plain_tool@example.com")
        create_tool_entitlement(user=user, product=create_tool_product("plain-tool", ai_capable=False))

        with self.assertRaises(ValidationError):
            create_ai_entitlement(user=user, product=create_ai_product())

    def test_ai_with_current_blackbod_tool_entitlement_accepted(self):
        user = make_user("ai_blackbod", "ai_blackbod@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())

        entitlement = create_ai_entitlement(user=user, product=create_ai_product())

        self.assertTrue(validate_ai_entitlement(entitlement))
        self.assertTrue(has_ai_access(user))

    def test_storage_and_ai_without_tool_rejected(self):
        user = make_user("ai_storage_only", "ai_storage_only@example.com")
        create_storage_entitlement(user=user, capacity_bytes=100)

        with self.assertRaises(ValidationError):
            create_ai_entitlement(user=user, product=create_ai_product())

    def test_ai_entitlement_does_not_depend_on_legacy_subscription_plan_tier(self):
        user = make_user("ai_no_legacy", "ai_no_legacy@example.com")
        self.assertFalse(UserSubscription.objects.filter(user=user).exists())
        create_tool_entitlement(user=user, product=blackbod_product())
        create_ai_entitlement(user=user, product=create_ai_product())

        self.assertTrue(has_ai_access(user))


class MetadataValidationTests(TestCase):

    def test_tool_without_tool_metadata_rejected_for_activation(self):
        user = make_user("meta_tool", "meta_tool@example.com")
        with self.assertRaises(ValidationError):
            create_tool_entitlement(user=user, product=create_tool_product("meta-tool", with_metadata=False))

    def test_storage_without_storage_metadata_rejected_for_package_activation(self):
        user = make_user("meta_storage", "meta_storage@example.com")
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=create_storage_product("meta-storage", with_metadata=False))

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_ai_without_ai_metadata_rejected_for_activation(self):
        user = make_user("meta_ai", "meta_ai@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        with self.assertRaises(ValidationError):
            create_ai_entitlement(user=user, product=create_ai_product("meta-ai", with_metadata=False))

    def test_storage_product_with_only_tool_metadata_rejected(self):
        user = make_user("meta_mismatch_storage", "meta_mismatch_storage@example.com")
        product = Product.objects.create(slug="storage-with-tool-meta", name="Bad Storage", product_type=Product.ProductType.STORAGE)
        ToolProductMetadata.objects.create(product=product, tool_slug="storage-with-tool-meta", ai_capable=True)
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=product)

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_ai_product_with_only_tool_metadata_rejected(self):
        user = make_user("meta_mismatch_ai", "meta_mismatch_ai@example.com")
        product = Product.objects.create(slug="ai-with-tool-meta", name="Bad AI", product_type=Product.ProductType.AI)
        ToolProductMetadata.objects.create(product=product, tool_slug="ai-with-tool-meta", ai_capable=True)
        package = CustomerPackage.objects.create(user=user)
        PackageItem.objects.create(package=package, product=blackbod_product())
        PackageItem.objects.create(package=package, product=product)

        with self.assertRaises(ValidationError):
            activate_package(package)

    def test_tool_entitlement_referencing_non_tool_product_rejected(self):
        user = make_user("meta_tool_ent", "meta_tool_ent@example.com")
        entitlement = ToolEntitlement(user=user, product=create_storage_product("storage-as-tool"))

        with self.assertRaises(ValidationError):
            validate_tool_entitlement(entitlement)

    def test_ai_entitlement_referencing_non_ai_product_rejected(self):
        user = make_user("meta_ai_ent", "meta_ai_ent@example.com")
        create_tool_entitlement(user=user, product=blackbod_product())
        entitlement = AIEntitlement(user=user, product=blackbod_product())

        with self.assertRaises(ValidationError):
            validate_ai_entitlement(entitlement)


class TemporalIntervalValidationTests(TestCase):

    def test_tool_ends_at_equal_starts_at_rejected(self):
        user = make_user("time_tool_equal", "time_tool_equal@example.com")
        now = timezone.now()
        entitlement = ToolEntitlement(user=user, product=blackbod_product(), starts_at=now, ends_at=now)

        with self.assertRaises(ValidationError):
            validate_tool_entitlement(entitlement)

    def test_tool_ends_at_before_starts_at_rejected(self):
        user = make_user("time_tool_before", "time_tool_before@example.com")
        now = timezone.now()
        entitlement = ToolEntitlement(user=user, product=blackbod_product(), starts_at=now, ends_at=now - timedelta(seconds=1))

        with self.assertRaises(ValidationError):
            validate_tool_entitlement(entitlement)

    def test_storage_ends_at_equal_starts_at_rejected(self):
        user = make_user("time_storage_equal", "time_storage_equal@example.com")
        now = timezone.now()
        entitlement = StorageEntitlement(user=user, capacity_bytes=100, starts_at=now, ends_at=now)

        with self.assertRaises(ValidationError):
            validate_storage_entitlement(entitlement)

    def test_storage_ends_at_before_starts_at_rejected(self):
        user = make_user("time_storage_before", "time_storage_before@example.com")
        now = timezone.now()
        entitlement = StorageEntitlement(user=user, capacity_bytes=100, starts_at=now, ends_at=now - timedelta(seconds=1))

        with self.assertRaises(ValidationError):
            validate_storage_entitlement(entitlement)

    def test_ai_ends_at_equal_starts_at_rejected(self):
        user = make_user("time_ai_equal", "time_ai_equal@example.com")
        now = timezone.now()
        create_tool_entitlement(user=user, product=blackbod_product())
        entitlement = AIEntitlement(user=user, product=create_ai_product(), starts_at=now, ends_at=now)

        with self.assertRaises(ValidationError):
            validate_ai_entitlement(entitlement)

    def test_ai_ends_at_before_starts_at_rejected(self):
        user = make_user("time_ai_before", "time_ai_before@example.com")
        now = timezone.now()
        create_tool_entitlement(user=user, product=blackbod_product())
        entitlement = AIEntitlement(user=user, product=create_ai_product(), starts_at=now, ends_at=now - timedelta(seconds=1))

        with self.assertRaises(ValidationError):
            validate_ai_entitlement(entitlement)


class CommercialCompatibilityTests(TestCase):

    def test_existing_billing_models_still_import_and_work(self):
        self.assertTrue(SubscriptionPlan.objects.filter(slug="professional").exists())
        user = make_user("compat_gate", "compat_gate@example.com")
        allowed, msg = can_create_contract(user)

        self.assertTrue(allowed)
        self.assertEqual(msg, "")
        self.assertFalse(UserSubscription.objects.filter(user=user).exists())

    def test_existing_billing_subscription_api_no_subscription_response_unchanged(self):
        user = make_user("compat_api", "compat_api@example.com")
        client = authed_client(user)

        response = client.get("/api/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"subscription": None})
