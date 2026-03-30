# backend/api/tests/test_idempotency.py
#
# Idempotency key rules:
# - If idempotency_key is present and a Payment with that key already exists,
#   the existing payment is returned with 200 (not 201).
# - If idempotency_key is absent, normal creation proceeds (201).
# - idempotency_key is globally unique — two payments cannot share the same key.
# - The check applies to all three creation endpoints:
#     POST /api/payments/
#     POST /api/payments/contracts/<id>/
#     POST /api/payments/obligations/<id>/

from django.test import TestCase

from backend.payments.models import Payment

from .helpers import (
    authed_client,
    make_contract,
    make_obligation,
    make_payment,
    make_user,
    make_version,
)


class IdempotencyBasePayload:
    """Mixin: provides a fresh valid payload and contract for each test."""

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")
        self._client = authed_client(self.alice)

    def _payload(self, key=None):
        data = {
            "contract": str(self.contract.id),
            "payer": self.alice.pk,
            "payee": self.bob.pk,
            "amount": "50.00",
            "payment_method": "manual",
        }
        if key is not None:
            data["idempotency_key"] = key
        return data


class PaymentListCreateIdempotencyTests(IdempotencyBasePayload, TestCase):

    URL = "/api/payments/"

    def test_first_request_creates_payment(self):
        r = self._client.post(self.URL, self._payload(key="key-001"), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Payment.objects.count(), 1)

    def test_duplicate_key_returns_200_not_201(self):
        self._client.post(self.URL, self._payload(key="key-002"), format="json")
        r = self._client.post(self.URL, self._payload(key="key-002"), format="json")
        self.assertEqual(r.status_code, 200)

    def test_duplicate_key_does_not_create_second_payment(self):
        self._client.post(self.URL, self._payload(key="key-003"), format="json")
        self._client.post(self.URL, self._payload(key="key-003"), format="json")
        self.assertEqual(Payment.objects.count(), 1)

    def test_duplicate_key_returns_same_payment_id(self):
        r1 = self._client.post(self.URL, self._payload(key="key-004"), format="json")
        r2 = self._client.post(self.URL, self._payload(key="key-004"), format="json")
        self.assertEqual(r1.data["id"], r2.data["id"])

    def test_different_keys_create_distinct_payments(self):
        self._client.post(self.URL, self._payload(key="key-005a"), format="json")
        self._client.post(self.URL, self._payload(key="key-005b"), format="json")
        self.assertEqual(Payment.objects.count(), 2)

    def test_no_key_still_creates_payment(self):
        r = self._client.post(self.URL, self._payload(), format="json")
        self.assertEqual(r.status_code, 201)

    def test_idempotency_key_stored_on_payment(self):
        self._client.post(self.URL, self._payload(key="key-007"), format="json")
        payment = Payment.objects.get()
        self.assertEqual(payment.idempotency_key, "key-007")

    def test_idempotency_key_in_response(self):
        r = self._client.post(self.URL, self._payload(key="key-008"), format="json")
        self.assertEqual(r.data["idempotency_key"], "key-008")


class ContractPaymentIdempotencyTests(IdempotencyBasePayload, TestCase):

    def _url(self):
        return f"/api/payments/contracts/{self.contract.id}/"

    def _contract_payload(self, key=None):
        data = {
            "payer": self.alice.pk,
            "payee": self.bob.pk,
            "amount": "75.00",
            "payment_method": "manual",
        }
        if key is not None:
            data["idempotency_key"] = key
        return data

    def test_first_request_creates_payment(self):
        r = self._client.post(self._url(), self._contract_payload(key="ckey-001"), format="json")
        self.assertEqual(r.status_code, 201)

    def test_duplicate_key_returns_existing(self):
        self._client.post(self._url(), self._contract_payload(key="ckey-002"), format="json")
        r = self._client.post(self._url(), self._contract_payload(key="ckey-002"), format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)

    def test_duplicate_key_returns_same_id(self):
        r1 = self._client.post(self._url(), self._contract_payload(key="ckey-003"), format="json")
        r2 = self._client.post(self._url(), self._contract_payload(key="ckey-003"), format="json")
        self.assertEqual(r1.data["id"], r2.data["id"])

    def test_no_key_creates_normally(self):
        r = self._client.post(self._url(), self._contract_payload(), format="json")
        self.assertEqual(r.status_code, 201)


class ObligationPaymentIdempotencyTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")
        self.version = make_version(self.contract, self.alice)
        self.obligation = make_obligation(self.contract, self.version, self.alice, self.bob)
        self._client = authed_client(self.alice)

    def _url(self):
        return f"/api/payments/obligations/{self.obligation.id}/"

    def _payload(self, key=None):
        data = {
            "payer": self.alice.pk,
            "payee": self.bob.pk,
            "amount": "25.00",
            "payment_method": "manual",
        }
        if key is not None:
            data["idempotency_key"] = key
        return data

    def test_first_request_creates_payment(self):
        r = self._client.post(self._url(), self._payload(key="okey-001"), format="json")
        self.assertEqual(r.status_code, 201)

    def test_duplicate_key_returns_existing(self):
        self._client.post(self._url(), self._payload(key="okey-002"), format="json")
        r = self._client.post(self._url(), self._payload(key="okey-002"), format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)

    def test_duplicate_key_returns_same_id(self):
        r1 = self._client.post(self._url(), self._payload(key="okey-003"), format="json")
        r2 = self._client.post(self._url(), self._payload(key="okey-003"), format="json")
        self.assertEqual(r1.data["id"], r2.data["id"])

    def test_no_key_creates_normally(self):
        r = self._client.post(self._url(), self._payload(), format="json")
        self.assertEqual(r.status_code, 201)
