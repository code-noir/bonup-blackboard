import json
from datetime import datetime, timezone as dt_timezone

from django.test import TestCase

from backend.agreement_exchange.models import AgreementExchange
from backend.agreement_exchange.services import sign_exchange
from backend.api.contracts.services.visibility_service import resolve_contract_dashboard_status
from backend.api.tests.helpers import authed_client, make_contract, make_user, make_version
from backend.contracts.models import LifecycleAgreement, LifecycleEvent, LifecycleItem
from backend.notifications.models import Notification
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
        self.contract.title = "Signed Timeline Contract"
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
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertNotEqual(self.contract.status, "active")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="timeline_setup_started").count(), 1)

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
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=first, event_type="timeline_setup_started").count(), 1)

    def test_lifecycle_endpoint_returns_contract_scoped_data(self):
        response = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["contract"]["id"], str(self.contract.id))
        self.assertEqual(response.data["contract"]["title"], "Signed Timeline Contract")
        self.assertEqual(response.data["signed_version"]["id"], str(self.version.id))
        self.assertEqual(response.data["signed_version"]["label"], "v1")
        self.assertEqual(response.data["lifecycle_agreement"]["status"], "setup")
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertNotEqual(self.contract.status, "active")
        self.assertEqual(set(response.data["items"].keys()), {"obligations", "payments", "deadlines", "services", "notices", "documents", "risks", "changes", "notes"})
        self.assertIn("views", response.data)
        self.assertIn("upcoming", response.data["views"])
        self.assertIn("changes_add_ons", response.data["views"])
        self.assertEqual(response.data["events"][0]["event_type"], "timeline_setup_started")

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
        self.assertEqual(dashboard_contract["primary_action_label"], "Open Agreement Timeline")
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


    def test_creating_timeline_item_does_not_activate_contract(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        response = self.initiator_client.post(
            f"/api/lifecycle/{agreement.id}/items/",
            {"item_type": "payment", "title": "First payment", "amount": "100.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="item_created").count(), 1)

    def test_first_performance_action_notifies_counterparty_and_activates_contract(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Initial payment",
            amount="125.00",
            created_by=self.initiator,
        )

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_paid"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_COMPLETED)
        self.assertEqual(self.contract.status, "active")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_ACTIVE)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="payment_marked_paid").count(), 1)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="contract_activated").count(), 1)
        notification = Notification.objects.get(user=self.counterparty, notification_type="agreement_timeline")
        self.assertEqual(notification.title, "Payment marked paid")
        self.assertIn("Signed Timeline Contract", notification.message)
        self.assertIn("Initial payment", notification.message)
        self.assertEqual(notification.metadata["redirect_url"], f"/lifecycle?contract={self.contract.id}")

    def test_active_transition_is_idempotent(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title="Provide keys",
            created_by=self.initiator,
        )

        first = self.initiator_client.post(f"/api/lifecycle/items/{item.id}/actions/", {"action": "mark_completed"}, format="json")
        second = self.initiator_client.post(f"/api/lifecycle/items/{item.id}/actions/", {"action": "mark_completed"}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="contract_activated").count(), 1)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "active")

    def test_change_order_proposal_and_acceptance_create_events_and_notifications(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_NOTE,
            title="Extend service area",
            created_by=self.initiator,
        )

        proposed = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "propose_change_order", "message": "Add the back patio."},
            format="json",
        )
        accepted = self.counterparty_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "accept_change_order"},
            format="json",
        )

        self.assertEqual(proposed.status_code, 200)
        self.assertEqual(accepted.status_code, 200)
        item.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(item.item_type, LifecycleItem.TYPE_CHANGE_ORDER)
        self.assertEqual(item.status, LifecycleItem.STATUS_CONFIRMED)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="change_order_proposed").count(), 1)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="change_order_accepted").count(), 1)
        self.assertEqual(Notification.objects.filter(notification_type="agreement_timeline").count(), 2)

    def test_add_on_proposal_creates_timeline_notification_without_activation(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_NOTE,
            title="Weekly cleanup add-on",
            created_by=self.initiator,
        )

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "propose_add_on", "message": "Add weekly cleanup."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(item.item_type, LifecycleItem.TYPE_ADD_ON)
        self.assertEqual(item.status, LifecycleItem.STATUS_PROPOSED)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        notification = Notification.objects.get(notification_type="agreement_timeline")
        self.assertIn("Weekly cleanup add-on", notification.message)

    def test_timeline_endpoint_returns_grouped_views(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_DUE_DATE,
            title="Notice deadline",
            due_date=datetime(2030, 1, 1, 12, 0, tzinfo=dt_timezone.utc),
            created_by=self.initiator,
        )
        LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_CHANGE_ORDER,
            title="Scope change",
            status=LifecycleItem.STATUS_PROPOSED,
            created_by=self.initiator,
        )

        response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn("views", response.data)
        self.assertEqual(response.data["counts"]["deadlines"], 1)
        self.assertEqual(response.data["counts"]["changes"], 1)
        self.assertEqual(response.data["views"]["due_dates"][0]["title"], "Notice deadline")
        self.assertEqual(response.data["views"]["changes_add_ons"][0]["title"], "Scope change")
        self.assertEqual(response.data["lifecycle_agreement"]["status"], "setup")
