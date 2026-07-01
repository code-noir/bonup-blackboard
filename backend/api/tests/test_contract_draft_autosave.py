# Regression tests for the draft autosave endpoint.

import json

from django.test import TestCase

from backend.agreement_exchange.models import AgreementExchange
from backend.contracts.models import (
    Contract,
    ContractExtractionCandidate,
    ContractExtractionRun,
    ContractObligation,
    ContractServiceObligation,
    ContractVersion,
)
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

    def test_prepare_shadow_writes_extraction_run_and_candidates(self):
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
        self.assertIn("prepared_terms", response.data)
        self.assertIn("created_records", response.data)
        self.assertNotIn("extraction_run", response.data)
        version = contract.versions.get()
        run = ContractExtractionRun.objects.get(contract=contract, stage=ContractExtractionRun.STAGE_PREPARE)
        self.assertEqual(run.contract_version, version)
        self.assertEqual(run.source_kind, ContractExtractionRun.SOURCE_EDITOR_HTML)
        self.assertEqual(run.engine_name, "prepare_shadow_extractor")
        self.assertEqual(run.engine_version, "v1")
        self.assertEqual(run.status, ContractExtractionRun.STATUS_COMPLETED)
        self.assertEqual(run.created_by, self.user)
        self.assertTrue(run.completed_at)
        self.assertTrue(run.source_hash)
        self.assertEqual(run.metadata["shadow_write"], True)
        self.assertEqual(run.metadata["prepare_version_id"], str(version.id))
        self.assertEqual(run.metadata["source"], "ContractPrepareAPIView")

        candidates = ContractExtractionCandidate.objects.filter(contract=contract, run=run)
        candidate_types = set(candidates.values_list("candidate_type", flat=True))
        self.assertIn(ContractExtractionCandidate.TYPE_PAYMENT, candidate_types)
        self.assertIn(ContractExtractionCandidate.TYPE_SERVICE_WORK, candidate_types)
        payment_candidate = candidates.get(candidate_type=ContractExtractionCandidate.TYPE_PAYMENT)
        self.assertEqual(payment_candidate.review_status, ContractExtractionCandidate.REVIEW_PENDING)
        self.assertEqual(payment_candidate.amount, 2500)
        self.assertEqual(str(payment_candidate.due_date), "2026-09-15")
        self.assertEqual(payment_candidate.currency, "USD")
        self.assertEqual(payment_candidate.metadata["shadow_write"], True)
        self.assertEqual(payment_candidate.metadata["original_model"], "ContractObligation")
        self.assertEqual(payment_candidate.raw_payload["amount"], "2500.00")

    def test_prepare_shadow_write_is_idempotent_for_same_source(self):
        contract = self._make_contract(
            title="Personal Loan Agreement",
            contract_type="Loan Agreement",
        )
        text = "Payment Terms. The borrower shall pay USD 400.00 on 2026-08-01."
        self._autosave(contract, f"<p>{text}</p>")

        first = self._prepare(contract, text)
        first_run = ContractExtractionRun.objects.get(contract=contract, stage=ContractExtractionRun.STAGE_PREPARE)
        first_candidate_ids = set(
            ContractExtractionCandidate.objects.filter(contract=contract).values_list("id", flat=True)
        )
        second = self._prepare(contract, text)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ContractExtractionRun.objects.filter(contract=contract).count(), 1)
        self.assertEqual(
            set(ContractExtractionCandidate.objects.filter(contract=contract).values_list("id", flat=True)),
            first_candidate_ids,
        )
        self.assertEqual(ContractExtractionRun.objects.get(contract=contract).id, first_run.id)
        self.assertEqual(ContractObligation.objects.filter(contract=contract).count(), 1)
        self.assertEqual(Payment.objects.filter(contract=contract).count(), 1)

    def test_prepare_shadow_splits_service_contract_candidates(self):
        contract = self._make_contract(
            title="Website Design Service Agreement",
            contract_type="Service Agreement",
            counterparty_name="Maria Jean",
        )
        text = """Website Design Service Agreement

Client: Alcide
Contractor: Maria Jean

Contractor agrees to design a five-page business website for Client.

Contractor must deliver the homepage mockup by August 10, 2026.
Contractor must deliver the full website by September 1, 2026.

Client agrees to pay Contractor $500 when the homepage mockup is delivered.
Client agrees to pay Contractor $1,000 when the full website is completed.

Contractor must fix reasonable bugs reported within 7 days after delivery.
Client must review each delivery within 5 days.
""".strip()
        self._autosave(contract, "".join(f"<p>{line}</p>" if line else "<p></p>" for line in text.splitlines()))

        response = self._prepare(contract, text)

        self.assertEqual(response.status_code, 200)
        self.assertIn("prepared_terms", response.data)
        self.assertIn("created_records", response.data)
        self.assertNotIn("extraction_run", response.data)
        run = ContractExtractionRun.objects.get(contract=contract, stage=ContractExtractionRun.STAGE_PREPARE)
        candidates = {candidate.title: candidate for candidate in ContractExtractionCandidate.objects.filter(run=run)}
        self.assertEqual(len(candidates), 6)

        homepage = candidates["Deliver homepage mockup"]
        self.assertEqual(homepage.candidate_type, ContractExtractionCandidate.TYPE_SERVICE_WORK)
        self.assertEqual(homepage.responsible_party, "Contractor / Maria Jean")
        self.assertEqual(homepage.beneficiary_party, "Client / Alcide")
        self.assertEqual(str(homepage.due_date), "2026-08-10")

        full_site = candidates["Deliver full website"]
        self.assertEqual(full_site.candidate_type, ContractExtractionCandidate.TYPE_SERVICE_WORK)
        self.assertEqual(str(full_site.due_date), "2026-09-01")

        payment_500 = candidates["Pay $500 for homepage mockup"]
        self.assertEqual(payment_500.candidate_type, ContractExtractionCandidate.TYPE_PAYMENT)
        self.assertEqual(payment_500.responsible_party, "Client / Alcide")
        self.assertEqual(payment_500.beneficiary_party, "Contractor / Maria Jean")
        self.assertEqual(payment_500.amount, 500)
        self.assertIsNone(payment_500.due_date)
        self.assertIn("homepage mockup", payment_500.metadata["due_trigger"])

        payment_1000 = candidates["Pay $1,000 for full website"]
        self.assertEqual(payment_1000.candidate_type, ContractExtractionCandidate.TYPE_PAYMENT)
        self.assertEqual(payment_1000.amount, 1000)
        self.assertIsNone(payment_1000.due_date)
        self.assertIn("full website", payment_1000.metadata["due_trigger"])

        bug_fix = candidates["Fix reasonable bugs after delivery"]
        self.assertEqual(bug_fix.candidate_type, ContractExtractionCandidate.TYPE_SERVICE_WORK)
        self.assertEqual(bug_fix.responsible_party, "Contractor / Maria Jean")
        self.assertEqual(bug_fix.beneficiary_party, "Client / Alcide")
        self.assertIsNone(bug_fix.due_date)
        self.assertEqual(bug_fix.metadata["relative_due"], {
            "amount": 7,
            "unit": "days",
            "direction": "after",
            "event": "delivery",
        })

        review = candidates["Review each delivery"]
        self.assertEqual(review.candidate_type, ContractExtractionCandidate.TYPE_RESPONSIBILITY)
        self.assertEqual(review.responsible_party, "Client / Alcide")
        self.assertEqual(review.beneficiary_party, "Contractor / Maria Jean")
        self.assertIsNone(review.due_date)
        self.assertEqual(review.metadata["relative_due"], {
            "amount": 5,
            "unit": "days",
            "direction": "after",
            "event": "delivery",
        })

        for candidate in candidates.values():
            self.assertEqual(candidate.metadata["extraction_level"], "sentence")
            self.assertTrue(candidate.source_clause_text)
            self.assertIn("sentence", candidate.raw_payload)

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

