# backend/api/tests/test_activity.py
#
# Tests for the Activity domain:
# - GET /api/activity/        — cross-contract feed, scoped + paginated
# - GET /api/contracts/<id>/activity/ — contract-scoped feed, ownership enforced
# - Write-through hooks on contract, version, payment, obligation, approval mutations

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.activity.models import ContractActivity
from backend.contracts.models import (
    ContractApprovalRequest,
    ContractObligation,
    ContractServiceObligation,
)
from backend.payments.models import Payment

from .helpers import authed_client, make_contract, make_obligation, make_subscription, make_user, make_version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _activity_count(contract, activity_type=None):
    qs = ContractActivity.objects.filter(contract=contract)
    if activity_type:
        qs = qs.filter(activity_type=activity_type)
    return qs.count()


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class ActivityListEndpointTests(TestCase):
    """GET /api/activity/ — scoping, ownership, pagination."""

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")

        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")
        self.other_contract = make_contract(self.charlie, counterparty_email="other@example.com")

        # Seed some activity
        ContractActivity.objects.create(
            contract=self.contract,
            user=self.alice,
            activity_type="contract_created",
            description="Created.",
        )
        ContractActivity.objects.create(
            contract=self.other_contract,
            user=self.charlie,
            activity_type="contract_created",
            description="Charlie's contract.",
        )

    def test_initiator_sees_own_contract_activity(self):
        r = authed_client(self.alice).get("/api/activity/")
        self.assertEqual(r.status_code, 200)
        ids = [a["contract_id"] for a in r.data["results"]]
        self.assertIn(str(self.contract.id), ids)

    def test_counterparty_sees_shared_contract_activity(self):
        r = authed_client(self.bob).get("/api/activity/")
        self.assertEqual(r.status_code, 200)
        ids = [a["contract_id"] for a in r.data["results"]]
        self.assertIn(str(self.contract.id), ids)

    def test_stranger_does_not_see_others_activity(self):
        r = authed_client(self.charlie).get("/api/activity/")
        self.assertEqual(r.status_code, 200)
        ids = [a["contract_id"] for a in r.data["results"]]
        self.assertNotIn(str(self.contract.id), ids)

    def test_response_has_pagination_envelope(self):
        r = authed_client(self.alice).get("/api/activity/")
        self.assertIn("count", r.data)
        self.assertIn("page", r.data)
        self.assertIn("page_size", r.data)
        self.assertIn("results", r.data)

    def test_page_size_param_respected(self):
        # Add more records so we have more than 1
        for i in range(5):
            ContractActivity.objects.create(
                contract=self.contract,
                user=self.alice,
                activity_type="contract_updated",
                description=f"Update {i}",
            )
        r = authed_client(self.alice).get("/api/activity/?page_size=2")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 2)
        self.assertEqual(r.data["page_size"], 2)

    def test_contract_id_filter(self):
        r = authed_client(self.alice).get(f"/api/activity/?contract_id={self.contract.id}")
        self.assertEqual(r.status_code, 200)
        for a in r.data["results"]:
            self.assertEqual(a["contract_id"], str(self.contract.id))

    def test_activity_type_filter(self):
        ContractActivity.objects.create(
            contract=self.contract,
            user=self.alice,
            activity_type="version_created",
            description="Version.",
        )
        r = authed_client(self.alice).get("/api/activity/?activity_type=version_created")
        self.assertEqual(r.status_code, 200)
        for a in r.data["results"]:
            self.assertEqual(a["activity_type"], "version_created")

    def test_activity_record_fields(self):
        r = authed_client(self.alice).get("/api/activity/")
        self.assertEqual(r.status_code, 200)
        record = r.data["results"][0]
        self.assertIn("id", record)
        self.assertIn("contract_id", record)
        self.assertIn("user_id", record)
        self.assertIn("activity_type", record)
        self.assertIn("description", record)
        self.assertIn("metadata", record)
        self.assertIn("created_at", record)


