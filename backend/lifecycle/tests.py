import json

from django.test import TestCase

from backend.agreement_exchange.models import AgreementExchange
from backend.agreement_exchange.services import sign_exchange
from backend.api.contracts.services.visibility_service import resolve_contract_dashboard_status
from backend.api.tests.helpers import authed_client, make_contract, make_user, make_version
from backend.contracts.models import LifecycleAgreement, LifecycleEvent
from backend.lifecycle.services import LifecycleNotReadyError, get_or_create_lifecycle_for_signed_contract


class LifecycleFoundationTests(TestCase):
    def setUp(self):
        self.initiator = make_user("life_initiator", "life-initiator@example.com")
        self.counterparty = make_user("life_counterparty", "life-counterparty@example.com")
        self.stranger = make_user("life_stranger", "life-stranger@example.com")
        self.initiator_client = authed_client(self.initiator)
        self.counterparty_client = authed_client(self.counterparty)
        self.stranger_client = authed_client(self.stranger)
        self.contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        self.contract.title = "Signed Lifecycle Contract"
        self.contract.save(update_fields=["title"])
        self.snapshot = json.dumps({"editor_html": "<p>Signed terms.</p>", "sections": []})
        self.version = make_version(self.contract, self.initiator, content_snapshot=self.snapshot, status="signed")
        self.contract.status = "signed"
        self.contract.save(update_fields=["status"])

    def test_signed_contract_can_create_lifecycle_agreement(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        self.assertEqual(agreement.contract, self.contract)
        self.assertEqual(agreement.signed_version, self.version)
        self.assertEqual(agreement.owner, self.initiator)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_ACTIVE)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="lifecycle_started").count(), 1)

    def test_signed_version_can_create_lifecycle_even_if_contract_status_is_not_active(self):
        self.contract.status = "draft"
        self.contract.save(update_fields=["status"])

        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        self.assertEqual(agreement.contract, self.contract)
        self.assertEqual(agreement.signed_version, self.version)

    def test_unsigned_prepared_contract_cannot_create_lifecycle_agreement(self):
        unsigned_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        make_version(unsigned_contract, self.initiator, content_snapshot="Draft", status="sent")

        with self.assertRaises(LifecycleNotReadyError):
            get_or_create_lifecycle_for_signed_contract(unsigned_contract, self.initiator)

        self.assertFalse(LifecycleAgreement.objects.filter(contract=unsigned_contract).exists())

    def test_get_or_create_lifecycle_is_idempotent(self):
        first = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        second = get_or_create_lifecycle_for_signed_contract(self.contract, self.counterparty)

        self.assertEqual(first.id, second.id)
        self.assertEqual(LifecycleAgreement.objects.filter(contract=self.contract).count(), 1)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=first, event_type="lifecycle_started").count(), 1)

    def test_lifecycle_endpoint_returns_contract_scoped_data(self):
        response = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["contract"]["id"], str(self.contract.id))
        self.assertEqual(response.data["contract"]["title"], "Signed Lifecycle Contract")
        self.assertEqual(response.data["signed_version"]["id"], str(self.version.id))
        self.assertEqual(response.data["signed_version"]["label"], "v1")
        self.assertEqual(response.data["lifecycle_agreement"]["status"], "active")
        self.assertEqual(set(response.data["items"].keys()), {"obligations", "payments", "deadlines", "services", "risks", "notes"})
        self.assertEqual(response.data["events"][0]["event_type"], "lifecycle_started")

    def test_lifecycle_endpoint_rejects_unauthorized_user(self):
        response = self.stranger_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "You are not a party to this contract.")

    def test_lifecycle_endpoint_rejects_unsigned_contract(self):
        unsigned_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        make_version(unsigned_contract, self.initiator, content_snapshot="Draft", status="sent")

        response = self.initiator_client.get(f"/api/lifecycle/?contract={unsigned_contract.id}")

        self.assertEqual(response.status_code, 409)
        self.assertIn("signed version", response.data["detail"])

    def test_dashboard_open_lifecycle_route_can_load_lifecycle_data(self):
        dashboard_response = self.counterparty_client.get("/api/contracts/")

        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_contract = next(item for item in dashboard_response.data if item["id"] == str(self.contract.id))
        self.assertEqual(dashboard_contract["display_status"], "signed")
        self.assertTrue(dashboard_contract["lifecycle_ready"])
        self.assertEqual(dashboard_contract["primary_action"], "open_lifecycle")
        self.assertEqual(dashboard_contract["primary_action_label"], "Open Lifecycle")
        self.assertEqual(dashboard_contract["primary_action_url"], f"/lifecycle?contract={self.contract.id}")

        response = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["contract"]["id"], str(self.contract.id))
        self.assertEqual(response.data["signed_version"]["id"], str(self.version.id))

    def test_contract_detail_metadata_shows_signed_for_signed_contract(self):
        response = self.counterparty_client.get(f"/api/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "signed")
        self.assertEqual(response.data["display_status"], "signed")
        self.assertEqual(response.data["display_status_label"], "Signed")

    def test_newly_created_draft_contract_returns_drafting_metadata(self):
        draft_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        draft_contract.status = "draft"
        draft_contract.state = "created"
        draft_contract.save(update_fields=["status", "state"])

        dashboard_status = resolve_contract_dashboard_status(draft_contract)

        self.assertEqual(dashboard_status["display_status"], "drafting")
        self.assertEqual(dashboard_status["display_status_label"], "Drafting")
        self.assertFalse(dashboard_status["lifecycle_ready"])
        self.assertEqual(dashboard_status["primary_action"], "continue_draft")
        self.assertEqual(dashboard_status["primary_action_label"], "Continue Draft")
        self.assertEqual(dashboard_status["primary_action_url"], f"/contracts/create?id={draft_contract.id}")

    def test_drafting_contract_detail_metadata_does_not_show_prepared(self):
        draft_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        draft_contract.status = "draft"
        draft_contract.state = "drafting"
        draft_contract.save(update_fields=["status", "state"])

        response = self.initiator_client.get(f"/api/contracts/{draft_contract.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["display_status"], "drafting")
        self.assertEqual(response.data["display_status_label"], "Drafting")
        self.assertNotEqual(response.data["display_status_label"], "Prepared")

    def test_prepared_contract_returns_prepared_metadata(self):
        prepared_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        prepared_contract.status = "draft"
        prepared_contract.state = "prepared"
        prepared_contract.save(update_fields=["status", "state"])

        dashboard_status = resolve_contract_dashboard_status(prepared_contract)

        self.assertEqual(dashboard_status["display_status"], "prepared")
        self.assertEqual(dashboard_status["display_status_label"], "Prepared")
        self.assertFalse(dashboard_status["lifecycle_ready"])
        self.assertEqual(dashboard_status["primary_action"], "open_negotiation")
        self.assertEqual(dashboard_status["primary_action_label"], "Open Negotiation")
        self.assertEqual(dashboard_status["primary_action_url"], f"/negotiation/{prepared_contract.id}")

    def test_signed_exchange_without_signed_version_shows_signed_but_no_lifecycle(self):
        unsigned_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        unsigned_version = make_version(unsigned_contract, self.initiator, content_snapshot="Draft", status="sent")
        AgreementExchange.objects.create(
            contract=unsigned_contract,
            current_contract_version=unsigned_version,
            source_contract_version=unsigned_version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_SIGNED,
            current_actor=AgreementExchange.ACTOR_NONE,
        )

        dashboard_status = resolve_contract_dashboard_status(unsigned_contract)
        response = self.counterparty_client.get(f"/api/lifecycle/?contract={unsigned_contract.id}")

        self.assertEqual(dashboard_status["display_status"], "signed")
        self.assertEqual(dashboard_status["display_status_label"], "Signed")
        self.assertFalse(dashboard_status["lifecycle_ready"])
        self.assertEqual(dashboard_status["primary_action"], "open_contract")
        self.assertEqual(dashboard_status["primary_action_label"], "Open")
        self.assertEqual(dashboard_status["primary_action_url"], f"/contracts/{unsigned_contract.id}/view")
        self.assertEqual(response.status_code, 409)

    def test_under_negotiation_and_prepared_dashboard_statuses_do_not_show_lifecycle(self):
        negotiating_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        negotiating_version = make_version(negotiating_contract, self.initiator, content_snapshot="Draft", status="sent")
        exchange = AgreementExchange.objects.create(
            contract=negotiating_contract,
            current_contract_version=negotiating_version,
            source_contract_version=negotiating_version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
            current_actor=AgreementExchange.ACTOR_COUNTERPARTY,
        )
        prepared_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        prepared_contract.status = "draft"
        prepared_contract.state = "prepared"
        prepared_contract.save(update_fields=["status", "state"])

        negotiating_status = resolve_contract_dashboard_status(negotiating_contract)
        prepared_status = resolve_contract_dashboard_status(prepared_contract)

        self.assertEqual(negotiating_status["display_status"], "under_negotiation")
        self.assertEqual(negotiating_status["display_status_label"], "Under Negotiation")
        self.assertFalse(negotiating_status["lifecycle_ready"])
        self.assertEqual(negotiating_status["primary_action"], "open_negotiation")
        self.assertEqual(negotiating_status["primary_action_label"], "Open Negotiation")
        self.assertEqual(negotiating_status["active_exchange_id"], str(exchange.id))
        self.assertEqual(prepared_status["display_status"], "prepared")
        self.assertEqual(prepared_status["display_status_label"], "Prepared")
        self.assertFalse(prepared_status["lifecycle_ready"])
        self.assertNotEqual(prepared_status["primary_action"], "open_lifecycle")

    def test_agreement_exchange_signed_flow_is_not_mutated_by_lifecycle_creation(self):
        contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        version = make_version(contract, self.initiator, content_snapshot=self.snapshot, status="sent")
        exchange = AgreementExchange.objects.create(
            contract=contract,
            current_contract_version=version,
            source_contract_version=version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
            current_actor=AgreementExchange.ACTOR_COUNTERPARTY,
        )
        sign_exchange(exchange_id=exchange.id, user=self.counterparty, typed_name="Counter Party")
        exchange.refresh_from_db()
        version.refresh_from_db()
        contract.refresh_from_db()

        before_status = exchange.status
        before_actor = exchange.current_actor
        before_version_id = exchange.current_contract_version_id
        agreement = get_or_create_lifecycle_for_signed_contract(contract, self.counterparty)
        exchange.refresh_from_db()

        self.assertEqual(exchange.status, before_status)
        self.assertEqual(exchange.current_actor, before_actor)
        self.assertEqual(exchange.current_contract_version_id, before_version_id)
        self.assertEqual(version.status, "signed")
        self.assertEqual(contract.status, "signed")
        self.assertNotEqual(contract.status, "active")
        self.assertEqual(agreement.source_exchange_id, exchange.id)
