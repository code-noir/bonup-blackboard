# backend/api/tests/test_payment_transitions.py
#
# Payment status-machine guards.
#
# Allowed transitions:
#   draft    → pending
#   pending  → confirmed
#   pending  → failed
#   draft    → cancelled
#   pending  → cancelled
#   confirmed → refunded
#   confirmed → reversed
#
# Every other combination must return 409 Conflict.

from django.test import TestCase

from .helpers import authed_client, make_contract, make_payment, make_user


class PaymentTransitionTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")

    def _payment(self, status):
        return make_payment(self.contract, payer=self.alice, payee=self.bob, status=status)

    def _url(self, payment, action):
        return f"/api/payments/{payment.id}/{action}/"

    def _post(self, payment, action):
        return authed_client(self.alice).post(self._url(payment, action))

    def _detail_url(self, payment):
        return f"/api/payments/{payment.id}/"

    # ------------------------------------------------------------------
    # Valid transitions — should return 200
    # ------------------------------------------------------------------

    def test_draft_to_pending(self):
        p = self._payment("draft")
        r = self._post(p, "pending")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "pending")

    def test_pending_to_confirmed(self):
        p = self._payment("pending")
        r = self._post(p, "confirm")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "confirmed")

    def test_pending_to_failed(self):
        p = self._payment("pending")
        r = self._post(p, "fail")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "failed")

    def test_draft_to_cancelled(self):
        p = self._payment("draft")
        r = self._post(p, "cancel")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "cancelled")

    def test_pending_to_cancelled(self):
        p = self._payment("pending")
        r = self._post(p, "cancel")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "cancelled")

    def test_confirmed_to_refunded(self):
        p = self._payment("confirmed")
        r = self._post(p, "refund")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "refunded")

    def test_confirmed_to_reversed(self):
        p = self._payment("confirmed")
        r = self._post(p, "reverse")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "reversed")

    # ------------------------------------------------------------------
    # Invalid transitions — must return 409
    # ------------------------------------------------------------------

    def test_draft_cannot_be_confirmed(self):
        r = self._post(self._payment("draft"), "confirm")
        self.assertEqual(r.status_code, 409)

    def test_draft_cannot_be_failed(self):
        r = self._post(self._payment("draft"), "fail")
        self.assertEqual(r.status_code, 409)

    def test_draft_cannot_be_refunded(self):
        r = self._post(self._payment("draft"), "refund")
        self.assertEqual(r.status_code, 409)

    def test_draft_cannot_be_reversed(self):
        r = self._post(self._payment("draft"), "reverse")
        self.assertEqual(r.status_code, 409)

    def test_confirmed_cannot_be_pending(self):
        r = self._post(self._payment("confirmed"), "pending")
        self.assertEqual(r.status_code, 409)

    def test_confirmed_cannot_be_failed(self):
        r = self._post(self._payment("confirmed"), "fail")
        self.assertEqual(r.status_code, 409)

    def test_confirmed_cannot_be_cancelled(self):
        r = self._post(self._payment("confirmed"), "cancel")
        self.assertEqual(r.status_code, 409)

    def test_failed_cannot_be_confirmed(self):
        r = self._post(self._payment("failed"), "confirm")
        self.assertEqual(r.status_code, 409)

    def test_cancelled_cannot_be_pending(self):
        r = self._post(self._payment("cancelled"), "pending")
        self.assertEqual(r.status_code, 409)

    def test_refunded_cannot_be_confirmed(self):
        r = self._post(self._payment("refunded"), "confirm")
        self.assertEqual(r.status_code, 409)

    def test_reversed_cannot_be_confirmed(self):
        r = self._post(self._payment("reversed"), "confirm")
        self.assertEqual(r.status_code, 409)

    # ------------------------------------------------------------------
    # Ownership check on transitions
    # ------------------------------------------------------------------

    def test_stranger_cannot_trigger_transition(self):
        charlie = make_user("charlie", "charlie@example.com")
        p = self._payment("draft")
        r = authed_client(charlie).post(self._url(p, "pending"))
        self.assertEqual(r.status_code, 403)

    def test_counterparty_can_trigger_transition(self):
        p = self._payment("draft")
        r = authed_client(self.bob).post(self._url(p, "pending"))
        self.assertEqual(r.status_code, 200)

    # ------------------------------------------------------------------
    # Detail PATCH must not bypass status transitions
    # ------------------------------------------------------------------

    def test_patch_cannot_change_status(self):
        p = self._payment("draft")

        r = authed_client(self.alice).patch(
            self._detail_url(p),
            {"status": "confirmed"},
            format="json",
        )

        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "draft")

    def test_patch_can_update_reference_without_changing_status(self):
        p = self._payment("draft")

        r = authed_client(self.alice).patch(
            self._detail_url(p),
            {"reference": "INV-001"},
            format="json",
        )

        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "draft")
        self.assertEqual(p.reference, "INV-001")