class ContractReturnToDraftTests(TestCase):
    def setUp(self):
        self.initiator = make_user("return_owner", "return-owner@example.com")
        self.counterparty = make_user("return_counterparty", "return-counterparty@example.com")
        make_subscription(self.initiator)
        self.client = authed_client(self.initiator)

    def _make_prepared_contract(self, **overrides):
        defaults = {
            "initiator": self.initiator,
            "counterparty_name": "Counter Party",
            "counterparty_email": self.counterparty.email,
            "title": "Prepared Contract",
            "status": "draft",
            "state": "prepared",
            "structure_type": "ONE_TIME",
        }
        defaults.update(overrides)
        contract = Contract.objects.create(**defaults)
        version = ContractVersion.objects.create(
            contract=contract,
            version_number=1,
            created_by=self.initiator,
            content_snapshot=json.dumps({
                "source": "contract_prepare",
                "editor_html": "<p>Prepared body</p>",
                "prepared_terms": {"payment_terms": []},
            }),
            status="draft",
        )
        return contract, version

    def test_return_to_draft_unlocks_prepared_contract_without_changing_content(self):
        contract, version = self._make_prepared_contract()
        original_snapshot = version.content_snapshot

        response = self.client.post(f"/api/contracts/{contract.id}/return-to-draft/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        contract.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(contract.state, "drafting")
        self.assertEqual(contract.status, "draft")
        self.assertEqual(version.status, "draft")
        self.assertEqual(version.content_snapshot, original_snapshot)
        self.assertEqual(contract.versions.count(), 1)
        self.assertEqual(response.data["editor_url"], f"/contracts/create?id={contract.id}")

    def test_return_to_draft_allows_draft_placeholder_exchange(self):
        contract, version = self._make_prepared_contract()
        AgreementExchange.objects.create(
            contract=contract,
            current_contract_version=version,
            source_contract_version=version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
        )

        response = self.client.post(f"/api/contracts/{contract.id}/return-to-draft/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        contract.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(contract.state, "drafting")
        self.assertEqual(contract.status, "draft")
        self.assertEqual(version.status, "draft")
        self.assertEqual(contract.agreement_exchanges.count(), 1)
        self.assertEqual(contract.agreement_exchanges.first().status, AgreementExchange.STATUS_DRAFT)

    def test_return_to_draft_rejects_after_exchange_has_started(self):
        contract, version = self._make_prepared_contract()
        exchange = AgreementExchange.objects.create(
            contract=contract,
            current_contract_version=version,
            source_contract_version=version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
        )

        response = self.client.post(f"/api/contracts/{contract.id}/return-to-draft/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("initial version has been sent", response.data["error"])
        contract.refresh_from_db()
        self.assertEqual(contract.state, "prepared")
        self.assertEqual(AgreementExchange.objects.get(pk=exchange.pk).status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)

    def test_return_to_draft_rejects_terminal_contract_statuses(self):
        for contract_status in ["sent", "signed", "active", "completed"]:
            with self.subTest(contract_status=contract_status):
                contract, _version = self._make_prepared_contract(status=contract_status, state=contract_status)

                response = self.client.post(f"/api/contracts/{contract.id}/return-to-draft/", {}, format="json")

                self.assertEqual(response.status_code, 400)
                contract.refresh_from_db()
                self.assertEqual(contract.status, contract_status)
                self.assertEqual(contract.state, contract_status)

    def test_return_to_draft_rejects_counterparty(self):
        contract, _version = self._make_prepared_contract()
        counterparty_client = authed_client(self.counterparty)

        response = counterparty_client.post(f"/api/contracts/{contract.id}/return-to-draft/", {}, format="json")

        self.assertEqual(response.status_code, 403)
        contract.refresh_from_db()
        self.assertEqual(contract.state, "prepared")

