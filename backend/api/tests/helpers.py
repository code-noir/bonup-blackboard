# backend/api/tests/helpers.py
#
# Shared fixtures for API-layer tests.

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from backend.billing.models import SubscriptionPlan, UserSubscription
from backend.contracts.models import (
    Contract,
    ContractApprovalRequest,
    ContractObligation,
    ContractVersion,
)
from backend.payments.models import Payment

User = get_user_model()


# ------------------------------------------------------------------
# Object builders
# ------------------------------------------------------------------

def make_user(username, email, password="testpass123"):
    return User.objects.create_user(username=username, email=email, password=password)


def make_contract(initiator, counterparty_email, max_versions=3, structure_type="ONE_TIME"):
    return Contract.objects.create(
        initiator=initiator,
        counterparty_email=counterparty_email,
        structure_type=structure_type,
        max_versions=max_versions,
    )


def make_version(contract, created_by, content_snapshot="Draft terms.", status="draft"):
    version_number = contract.versions.count() + 1
    return ContractVersion.objects.create(
        contract=contract,
        version_number=version_number,
        created_by=created_by,
        content_snapshot=content_snapshot,
        status=status,
    )


def make_obligation(contract, version, obligor, obligee, amount_due="500.00"):
    return ContractObligation.objects.create(
        contract=contract,
        version=version,
        obligor=obligor,
        obligee=obligee,
        installment_number=1,
        amount_due=Decimal(amount_due),
        due_date=timezone.now() + timedelta(days=30),
    )


def make_payment(contract, payer, payee, amount="100.00", status="draft"):
    return Payment.objects.create(
        contract=contract,
        payer=payer,
        payee=payee,
        amount=Decimal(amount),
        status=status,
    )


def make_approval_request(contract, summary="Approve this.", requested_from=None):
    return ContractApprovalRequest.objects.create(
        contract=contract,
        summary=summary,
        requested_from=requested_from,
        status="pending",
    )


def make_subscription(user):
    """
    Give *user* an unlimited subscription for test purposes.

    Uses get_or_create on the plan so this works in both TestCase (where
    migration-seeded plans persist) and TransactionTestCase (where they are
    wiped between tests).
    """
    plan, _ = SubscriptionPlan.objects.get_or_create(
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
    # Ensure has_sol is set even if plan already existed before this field was added
    if not plan.has_sol:
        plan.has_sol = True
        plan.save(update_fields=["has_sol"])
    return UserSubscription.objects.create(
        user=user,
        plan=plan,
        status="active",
        billing_period="monthly",
        current_period_start=timezone.now(),
    )


def authed_client(user):
    """Return a DRF APIClient authenticated as *user* (bypasses JWT)."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client