class ContractActivityEndpointTests(TestCase):
    """GET /api/contracts/<id>/activity/ — ownership and correct scoping."""

    def setUp(self):
        self.alice = make_user("alice_ca", "alice_ca@example.com")
        self.bob = make_user("bob_ca", "bob_ca@example.com")
        self.charlie = make_user("charlie_ca", "charlie_ca@example.com")

        self.contract = make_contract(self.alice, counterparty_email="bob_ca@example.com")
        ContractActivity.objects.create(
            contract=self.contract,
            user=self.alice,
            activity_type="contract_created",
            description="Created.",
        )

    def test_initiator_can_read_contract_activity(self):
        r = authed_client(self.alice).get(f"/api/contracts/{self.contract.id}/activity/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)

    def test_counterparty_can_read_contract_activity(self):
        r = authed_client(self.bob).get(f"/api/contracts/{self.contract.id}/activity/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)

    def test_stranger_cannot_read_contract_activity(self):
        r = authed_client(self.charlie).get(f"/api/contracts/{self.contract.id}/activity/")
        self.assertEqual(r.status_code, 403)

    def test_contract_activity_has_pagination_envelope(self):
        r = authed_client(self.alice).get(f"/api/contracts/{self.contract.id}/activity/")
        self.assertIn("count", r.data)
        self.assertIn("page", r.data)
        self.assertIn("page_size", r.data)
        self.assertIn("results", r.data)

    def test_nonexistent_contract_returns_404(self):
        r = authed_client(self.alice).get(
            "/api/contracts/00000000-0000-0000-0000-000000000000/activity/"
        )
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# Write-through hook tests
# ---------------------------------------------------------------------------

class ContractCreatedHookTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_cc", "alice_cc@example.com")
        make_subscription(self.alice)

    def test_contract_create_logs_activity(self):
        r = authed_client(self.alice).post(
            "/api/contracts/",
            {"counterparty_email": "bob@example.com", "structure_type": "ONE_TIME"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        contract_id = r.data["id"]
        self.assertEqual(
            _activity_count_by_id(contract_id, "contract_created"), 1
        )


class VersionHookTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_vh", "alice_vh@example.com")
        self.bob = make_user("bob_vh", "bob_vh@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_vh@example.com")

    def test_version_create_logs_activity(self):
        authed_client(self.alice).post(
            f"/api/contracts/{self.contract.id}/versions/",
            {"content_snapshot": "Draft terms."},
            format="json",
        )
        self.assertEqual(_activity_count(self.contract, "version_created"), 1)

    def test_version_sign_logs_activity(self):
        version = make_version(self.contract, self.alice)
        authed_client(self.bob).post(
            f"/api/contracts/{self.contract.id}/versions/{version.id}/sign/"
        )
        self.assertEqual(_activity_count(self.contract, "version_signed"), 1)

    def test_version_reject_logs_activity(self):
        version = make_version(self.contract, self.alice)
        authed_client(self.bob).post(
            f"/api/contracts/{self.contract.id}/versions/{version.id}/reject/"
        )
        self.assertEqual(_activity_count(self.contract, "version_rejected"), 1)


class PaymentHookTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_ph", "alice_ph@example.com")
        self.bob = make_user("bob_ph", "bob_ph@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_ph@example.com")
        version = make_version(self.contract, self.alice)
        self.obligation = make_obligation(self.contract, version, self.alice, self.bob)

    def _create_payment(self, amount="100.00", status="draft"):
        return Payment.objects.create(
            contract=self.contract,
            payer=self.alice,
            payee=self.bob,
            amount=Decimal(amount),
            status=status,
        )

    def test_payment_confirm_logs_activity(self):
        payment = self._create_payment(status="pending")
        authed_client(self.alice).post(f"/api/payments/{payment.id}/confirm/")
        self.assertEqual(_activity_count(self.contract, "payment_confirmed"), 1)

    def test_payment_failed_logs_activity(self):
        payment = self._create_payment(status="pending")
        authed_client(self.alice).post(f"/api/payments/{payment.id}/fail/")
        self.assertEqual(_activity_count(self.contract, "payment_failed"), 1)

    def test_payment_cancelled_logs_activity(self):
        payment = self._create_payment(status="draft")
        authed_client(self.alice).post(f"/api/payments/{payment.id}/cancel/")
        self.assertEqual(_activity_count(self.contract, "payment_cancelled"), 1)

    def test_payment_refunded_logs_activity(self):
        payment = self._create_payment(status="confirmed")
        authed_client(self.alice).post(f"/api/payments/{payment.id}/refund/")
        self.assertEqual(_activity_count(self.contract, "payment_refunded"), 1)

    def test_payment_reversed_logs_activity(self):
        payment = self._create_payment(status="confirmed")
        authed_client(self.alice).post(f"/api/payments/{payment.id}/reverse/")
        self.assertEqual(_activity_count(self.contract, "payment_reversed"), 1)


class ObligationResolveHookTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_or", "alice_or@example.com")
        self.bob = make_user("bob_or", "bob_or@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_or@example.com")
        version = make_version(self.contract, self.alice)
        self.service_ob = ContractServiceObligation.objects.create(
            contract=self.contract,
            version=version,
            obligor=self.alice,
            obligee=self.bob,
            description="Deliver project.",
            due_date=timezone.now() + __import__("datetime").timedelta(days=30),
        )

    def test_service_obligation_resolve_logs_activity(self):
        authed_client(self.alice).post(
            f"/api/contracts/obligations/service/{self.service_ob.id}/resolve/"
        )
        self.assertEqual(_activity_count(self.contract, "obligation_resolved"), 1)


# ---------------------------------------------------------------------------
# Helper for tests that need to check by contract UUID string
# ---------------------------------------------------------------------------

def _activity_count_by_id(contract_id_str, activity_type=None):
    from backend.contracts.models import Contract
    contract = Contract.objects.get(id=contract_id_str)
    return _activity_count(contract, activity_type)
