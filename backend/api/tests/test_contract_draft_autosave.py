# Regression tests for the draft autosave endpoint.

import json

from django.test import TestCase

from backend.contracts.models import Contract, ContractObligation, ContractServiceObligation, ContractVersion
from backend.payments.models import Payment

from .helpers import authed_client, make_subscription, make_user


class ContractDraftAutosaveTests(TestCase):
    def setUp(self):
        self.user = make_user("draft_owner", "draft_owner@example.com")
        make_subscription(self.user)
        self.client = authed_client(self.user)

    def _make_contract(self, **overrides):
        defaults = {
            "initiator": self.user,
            "counterparty_email": "counterparty@example.com",
            "title": "Draftable Contract",
            "status": "draft",
            "state": "created",
            "structure_type": "ONE_TIME",
        }
        defaults.update(overrides)
        return Contract.objects.create(**defaults)

    def test_patch_creates_first_version_and_updates_contract_state(self):
        contract = self._make_contract()
        payload = {
            "content_snapshot": json.dumps({
                "source": "editor_autosave",
                "editor_html": "<p>Draft body</p>",
                "sections": [{"id": "s1", "number": 1, "name": "Introduction"}],
            })
        }

        response = self.client.patch(f"/api/contracts/{contract.id}/draft/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual(contract.state, "drafting")
        self.assertEqual(contract.status, "draft")
        self.assertEqual(contract.versions.count(), 1)

        version = contract.versions.first()
        self.assertIsNotNone(version)
        snapshot = json.loads(version.content_snapshot)
        self.assertEqual(snapshot["editor_html"], "<p>Draft body</p>")
        self.assertEqual(snapshot["sections"][0]["name"], "Introduction")

    def test_patch_updates_existing_draft_without_creating_extra_versions(self):
        contract = self._make_contract()
        version = ContractVersion.objects.create(
            contract=contract,
            version_number=1,
            created_by=self.user,
            content_snapshot=json.dumps({
                "source": "editor_autosave",
                "editor_html": "<p>Original body</p>",
                "sections": [{"id": "s1", "number": 1, "name": "Introduction"}],
            }),
            status="draft",
        )

        response = self.client.patch(
            f"/api/contracts/{contract.id}/draft/",
            {
                "content_snapshot": json.dumps({
                    "source": "editor_autosave",
                    "editor_html": "<p>Updated body</p>",
                    "sections": [{"id": "s1", "number": 1, "name": "Introduction"}],
                })
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(contract.versions.count(), 1)
        version.refresh_from_db()
        snapshot = json.loads(version.content_snapshot)
        self.assertEqual(snapshot["editor_html"], "<p>Updated body</p>")

    def test_patch_rejects_prepared_contracts(self):
        contract = self._make_contract(state="prepared")
        ContractVersion.objects.create(
            contract=contract,
            version_number=1,
            created_by=self.user,
            content_snapshot=json.dumps({
                "source": "contract_prepare",
                "editor_html": "<p>Prepared body</p>",
                "prepared_terms": {"payment_terms": []},
            }),
            status="draft",
        )

        response = self.client.patch(
            f"/api/contracts/{contract.id}/draft/",
            {"content_snapshot": json.dumps({"source": "editor_autosave", "editor_html": "<p>Edited</p>"})},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(contract.versions.count(), 1)


class ContractPrepareTests(TestCase):
    def setUp(self):
        self.user = make_user("prepare_owner", "prepare-owner@example.com")
        self.counterparty = make_user("prepare_counterparty", "prepare-counterparty@example.com")
        make_subscription(self.user)
        self.client = authed_client(self.user)

    def _make_contract(self, **overrides):
        defaults = {
            "initiator": self.user,
            "counterparty_name": "Counter Party",
            "counterparty_email": self.counterparty.email,
            "title": "Preparable Contract",
            "contract_type": "Service Agreement",
            "status": "draft",
            "state": "drafting",
            "structure_type": "ONE_TIME",
            "currency": "USD",
        }
        defaults.update(overrides)
        return Contract.objects.create(**defaults)

    def _autosave(self, contract, html):
        response = self.client.patch(
            f"/api/contracts/{contract.id}/draft/",
            {
                "content_snapshot": json.dumps({
                    "source": "editor_autosave",
                    "editor_html": html,
                    "sections": [{"id": "s1", "number": 1, "name": "Terms"}],
                })
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _prepare(self, contract, text):
        return self.client.post(
            f"/api/contracts/{contract.id}/prepare/",
            {
                "editor_html": f"<p>{text}</p>",
                "sections": [{"id": "s1", "number": 1, "name": "Terms"}],
                "draft_text": text,
            },
            format="json",
        )

    def test_prepare_non_payment_contract_still_works(self):
        contract = self._make_contract(
            title="Confidentiality Agreement",
            contract_type="NDA / Confidentiality Agreement",
        )
        text = (
            "The parties shall keep confidential information private. "
            "This confidentiality obligation survives termination."
        )
        self._autosave(contract, f"<p>{text}</p>")

        response = self._prepare(contract, text)

        self.assertEqual(response.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual(contract.state, "prepared")
        self.assertEqual(contract.versions.count(), 1)
        self.assertEqual(ContractObligation.objects.filter(contract=contract).count(), 0)
        self.assertEqual(ContractServiceObligation.objects.filter(contract=contract).count(), 0)
        self.assertEqual(Payment.objects.filter(contract=contract).count(), 0)

    def test_prepare_payment_contract_creates_records_without_payment_version_field(self):
        contract = self._make_contract(
            title="Personal Loan Agreement",
            contract_type="Loan Agreement",
        )
        text = (
            "Payment Terms. The borrower shall pay USD 2500.00 on 2026-09-15. "
            "The lender shall provide the loan funds after signing."
        )
        self._autosave(contract, f"<h2>Payment Terms</h2><p>{text}</p>")

        response = self._prepare(contract, text)

        self.assertEqual(response.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual(contract.state, "prepared")
        self.assertEqual(contract.versions.count(), 1)
        self.assertEqual(ContractObligation.objects.filter(contract=contract).count(), 1)
        payment = Payment.objects.get(contract=contract)
        obligation = ContractObligation.objects.get(contract=contract)
        self.assertEqual(payment.payment_obligation, obligation)
        self.assertEqual(payment.metadata["contract_version_id"], str(obligation.version_id))

    def test_prepare_missing_registered_counterparty_returns_clear_error(self):
        contract = self._make_contract(counterparty_email="missing@example.com")
        text = "Payment Terms. The client shall pay USD 400.00 on 2026-08-01."
        self._autosave(contract, f"<p>{text}</p>")

        response = self._prepare(contract, text)

        self.assertEqual(response.status_code, 409)
        self.assertIn("counterparty email belongs to a registered user", response.data["error"])

    def test_failed_prepare_does_not_create_duplicate_records(self):
        contract = self._make_contract(counterparty_email="missing@example.com")
        text = "Payment Terms. The client shall pay USD 400.00 on 2026-08-01."
        self._autosave(contract, f"<p>{text}</p>")
        version_count = contract.versions.count()

        first = self._prepare(contract, text)
        second = self._prepare(contract, text)

        self.assertEqual(first.status_code, 409)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Contract.objects.filter(id=contract.id).count(), 1)
        self.assertEqual(contract.versions.count(), version_count)
        self.assertEqual(ContractObligation.objects.filter(contract=contract).count(), 0)
        self.assertEqual(ContractServiceObligation.objects.filter(contract=contract).count(), 0)
        self.assertEqual(Payment.objects.filter(contract=contract).count(), 0)

