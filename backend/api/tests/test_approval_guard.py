# backend/api/tests/test_approval_guard.py
#
# Approval requested_from guard:
# - If requested_from is set, only that specific user may approve or reject.
# - Any contract party may approve/reject when requested_from is unset.
# - Non-parties are blocked at the is_party level regardless.

from django.test import TestCase

from backend.contracts.models import ContractApprovalRequest

from .helpers import (
    authed_client,
    make_approval_request,
    make_contract,
    make_user,
)


class ApprovalRequestedFromGuardTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")

    # ------------------------------------------------------------------
    # requested_from is set to alice
    # ------------------------------------------------------------------

    def test_requested_from_user_can_approve(self):
        approval = make_approval_request(self.contract, requested_from=self.alice)
        r = authed_client(self.alice).post(
            f"/api/contracts/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "approved")

    def test_other_party_cannot_approve_when_requested_from_is_set(self):
        # bob is a party but NOT the requested_from user
        approval = make_approval_request(self.contract, requested_from=self.alice)
        r = authed_client(self.bob).post(
            f"/api/contracts/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_approve_regardless_of_requested_from(self):
        approval = make_approval_request(self.contract, requested_from=self.alice)
        r = authed_client(self.charlie).post(
            f"/api/contracts/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 403)

    def test_requested_from_user_can_reject(self):
        approval = make_approval_request(self.contract, requested_from=self.alice)
        r = authed_client(self.alice).post(
            f"/api/contracts/approval-requests/{approval.id}/reject/"
        )
        self.assertEqual(r.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "rejected")

    def test_other_party_cannot_reject_when_requested_from_is_set(self):
        approval = make_approval_request(self.contract, requested_from=self.alice)
        r = authed_client(self.bob).post(
            f"/api/contracts/approval-requests/{approval.id}/reject/"
        )
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_reject_regardless_of_requested_from(self):
        approval = make_approval_request(self.contract, requested_from=self.alice)
        r = authed_client(self.charlie).post(
            f"/api/contracts/approval-requests/{approval.id}/reject/"
        )
        self.assertEqual(r.status_code, 403)

    # ------------------------------------------------------------------
    # requested_from is None — any party may act
    # ------------------------------------------------------------------

    def test_initiator_can_approve_when_no_requested_from(self):
        approval = make_approval_request(self.contract, requested_from=None)
        r = authed_client(self.alice).post(
            f"/api/contracts/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 200)

    def test_counterparty_can_approve_when_no_requested_from(self):
        approval = make_approval_request(self.contract, requested_from=None)
        r = authed_client(self.bob).post(
            f"/api/contracts/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 200)

    def test_stranger_still_blocked_when_no_requested_from(self):
        approval = make_approval_request(self.contract, requested_from=None)
        r = authed_client(self.charlie).post(
            f"/api/contracts/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 403)

    def test_counterparty_can_reject_when_no_requested_from(self):
        approval = make_approval_request(self.contract, requested_from=None)
        r = authed_client(self.bob).post(
            f"/api/contracts/approval-requests/{approval.id}/reject/"
        )
        self.assertEqual(r.status_code, 200)

    # ------------------------------------------------------------------
    # Obligations-domain approval endpoint has the same guard
    # ------------------------------------------------------------------

    def test_obligations_domain_approve_respects_requested_from(self):
        approval = make_approval_request(self.contract, requested_from=self.alice)
        # bob is party but not requested_from → 403
        r = authed_client(self.bob).post(
            f"/api/obligations/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 403)

    def test_obligations_domain_approve_allows_requested_from_user(self):
        approval = make_approval_request(self.contract, requested_from=self.alice)
        r = authed_client(self.alice).post(
            f"/api/obligations/approval-requests/{approval.id}/approve/"
        )
        self.assertEqual(r.status_code, 200)
