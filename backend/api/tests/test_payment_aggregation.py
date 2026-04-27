# backend/api/tests/test_payment_aggregation.py
#
# B2 — Owner-wide aggregation verification: payment dashboard summary.
#
# The payment dashboard summary aggregates across all contracts where the
# authenticated user is a party (initiator or counterparty), regardless of
# which BusinessEntity the contract belongs to.
#
# These tests document and confirm that behavior is:
#   1. Intentionally owner-wide — payments from two different businesses
#      owned by the same user are aggregated together.
#   2. Owner-bounded — another user's payments are never included in the
#      summary, even if both users own businesses.

from decimal import Decimal

from django.test import TestCase

from backend.users.models import BusinessEntity
from backend.contracts.models import Contract
from .helpers import authed_client, make_payment, make_subscription, make_user


def make_entity(owner, name="Test Biz"):
    return BusinessEntity.objects.create(
        owner=owner,
        name=name,
        business_type="LLC",
    )


def make_business_contract(initiator, entity, counterparty_email="cp@example.com"):
    return Contract.objects.create(
        initiator=initiator,
        counterparty_email=counterparty_email,
        structure_type="ONE_TIME",
        max_versions=3,
        entity=entity,
        entity_type="business",
    )


URL = "/api/payments/dashboard-summary/"


class PaymentDashboardAggregationTests(TestCase):
    """
    GET /api/payments/dashboard-summary/

    Confirms that the dashboard aggregates owner-wide (across all businesses
    for the authenticated user) and excludes other users' payments entirely.
    """

    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.other = make_user("other", "other@example.com")
        make_subscription(self.owner)
        make_subscription(self.other)

        self.entity_a = make_entity(self.owner, "Owner Biz A")
        self.entity_b = make_entity(self.owner, "Owner Biz B")
        self.other_entity = make_entity(self.other, "Other Biz")

        self.contract_a = make_business_contract(self.owner, self.entity_a)
        self.contract_b = make_business_contract(self.owner, self.entity_b)
        self.other_contract = make_business_contract(self.other, self.other_entity)

        self.owner_client = authed_client(self.owner)
        self.other_client = authed_client(self.other)

    def test_dashboard_summary_aggregates_payments_across_both_businesses(self):
        """
        Owner has confirmed payments on contracts under two different businesses.
        The summary confirmed_amount is the sum of both — owner-wide aggregation
        is intentional, not a bug.
        """
        make_payment(self.contract_a, self.owner, self.other, amount="200.00", status="confirmed")
        make_payment(self.contract_b, self.owner, self.other, amount="150.00", status="confirmed")

        response = self.owner_client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["confirmed_amount"]), Decimal("350.00"))

    def test_dashboard_summary_count_spans_both_businesses(self):
        """
        The total payment count includes payments from both business contracts.
        """
        make_payment(self.contract_a, self.owner, self.other, amount="100.00", status="confirmed")
        make_payment(self.contract_b, self.owner, self.other, amount="100.00", status="draft")

        response = self.owner_client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_dashboard_summary_excludes_other_users_payments(self):
        """
        Another user's confirmed payment is never included in the owner's summary.
        Owner-wide aggregation is bounded to the owner's own contracts.
        """
        make_payment(self.contract_a, self.owner, self.other, amount="100.00", status="confirmed")
        make_payment(self.other_contract, self.other, self.owner, amount="999.00", status="confirmed")

        response = self.owner_client.get(URL)
        self.assertEqual(response.status_code, 200)
        # Only owner's own 100.00 — other user's 999.00 must not appear.
        self.assertEqual(Decimal(response.data["confirmed_amount"]), Decimal("100.00"))
        self.assertEqual(response.data["count"], 1)
