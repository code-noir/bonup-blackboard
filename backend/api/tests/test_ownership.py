# backend/api/tests/test_ownership.py
#
# Ownership isolation: a contract is visible only to its initiator and
# its counterparty.  A third party (charlie) must be blocked on every
# relevant endpoint; the counterparty (bob) must have full read access.

from django.test import TestCase

from .helpers import (
    authed_client,
    make_contract,
    make_obligation,
    make_payment,
    make_user,
    make_version,
)


class OwnershipContractTests(TestCase):
    """Contract CRUD endpoints respect party membership."""

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")

        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")

        # Charlie has his own unrelated contract — must not bleed into alice's list.
        self.charlie_contract = make_contract(self.charlie, counterparty_email="other@example.com")

    # ------------------------------------------------------------------
    # List endpoint is scoped — no data leakage across users
    # ------------------------------------------------------------------

    def test_initiator_list_returns_own_contracts(self):
        r = authed_client(self.alice).get("/api/contracts/")
        ids = [c["id"] for c in r.data]
        self.assertIn(str(self.contract.id), ids)
        self.assertNotIn(str(self.charlie_contract.id), ids)

    def test_counterparty_list_returns_shared_contract(self):
        r = authed_client(self.bob).get("/api/contracts/")
        ids = [c["id"] for c in r.data]
        self.assertIn(str(self.contract.id), ids)

    def test_stranger_list_excludes_others_contracts(self):
        r = authed_client(self.charlie).get("/api/contracts/")
        ids = [c["id"] for c in r.data]
        self.assertNotIn(str(self.contract.id), ids)

    # ------------------------------------------------------------------
    # Detail — retrieve
    # ------------------------------------------------------------------

    def test_initiator_can_retrieve_own_contract(self):
        r = authed_client(self.alice).get(f"/api/contracts/{self.contract.id}/")
        self.assertEqual(r.status_code, 200)

    def test_counterparty_can_retrieve_contract(self):
        r = authed_client(self.bob).get(f"/api/contracts/{self.contract.id}/")
        self.assertEqual(r.status_code, 200)

    def test_stranger_cannot_retrieve_contract(self):
        r = authed_client(self.charlie).get(f"/api/contracts/{self.contract.id}/")
        self.assertEqual(r.status_code, 403)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def test_initiator_can_update_contract(self):
        r = authed_client(self.alice).patch(
            f"/api/contracts/{self.contract.id}/",
            {"structure_type": "ONGOING"},
            format="json",
        )
        self.assertIn(r.status_code, (200, 400))  # 400 = validation, not 403

    def test_stranger_cannot_update_contract(self):
        r = authed_client(self.charlie).patch(
            f"/api/contracts/{self.contract.id}/",
            {"structure_type": "ONGOING"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def test_initiator_can_delete_contract(self):
        r = authed_client(self.alice).delete(f"/api/contracts/{self.contract.id}/")
        self.assertEqual(r.status_code, 204)

    def test_stranger_cannot_delete_contract(self):
        r = authed_client(self.charlie).delete(f"/api/contracts/{self.contract.id}/")
        self.assertEqual(r.status_code, 403)


class OwnershipObligationTests(TestCase):
    """Obligation endpoints respect party membership."""

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")

        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")
        self.version = make_version(self.contract, self.alice)
        self.obligation = make_obligation(self.contract, self.version, self.alice, self.bob)

    def test_initiator_list_contains_own_obligations(self):
        r = authed_client(self.alice).get("/api/obligations/")
        self.assertEqual(r.status_code, 200)
        results = r.data.get("results", r.data)
        ids = [str(o.get("id", "")) for o in results]
        self.assertIn(str(self.obligation.id), ids)

    def test_counterparty_list_contains_shared_obligations(self):
        r = authed_client(self.bob).get("/api/obligations/")
        self.assertEqual(r.status_code, 200)
        results = r.data.get("results", r.data)
        ids = [str(o.get("id", "")) for o in results]
        self.assertIn(str(self.obligation.id), ids)

    def test_stranger_list_excludes_others_obligations(self):
        r = authed_client(self.charlie).get("/api/obligations/")
        self.assertEqual(r.status_code, 200)
        results = r.data.get("results", r.data)
        ids = [str(o.get("id", "")) for o in results]
        self.assertNotIn(str(self.obligation.id), ids)

    def test_initiator_can_retrieve_obligation(self):
        r = authed_client(self.alice).get(f"/api/obligations/payment/{self.obligation.id}/")
        self.assertEqual(r.status_code, 200)

    def test_counterparty_can_retrieve_obligation(self):
        r = authed_client(self.bob).get(f"/api/obligations/payment/{self.obligation.id}/")
        self.assertEqual(r.status_code, 200)

    def test_stranger_cannot_retrieve_obligation(self):
        r = authed_client(self.charlie).get(f"/api/obligations/payment/{self.obligation.id}/")
        self.assertEqual(r.status_code, 403)


class OwnershipPaymentTests(TestCase):
    """Payment endpoints respect party membership."""

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")

        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")
        self.payment = make_payment(self.contract, payer=self.alice, payee=self.bob)

        # Charlie's own unrelated payment — must not show up in alice's list.
        charlie_contract = make_contract(self.charlie, counterparty_email="other@example.com")
        self.charlie_payment = make_payment(charlie_contract, payer=self.charlie, payee=self.charlie)

    def test_initiator_list_contains_own_payments(self):
        r = authed_client(self.alice).get("/api/payments/")
        ids = [p["id"] for p in r.data["results"]]
        self.assertIn(str(self.payment.id), ids)
        self.assertNotIn(str(self.charlie_payment.id), ids)

    def test_counterparty_list_contains_shared_payments(self):
        r = authed_client(self.bob).get("/api/payments/")
        ids = [p["id"] for p in r.data["results"]]
        self.assertIn(str(self.payment.id), ids)

    def test_stranger_list_excludes_others_payments(self):
        r = authed_client(self.charlie).get("/api/payments/")
        ids = [p["id"] for p in r.data["results"]]
        self.assertNotIn(str(self.payment.id), ids)

    def test_initiator_can_retrieve_payment(self):
        r = authed_client(self.alice).get(f"/api/payments/{self.payment.id}/")
        self.assertEqual(r.status_code, 200)

    def test_counterparty_can_retrieve_payment(self):
        r = authed_client(self.bob).get(f"/api/payments/{self.payment.id}/")
        self.assertEqual(r.status_code, 200)

    def test_stranger_cannot_retrieve_payment(self):
        r = authed_client(self.charlie).get(f"/api/payments/{self.payment.id}/")
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_patch_payment(self):
        r = authed_client(self.charlie).patch(
            f"/api/payments/{self.payment.id}/",
            {"reference": "hacked"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_delete_payment(self):
        r = authed_client(self.charlie).delete(f"/api/payments/{self.payment.id}/")
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_transition_payment(self):
        r = authed_client(self.charlie).post(f"/api/payments/{self.payment.id}/pending/")
        self.assertEqual(r.status_code, 403)
