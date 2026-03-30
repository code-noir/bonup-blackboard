# backend/api/tests/test_role_switch.py
#
# Role switch rules:
# - Only the counterparty may request a role switch.
# - Only the initiator may confirm it.
# - Only one pending request per contract at a time.
# - Requests expire after 7 days (TTL).  Confirming an expired request → 410.
# - Role switch is blocked once a signed version exists.
# - On confirmation: old contract is deleted, new contract is created with
#   roles swapped (new initiator = old counterparty, new counterparty email =
#   old initiator's email).  The counterparty must have a registered account.

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from backend.contracts.models import Contract, ContractRoleSwitchRequest

from .helpers import authed_client, make_contract, make_user, make_version


class RoleSwitchRequestTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")

    def _request_url(self):
        return f"/api/contracts/{self.contract.id}/request-role-switch/"

    def test_counterparty_can_request_role_switch(self):
        r = authed_client(self.bob).post(self._request_url())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "pending")

    def test_initiator_cannot_request_role_switch(self):
        r = authed_client(self.alice).post(self._request_url())
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_request_role_switch(self):
        r = authed_client(self.charlie).post(self._request_url())
        self.assertEqual(r.status_code, 403)

    def test_duplicate_pending_request_rejected(self):
        authed_client(self.bob).post(self._request_url())
        r = authed_client(self.bob).post(self._request_url())
        self.assertEqual(r.status_code, 409)

    def test_expired_stale_request_is_cleaned_and_new_request_succeeds(self):
        # Pre-create an already-expired pending request.
        ContractRoleSwitchRequest.objects.create(
            contract=self.contract,
            requested_by=self.bob,
            status="pending",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        # New request should succeed because the stale one is auto-expired.
        r = authed_client(self.bob).post(self._request_url())
        self.assertEqual(r.status_code, 201)

    def test_role_switch_blocked_after_signing(self):
        v = make_version(self.contract, self.alice)
        v.status = "signed"
        v.save(update_fields=["status"])

        r = authed_client(self.bob).post(self._request_url())
        self.assertEqual(r.status_code, 403)


class RoleSwitchConfirmTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")

    def _confirm_url(self):
        return f"/api/contracts/{self.contract.id}/confirm-role-switch/"

    def _create_pending_request(self, ttl_days=7):
        return ContractRoleSwitchRequest.objects.create(
            contract=self.contract,
            requested_by=self.bob,
            status="pending",
            expires_at=timezone.now() + timedelta(days=ttl_days),
        )

    def test_counterparty_cannot_confirm_role_switch(self):
        self._create_pending_request()
        r = authed_client(self.bob).post(self._confirm_url())
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_confirm_role_switch(self):
        self._create_pending_request()
        r = authed_client(self.charlie).post(self._confirm_url())
        self.assertEqual(r.status_code, 403)

    def test_confirm_with_no_pending_request_returns_404(self):
        r = authed_client(self.alice).post(self._confirm_url())
        self.assertEqual(r.status_code, 404)

    def test_confirm_expired_request_returns_410(self):
        ContractRoleSwitchRequest.objects.create(
            contract=self.contract,
            requested_by=self.bob,
            status="pending",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        r = authed_client(self.alice).post(self._confirm_url())
        self.assertEqual(r.status_code, 410)

    def test_confirm_blocked_after_signing(self):
        self._create_pending_request()
        v = make_version(self.contract, self.alice)
        v.status = "signed"
        v.save(update_fields=["status"])

        r = authed_client(self.alice).post(self._confirm_url())
        self.assertEqual(r.status_code, 403)

    def test_confirm_requires_counterparty_account(self):
        # Create a contract whose counterparty email belongs to no registered user.
        # (Deleting bob would cascade-delete the role switch request, so we test
        # the scenario via a fresh contract with an unregistered counterparty.)
        unregistered_email = "unregistered@example.com"
        contract = make_contract(self.alice, counterparty_email=unregistered_email)
        ContractRoleSwitchRequest.objects.create(
            contract=contract,
            requested_by=self.alice,  # requested_by just needs to exist to pass CASCADE
            status="pending",
            expires_at=timezone.now() + timedelta(days=7),
        )
        r = authed_client(self.alice).post(f"/api/contracts/{contract.id}/confirm-role-switch/")
        self.assertEqual(r.status_code, 409)

    def test_confirm_creates_new_contract_with_swapped_roles(self):
        self._create_pending_request()
        old_id = self.contract.id

        r = authed_client(self.alice).post(self._confirm_url())
        self.assertEqual(r.status_code, 201)

        new_id = r.data["new_contract_id"]
        self.assertNotEqual(str(old_id), new_id)

        # Original contract is deleted.
        self.assertFalse(Contract.objects.filter(id=old_id).exists())

        # New contract has swapped roles.
        new_contract = Contract.objects.get(id=new_id)
        self.assertEqual(new_contract.initiator_id, self.bob.pk)
        self.assertEqual(new_contract.counterparty_email, self.alice.email)

    def test_confirm_new_contract_has_no_versions(self):
        self._create_pending_request()
        r = authed_client(self.alice).post(self._confirm_url())
        new_contract = Contract.objects.get(id=r.data["new_contract_id"])
        self.assertEqual(new_contract.versions.count(), 0)
