import json
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from backend.agreement_exchange.models import AgreementExchange
from backend.agreement_exchange.services import sign_exchange
from backend.api.contracts.services.visibility_service import resolve_contract_dashboard_status
from backend.api.tests.helpers import authed_client, make_contract, make_user, make_version
from backend.contracts.models import ContractObligation, ContractServiceObligation, LifecycleAgreement, LifecycleChangeProposal, LifecycleChangeProposalMessage, LifecycleEvent, LifecycleItem, LifecycleItemAttachment, LifecycleItemMessage, LifecycleItemResponse, LifecycleItemUserState
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

    def test_ready_for_performance_marks_lifecycle_without_activation(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        response = self.initiator_client.post(f"/api/lifecycle/{agreement.id}/ready-for-performance/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertTrue(agreement.performance_ready)
        self.assertEqual(agreement.performance_ready_by, self.initiator)
        self.assertIsNotNone(agreement.performance_ready_at)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(self.contract.status, "signed")
        self.assertNotEqual(self.contract.status, "active")
        self.assertTrue(response.data["lifecycle_agreement"]["performance_ready"])

    def test_ready_for_performance_is_idempotent(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        first = self.initiator_client.post(f"/api/lifecycle/{agreement.id}/ready-for-performance/", {}, format="json")
        agreement.refresh_from_db()
        first_ready_at = agreement.performance_ready_at
        second = self.counterparty_client.post(f"/api/lifecycle/{agreement.id}/ready-for-performance/", {}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        agreement.refresh_from_db()
        self.assertEqual(agreement.performance_ready_at, first_ready_at)
        self.assertEqual(agreement.performance_ready_by, self.initiator)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")

    def test_ready_for_performance_rejects_unauthorized_user(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        response = self.stranger_client.post(f"/api/lifecycle/{agreement.id}/ready-for-performance/", {}, format="json")

        self.assertEqual(response.status_code, 403)
        agreement.refresh_from_db()
        self.assertFalse(agreement.performance_ready)

    def test_agreement_performance_list_only_returns_ready_party_agreements(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        other_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        make_version(other_contract, self.initiator, content_snapshot=self.snapshot, status="signed")
        other_contract.status = "signed"
        other_contract.save(update_fields=["status"])
        get_or_create_lifecycle_for_signed_contract(other_contract, self.initiator)

        before = self.counterparty_client.get("/api/lifecycle/performance/")
        self.initiator_client.post(f"/api/lifecycle/{agreement.id}/ready-for-performance/", {}, format="json")
        after = self.counterparty_client.get("/api/lifecycle/performance/")
        stranger = self.stranger_client.get("/api/lifecycle/performance/")

        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.data["results"], [])
        self.assertEqual(after.status_code, 200)
        self.assertEqual(len(after.data["results"]), 1)
        self.assertEqual(after.data["results"][0]["id"], str(agreement.id))
        self.assertEqual(after.data["results"][0]["contract"]["title"], "Signed Timeline Contract")
        self.assertEqual(after.data["results"][0]["status"], "Waiting for first performed obligation")
        self.assertEqual(stranger.status_code, 200)
        self.assertEqual(stranger.data["results"], [])

    def test_due_personal_reminder_command_notifies_owner_only(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Payment installment 1",
            amount="125.00",
            created_by=self.initiator,
        )
        state = LifecycleItemUserState.objects.create(
            lifecycle_item=item,
            user=self.initiator,
            reminder_at=timezone.now() - timedelta(minutes=5),
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()

        out = StringIO()
        call_command("send_due_timeline_reminders", stdout=out)

        self.assertIn("Sent 1", out.getvalue())
        notification = Notification.objects.get(user=self.initiator, metadata__source="agreement_performance_reminder")
        self.assertEqual(notification.notification_type, "agreement_timeline")
        self.assertEqual(notification.title, "Reminder: Payment installment 1")
        self.assertIn("Payment installment 1", notification.message)
        self.assertIn("Signed Timeline Contract", notification.message)
        self.assertEqual(notification.related_contract, self.contract)
        self.assertEqual(notification.metadata["lifecycle_item_id"], str(item.id))
        self.assertEqual(notification.metadata["lifecycle_agreement_id"], str(agreement.id))
        self.assertEqual(notification.metadata["contract_id"], str(self.contract.id))
        self.assertEqual(notification.metadata["source"], "agreement_performance_reminder")
        self.assertEqual(notification.metadata["redirect_url"], "/agreement-performance")
        self.assertEqual(Notification.objects.filter(user=self.counterparty, metadata__source="agreement_performance_reminder").count(), 0)
        state.refresh_from_db()
        self.assertEqual(state.metadata["reminder_delivery"]["sent_for"], state.reminder_at.isoformat())
        self.assertEqual(state.metadata["reminder_delivery"]["notification_id"], str(notification.id))
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events)
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)

    def test_due_personal_reminder_command_is_idempotent_for_same_reminder_time(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Payment installment 1",
            created_by=self.initiator,
        )
        LifecycleItemUserState.objects.create(
            lifecycle_item=item,
            user=self.initiator,
            reminder_at=timezone.now() - timedelta(minutes=5),
        )

        call_command("send_due_timeline_reminders", stdout=StringIO())
        call_command("send_due_timeline_reminders", stdout=StringIO())

        self.assertEqual(Notification.objects.filter(user=self.initiator, metadata__source="agreement_performance_reminder").count(), 1)

    def test_changed_due_personal_reminder_can_send_again_for_new_time(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Payment installment 1",
            created_by=self.initiator,
        )
        state = LifecycleItemUserState.objects.create(
            lifecycle_item=item,
            user=self.initiator,
            reminder_at=timezone.now() - timedelta(minutes=10),
        )
        call_command("send_due_timeline_reminders", stdout=StringIO())

        state.refresh_from_db()
        state.reminder_at = timezone.now() - timedelta(minutes=1)
        state.save(update_fields=["reminder_at", "updated_at"])
        call_command("send_due_timeline_reminders", stdout=StringIO())

        self.assertEqual(Notification.objects.filter(user=self.initiator, metadata__source="agreement_performance_reminder").count(), 2)
        state.refresh_from_db()
        self.assertEqual(state.metadata["reminder_delivery"]["sent_for"], state.reminder_at.isoformat())

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

    def test_first_performance_action_notifies_counterparty_and_starts_performance(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Initial payment",
            amount="125.00",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_paid", "file": SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 proof", content_type="application/pdf")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_COMPLETED)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_ACTIVE)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="payment_marked_paid").count(), 1)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="contract_activated").count(), 0)
        event = LifecycleEvent.objects.get(lifecycle_agreement=agreement, event_type="payment_marked_paid")
        self.assertTrue(event.metadata["performance_started"])
        self.assertEqual(event.metadata["result_status"], LifecycleItem.STATUS_COMPLETED)
        notification = Notification.objects.get(user=self.counterparty, notification_type="agreement_timeline")
        self.assertEqual(notification.title, "Paid")
        self.assertIn("Signed Timeline Contract", notification.message)
        self.assertIn("Initial payment", notification.message)
        self.assertEqual(notification.metadata["source"], "agreement_performance_action")
        self.assertEqual(notification.metadata["action"], "mark_paid")
        self.assertEqual(notification.metadata["contract_id"], str(self.contract.id))
        self.assertEqual(notification.metadata["lifecycle_agreement_id"], str(agreement.id))
        self.assertEqual(notification.metadata["lifecycle_item_id"], str(item.id))
        self.assertEqual(notification.metadata["lifecycle_event_id"], str(event.id))
        self.assertTrue(notification.metadata["attachment_id"])
        self.assertEqual(event.metadata["attachment_id"], notification.metadata["attachment_id"])
        self.assertEqual(event.metadata["result_label"], "Paid")
        self.assertEqual(notification.metadata["redirect_url"], "/agreement-performance")
        self.assertEqual(Notification.objects.filter(user=self.initiator, metadata__source="agreement_performance_action").count(), 0)

    def test_performance_action_is_idempotent(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title="Provide keys",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )

        first = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_completed", "file": SimpleUploadedFile("proof.pdf", b"%PDF-1.4 proof", content_type="application/pdf")},
            format="multipart",
        )
        second = self.initiator_client.post(f"/api/lifecycle/items/{item.id}/actions/", {"action": "mark_completed"}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="item_completed").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.counterparty, metadata__source="agreement_performance_action").count(), 1)
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_ACTIVE)
        self.assertEqual(self.contract.status, "signed")

    def test_performance_action_requires_responsible_party(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Initial payment",
            amount="125.00",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )

        response = self.counterparty_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_paid"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        item.refresh_from_db()
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="payment_marked_paid").count(), 0)
        self.assertEqual(Notification.objects.filter(metadata__source="agreement_performance_action").count(), 0)

    def test_work_performed_uses_agreement_performance_notification_action(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party="Lender",
            created_by=self.initiator,
        )

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_work_performed", "file": SimpleUploadedFile("deposit.pdf", b"%PDF-1.4 proof", content_type="application/pdf")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_COMPLETED)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_ACTIVE)
        self.assertEqual(self.contract.status, "signed")
        event = LifecycleEvent.objects.get(lifecycle_agreement=agreement, event_type="work_marked_performed")
        notification = Notification.objects.get(user=self.counterparty, metadata__source="agreement_performance_action")
        self.assertEqual(notification.title, "Performed")
        self.assertEqual(notification.metadata["action"], "mark_performed")
        self.assertEqual(notification.metadata["api_action"], "mark_work_performed")
        self.assertEqual(notification.metadata["lifecycle_event_id"], str(event.id))
        self.assertTrue(notification.metadata["attachment_id"])
        self.assertEqual(event.metadata["attachment_id"], notification.metadata["attachment_id"])
        self.assertEqual(event.metadata["result_label"], "Performed")

    def test_performance_action_requires_proof_file(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Initial payment",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_paid"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Upload proof or receipt", response.data["detail"])
        item.refresh_from_db()
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="payment_marked_paid").count(), 0)
        self.assertEqual(Notification.objects.filter(metadata__source="agreement_performance_action").count(), 0)

    def test_performance_action_rejects_unsupported_proof_file(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Initial payment",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_paid", "file": SimpleUploadedFile("proof.exe", b"binary", content_type="application/x-msdownload")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported proof file type", response.data["detail"])
        item.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)

    def test_performance_action_rejects_oversized_video_proof(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Install equipment",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )
        upload = SimpleUploadedFile("proof.mp4", b"small", content_type="video/mp4")
        upload.size = 100 * 1024 * 1024 + 1

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/actions/",
            {"action": "mark_work_performed", "file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Maximum size is 100 MB", response.data["detail"])
        item.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)

    def test_lifecycle_item_proof_upload_is_shared_and_notifies_counterparty(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Payment installment 1",
            amount="125.00",
            responsible_party=str(self.counterparty.id),
            created_by=self.initiator,
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()
        upload = SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 paid by bank transfer", content_type="application/pdf")

        response = self.counterparty_client.post(
            f"/api/lifecycle/items/{item.id}/attachments/",
            {"file": upload, "note": "Bank receipt"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        attachment = LifecycleItemAttachment.objects.get(pk=response.data["id"])
        self.assertEqual(attachment.lifecycle_item, item)
        self.assertEqual(attachment.lifecycle_agreement, agreement)
        self.assertEqual(attachment.contract, self.contract)
        self.assertEqual(attachment.uploaded_by, self.counterparty)
        self.assertEqual(attachment.original_filename, "receipt.pdf")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(attachment.file_size, len(b"%PDF-1.4 paid by bank transfer"))
        self.assertEqual(attachment.note, "Bank receipt")
        self.assertTrue(response.data["file_url"])

        event = LifecycleEvent.objects.get(lifecycle_agreement=agreement, event_type="proof_uploaded")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events + 1)
        self.assertEqual(event.metadata["source"], "agreement_performance_proof")
        self.assertEqual(event.metadata["action"], "upload_proof")
        self.assertEqual(event.metadata["contract_id"], str(self.contract.id))
        self.assertEqual(event.metadata["lifecycle_agreement_id"], str(agreement.id))
        self.assertEqual(event.metadata["lifecycle_item_id"], str(item.id))
        self.assertEqual(event.metadata["attachment_id"], str(attachment.id))

        notification = Notification.objects.get(user=self.initiator, metadata__source="agreement_performance_proof")
        self.assertEqual(notification.title, "Proof uploaded")
        self.assertIn("Payment installment 1", notification.message)
        self.assertEqual(notification.related_contract, self.contract)
        self.assertEqual(notification.metadata["action"], "upload_proof")
        self.assertEqual(notification.metadata["attachment_id"], str(attachment.id))
        self.assertEqual(notification.metadata["lifecycle_event_id"], str(event.id))
        self.assertEqual(notification.metadata["redirect_url"], "/agreement-performance")
        self.assertEqual(Notification.objects.filter(user=self.counterparty, metadata__source="agreement_performance_proof").count(), 0)

        item.refresh_from_db()
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(self.contract.status, "signed")

    def test_lifecycle_item_proof_attachment_visible_to_parties_only(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )
        upload = SimpleUploadedFile("deposit.pdf", b"%PDF-1.4 deposit confirmation", content_type="application/pdf")
        created = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/attachments/",
            {"file": upload},
            format="multipart",
        )

        initiator_response = self.initiator_client.get(f"/api/lifecycle/items/{item.id}/attachments/")
        counterparty_response = self.counterparty_client.get(f"/api/lifecycle/items/{item.id}/attachments/")
        stranger_response = self.stranger_client.get(f"/api/lifecycle/items/{item.id}/attachments/")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(initiator_response.status_code, 200)
        self.assertEqual(counterparty_response.status_code, 200)
        self.assertEqual(stranger_response.status_code, 403)
        self.assertEqual(len(initiator_response.data["results"]), 1)
        self.assertEqual(len(counterparty_response.data["results"]), 1)
        self.assertEqual(counterparty_response.data["results"][0]["id"], created.data["id"])

    def test_lifecycle_item_proof_upload_requires_responsible_party(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )

        response = self.counterparty_client.post(
            f"/api/lifecycle/items/{item.id}/attachments/",
            {"file": SimpleUploadedFile("deposit.pdf", b"%PDF-1.4 deposit confirmation", content_type="application/pdf")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("responsible party", response.data["detail"])
        self.assertEqual(LifecycleItemAttachment.objects.filter(lifecycle_item=item).count(), 0)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="proof_uploaded").count(), 0)
        self.assertEqual(Notification.objects.filter(metadata__source="agreement_performance_proof").count(), 0)

    def test_lifecycle_item_payload_exposes_proof_permissions_by_party(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )
        self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/attachments/",
            {"file": SimpleUploadedFile("deposit.pdf", b"%PDF-1.4 deposit confirmation", content_type="application/pdf")},
            format="multipart",
        )

        initiator_response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        counterparty_response = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        initiator_item = next(value for value in initiator_response.data["views"]["work_services"] if value["id"] == str(item.id))
        counterparty_item = next(value for value in counterparty_response.data["views"]["work_services"] if value["id"] == str(item.id))
        self.assertTrue(initiator_item["can_upload_proof"])
        self.assertFalse(initiator_item["can_respond_to_proof"])
        self.assertFalse(counterparty_item["can_upload_proof"])
        self.assertTrue(counterparty_item["can_respond_to_proof"])

    def test_counterparty_response_creates_shared_event_and_notifies_responsible_party(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )
        self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/attachments/",
            {"file": SimpleUploadedFile("deposit.pdf", b"%PDF-1.4 deposit confirmation", content_type="application/pdf")},
            format="multipart",
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()

        response = self.counterparty_client.post(
            f"/api/lifecycle/items/{item.id}/responses/",
            {"response": "received", "note": "Funds arrived."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item_response = LifecycleItemResponse.objects.get(lifecycle_item=item, responder=self.counterparty)
        self.assertEqual(item_response.response, LifecycleItemResponse.RESPONSE_RECEIVED)
        self.assertEqual(item_response.note, "Funds arrived.")
        event = LifecycleEvent.objects.get(lifecycle_agreement=agreement, event_type="proof_response")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events + 1)
        self.assertEqual(event.metadata["source"], "agreement_performance_response")
        self.assertEqual(event.metadata["action"], "received")
        self.assertEqual(event.metadata["lifecycle_item_id"], str(item.id))
        self.assertEqual(event.metadata["response_id"], str(item_response.id))
        notification = Notification.objects.get(user=self.initiator, metadata__source="agreement_performance_response")
        self.assertEqual(notification.metadata["action"], "received")
        self.assertEqual(notification.metadata["lifecycle_item_id"], str(item.id))
        self.assertEqual(notification.metadata["lifecycle_event_id"], str(event.id))
        self.assertEqual(notification.metadata["redirect_url"], "/agreement-performance")
        self.assertEqual(Notification.objects.filter(user=self.counterparty, metadata__source="agreement_performance_response").count(), 0)
        item.refresh_from_db()
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(self.contract.status, "signed")

    def test_responsible_party_and_stranger_cannot_submit_counterparty_response(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )
        self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/attachments/",
            {"file": SimpleUploadedFile("deposit.pdf", b"%PDF-1.4 deposit confirmation", content_type="application/pdf")},
            format="multipart",
        )

        responsible_response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/responses/",
            {"response": "received"},
            format="json",
        )
        stranger_response = self.stranger_client.post(
            f"/api/lifecycle/items/{item.id}/responses/",
            {"response": "received"},
            format="json",
        )

        self.assertEqual(responsible_response.status_code, 403)
        self.assertEqual(stranger_response.status_code, 403)
        self.assertEqual(LifecycleItemResponse.objects.filter(lifecycle_item=item).count(), 0)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="proof_response").count(), 0)

    def test_lifecycle_item_messages_are_shared_between_parties_and_notify_counterparty(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party=str(self.initiator.id),
            status=LifecycleItem.STATUS_COMPLETED,
            created_by=self.initiator,
        )

        response = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/messages/",
            {"body": "Please confirm once the deposit clears."},
            format="json",
        )
        counterparty_messages = self.counterparty_client.get(f"/api/lifecycle/items/{item.id}/messages/")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(counterparty_messages.status_code, 200)
        self.assertEqual(counterparty_messages.data["results"][0]["body"], "Please confirm once the deposit clears.")
        self.assertFalse(counterparty_messages.data["results"][0]["is_mine"])
        message = LifecycleItemMessage.objects.get(pk=response.data["id"])
        self.assertEqual(message.lifecycle_item, item)
        self.assertEqual(message.lifecycle_agreement, agreement)
        self.assertEqual(message.contract, self.contract)
        self.assertEqual(message.sender, self.initiator)
        notification = Notification.objects.get(user=self.counterparty, metadata__source="agreement_performance_message")
        self.assertEqual(notification.metadata["lifecycle_item_id"], str(item.id))
        self.assertEqual(notification.metadata["message_id"], str(message.id))
        self.assertEqual(notification.metadata["redirect_url"], "/agreement-performance")
        self.assertEqual(Notification.objects.filter(user=self.initiator, metadata__source="agreement_performance_message").count(), 0)
        item.refresh_from_db()
        agreement.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_COMPLETED)
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type__icontains="message").count(), 0)

    def test_lifecycle_item_message_rejects_blank_and_unrelated_users(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Provide loan funds",
            responsible_party=str(self.initiator.id),
            created_by=self.initiator,
        )

        blank = self.initiator_client.post(
            f"/api/lifecycle/items/{item.id}/messages/",
            {"body": "   "},
            format="json",
        )
        stranger = self.stranger_client.post(
            f"/api/lifecycle/items/{item.id}/messages/",
            {"body": "Not a party"},
            format="json",
        )

        self.assertEqual(blank.status_code, 400)
        self.assertEqual(stranger.status_code, 403)
        self.assertEqual(LifecycleItemMessage.objects.filter(lifecycle_item=item).count(), 0)
        self.assertEqual(Notification.objects.filter(metadata__source="agreement_performance_message").count(), 0)

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

    def test_add_on_change_proposal_create_lists_and_notifies_counterparty(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        response = self.initiator_client.post(
            f"/api/lifecycle/agreements/{agreement.id}/proposals/",
            {
                "proposal_type": "add_on",
                "title": "Extend rental two days",
                "description": "Add two more performance days.",
                "responsible_party": "counterparty",
                "amount": "125.50",
                "due_date": "2026-07-15",
                "note": "Please review this add-on.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        proposal = LifecycleChangeProposal.objects.get(pk=response.data["id"])
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(proposal.proposal_type, LifecycleChangeProposal.TYPE_ADD_ON)
        self.assertEqual(proposal.status, LifecycleChangeProposal.STATUS_PROPOSED)
        self.assertIsNone(proposal.affected_item_id)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_type=LifecycleItem.SOURCE_ADD_ON).count(), 0)

        notification = Notification.objects.get(user=self.counterparty, metadata__source="agreement_performance_change_proposal")
        self.assertEqual(notification.metadata["action"], "create_add_on")
        self.assertEqual(notification.metadata["proposal_id"], str(proposal.id))
        self.assertEqual(notification.metadata["redirect_url"], "/agreement-performance")
        self.assertEqual(Notification.objects.filter(user=self.initiator, metadata__source="agreement_performance_change_proposal").count(), 0)

        initiator_list = self.initiator_client.get(f"/api/lifecycle/agreements/{agreement.id}/proposals/")
        counterparty_list = self.counterparty_client.get(f"/api/lifecycle/agreements/{agreement.id}/proposals/")
        stranger_list = self.stranger_client.get(f"/api/lifecycle/agreements/{agreement.id}/proposals/")
        self.assertEqual(initiator_list.status_code, 200)
        self.assertEqual(counterparty_list.status_code, 200)
        self.assertEqual(stranger_list.status_code, 403)
        self.assertEqual(initiator_list.data["results"][0]["id"], str(proposal.id))
        self.assertEqual(counterparty_list.data["results"][0]["id"], str(proposal.id))

    def test_change_order_proposal_requires_affected_item_and_does_not_mutate_item(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_SERVICE_WORK,
            title="Initial service scope",
            description="Original scope",
            status=LifecycleItem.STATUS_PENDING,
            created_by=self.initiator,
        )

        missing = self.initiator_client.post(
            f"/api/lifecycle/agreements/{agreement.id}/proposals/",
            {"proposal_type": "change_order", "title": "Split work", "description": "Split the scope."},
            format="json",
        )
        self.assertEqual(missing.status_code, 400)

        response = self.counterparty_client.post(
            f"/api/lifecycle/agreements/{agreement.id}/proposals/",
            {
                "proposal_type": "change_order",
                "affected_item_id": str(item.id),
                "title": "Split work",
                "description": "Split the scope into two milestones.",
                "amount": "50.00",
                "due_date": "2026-08-01",
                "responsible_party": "initiator",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        item.refresh_from_db()
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        proposal = LifecycleChangeProposal.objects.get(pk=response.data["id"])
        self.assertEqual(proposal.affected_item_id, item.id)
        self.assertEqual(item.item_type, LifecycleItem.TYPE_SERVICE_WORK)
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        notification = Notification.objects.get(user=self.initiator, metadata__source="agreement_performance_change_proposal")
        self.assertEqual(notification.metadata["action"], "create_change_order")
        self.assertEqual(notification.metadata["affected_item_id"], str(item.id))

    def test_unrelated_user_cannot_create_or_retrieve_change_proposal(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        response = self.initiator_client.post(
            f"/api/lifecycle/agreements/{agreement.id}/proposals/",
            {
                "proposal_type": "add_on",
                "title": "Extra service",
                "description": "Add extra service.",
                "responsible_party": "initiator",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        stranger_create = self.stranger_client.post(
            f"/api/lifecycle/agreements/{agreement.id}/proposals/",
            {
                "proposal_type": "add_on",
                "title": "Bad proposal",
                "description": "Should fail.",
                "responsible_party": "initiator",
            },
            format="json",
        )
        stranger_detail = self.stranger_client.get(f"/api/lifecycle/proposals/{response.data['id']}/")
        self.assertEqual(stranger_create.status_code, 403)
        self.assertEqual(stranger_detail.status_code, 403)
        self.assertEqual(LifecycleChangeProposal.objects.count(), 1)

    def test_change_proposal_messages_are_proposal_scoped_and_notify_other_party(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        proposal = LifecycleChangeProposal.objects.create(
            lifecycle_agreement=agreement,
            contract=self.contract,
            proposal_type=LifecycleChangeProposal.TYPE_ADD_ON,
            status=LifecycleChangeProposal.STATUS_PROPOSED,
            proposed_by=self.counterparty,
            title="Monthly check-in",
            description="Add a recurring performance check-in.",
            responsible_party=LifecycleChangeProposal.RESPONSIBLE_COUNTERPARTY,
        )

        empty = self.initiator_client.get(f"/api/lifecycle/proposals/{proposal.id}/messages/")
        response = self.counterparty_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/messages/",
            {"body": "Please review this add-on before the next deadline."},
            format="json",
        )
        initiator_list = self.initiator_client.get(f"/api/lifecycle/proposals/{proposal.id}/messages/")
        stranger_list = self.stranger_client.get(f"/api/lifecycle/proposals/{proposal.id}/messages/")

        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.data["results"], [])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["body"], "Please review this add-on before the next deadline.")
        self.assertTrue(response.data["is_mine"])
        self.assertEqual(initiator_list.status_code, 200)
        self.assertEqual(initiator_list.data["results"][0]["id"], response.data["id"])
        self.assertFalse(initiator_list.data["results"][0]["is_mine"])
        self.assertEqual(stranger_list.status_code, 403)
        self.assertEqual(LifecycleChangeProposalMessage.objects.filter(proposal=proposal).count(), 1)

        proposal.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(proposal.status, LifecycleChangeProposal.STATUS_PROPOSED)
        self.assertEqual(self.contract.status, "signed")
        notification = Notification.objects.get(user=self.initiator, metadata__source="agreement_performance_change_proposal_message")
        self.assertEqual(notification.metadata["proposal_id"], str(proposal.id))
        self.assertEqual(Notification.objects.filter(user=self.counterparty, metadata__source="agreement_performance_change_proposal_message").count(), 0)

    def test_non_proposer_can_accept_change_order_and_update_affected_obligation(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Payment installment 1",
            due_date=datetime(2026, 7, 31, 0, 0, tzinfo=dt_timezone.utc),
            amount="400.00",
            responsible_party="Original responsible party",
            status=LifecycleItem.STATUS_PENDING,
            created_by=self.initiator,
        )
        LifecycleItemUserState.objects.create(
            lifecycle_item=item,
            user=self.initiator,
            due_date_override=datetime(2026, 6, 26, 0, 0, tzinfo=dt_timezone.utc),
            amount_override="400.00",
            responsible_party_override="Borrower",
            status_override=LifecycleItem.STATUS_PENDING,
        )
        proposal = LifecycleChangeProposal.objects.create(
            lifecycle_agreement=agreement,
            contract=self.contract,
            proposal_type=LifecycleChangeProposal.TYPE_CHANGE_ORDER,
            status=LifecycleChangeProposal.STATUS_PROPOSED,
            proposed_by=self.counterparty,
            affected_item=item,
            title="Move first repayment deadline",
            description="Change the first due date.",
            due_date="2026-08-01",
            amount="400.00",
            responsible_party=LifecycleChangeProposal.RESPONSIBLE_INITIATOR,
        )

        proposer_attempt = self.counterparty_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {"decision": "accepted", "note": "I accept my own proposal."},
            format="json",
        )
        response = self.initiator_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {
                "decision": "accepted",
                "note": "Based on the proposal chat, first repayment deadline moves to August 6, 2026.",
                "final_due_date": "2026-08-06",
                "final_amount": "400.00",
                "final_responsible_party": LifecycleChangeProposal.RESPONSIBLE_COUNTERPARTY,
            },
            format="json",
        )
        second_decision = self.initiator_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {"decision": "rejected"},
            format="json",
        )
        stranger_decision = self.stranger_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {"decision": "rejected"},
            format="json",
        )

        self.assertEqual(proposer_attempt.status_code, 403)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], LifecycleChangeProposal.STATUS_ACCEPTED)
        self.assertEqual(response.data["decision_note"], "Based on the proposal chat, first repayment deadline moves to August 6, 2026.")
        self.assertEqual(response.data["final_due_date"], "2026-08-06")
        self.assertEqual(response.data["final_amount"], "400.00")
        self.assertEqual(response.data["can_decide"], False)
        self.assertEqual(second_decision.status_code, 400)
        self.assertEqual(stranger_decision.status_code, 403)

        proposal.refresh_from_db()
        item.refresh_from_db()
        overlay = LifecycleItemUserState.objects.get(lifecycle_item=item, user=self.initiator)
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(proposal.status, LifecycleChangeProposal.STATUS_ACCEPTED)
        self.assertEqual(proposal.decided_by, self.initiator)
        self.assertIsNotNone(proposal.decided_at)
        self.assertEqual(proposal.final_due_date.isoformat(), "2026-08-06")
        self.assertEqual(str(proposal.final_amount), "400.00")
        self.assertEqual(item.due_date.date().isoformat(), "2026-08-06")
        self.assertEqual(str(item.amount), "400.00")
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(overlay.due_date_override.isoformat(), "2026-08-06T00:00:00+00:00")
        self.assertEqual(item.title, "Payment installment 1")
        self.assertEqual(LifecycleItem.objects.filter(lifecycle_agreement=agreement).count(), 1)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        event = LifecycleEvent.objects.get(lifecycle_agreement=agreement, event_type="change_order_accepted")
        self.assertEqual(event.metadata["proposal_id"], str(proposal.id))
        self.assertEqual(event.metadata["affected_item_id"], str(item.id))
        self.assertEqual(event.metadata["old_due_date"], "2026-07-31T00:00:00+00:00")
        self.assertIn("2026-08-06T00:00:00", event.metadata["new_due_date"])
        self.assertEqual(event.metadata["old_amount"], "400.00")
        self.assertEqual(event.metadata["new_amount"], "400.00")
        notification = Notification.objects.get(user=self.counterparty, metadata__source="agreement_performance_change_proposal", metadata__action=LifecycleChangeProposal.STATUS_ACCEPTED)
        self.assertEqual(notification.metadata["proposal_id"], str(proposal.id))
        self.assertEqual(notification.metadata["affected_item_id"], str(item.id))
        self.assertEqual(notification.metadata["lifecycle_event_id"], str(event.id))
        self.assertEqual(Notification.objects.filter(user=self.initiator, metadata__source="agreement_performance_change_proposal", metadata__action=LifecycleChangeProposal.STATUS_ACCEPTED).count(), 0)

        board = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        self.assertEqual(board.status_code, 200)
        payment = next(row for row in board.data["views"]["payments"] if row["id"] == str(item.id))
        deadline = next(row for row in board.data["views"]["due_dates"] if row["id"] == str(item.id))
        self.assertIn("2026-08-06T00:00:00", payment["due_date"])
        self.assertIn("2026-08-06T00:00:00", deadline["due_date"])
        self.assertNotIn("2026-07-31", [row.get("due_date", "")[:10] for row in board.data["views"]["due_dates"] if row["id"] == str(item.id)])

    def test_non_proposer_can_accept_add_on_and_create_active_obligation_once(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        proposal = LifecycleChangeProposal.objects.create(
            lifecycle_agreement=agreement,
            contract=self.contract,
            proposal_type=LifecycleChangeProposal.TYPE_ADD_ON,
            status=LifecycleChangeProposal.STATUS_PROPOSED,
            proposed_by=self.initiator,
            title="Monthly payments check-in",
            description="Add a monthly performance check-in obligation.",
            responsible_party=LifecycleChangeProposal.RESPONSIBLE_COUNTERPARTY,
            amount="25.00",
            due_date="2026-09-10",
        )

        proposer_attempt = self.initiator_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {"decision": "accepted", "note": "Trying to accept my own add-on."},
            format="json",
        )
        response = self.counterparty_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {
                "decision": "accepted",
                "note": "Accepted with final terms.",
                "final_due_date": "2026-09-15",
                "final_amount": "30.00",
                "final_responsible_party": LifecycleChangeProposal.RESPONSIBLE_COUNTERPARTY,
            },
            format="json",
        )
        second_decision = self.counterparty_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {"decision": "accepted"},
            format="json",
        )

        self.assertEqual(proposer_attempt.status_code, 403)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], LifecycleChangeProposal.STATUS_ACCEPTED)
        self.assertIsNotNone(response.data["created_item_id"])
        self.assertEqual(response.data["final_due_date"], "2026-09-15")
        self.assertEqual(response.data["final_amount"], "30.00")
        self.assertEqual(second_decision.status_code, 400)

        proposal.refresh_from_db()
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        created_item = LifecycleItem.objects.get(pk=response.data["created_item_id"])
        self.assertEqual(proposal.status, LifecycleChangeProposal.STATUS_ACCEPTED)
        self.assertEqual(proposal.decided_by, self.counterparty)
        self.assertEqual(proposal.decision_note, "Accepted with final terms.")
        self.assertEqual(proposal.final_due_date.isoformat(), "2026-09-15")
        self.assertEqual(str(proposal.final_amount), "30.00")
        self.assertEqual(proposal.final_responsible_party, self.contract.counterparty_name or self.contract.counterparty_email)
        self.assertEqual(created_item.lifecycle_agreement, agreement)
        self.assertEqual(created_item.source_type, LifecycleItem.SOURCE_ADD_ON)
        self.assertEqual(created_item.source_id, f"lifecycle_change_proposal:{proposal.id}")
        self.assertEqual(created_item.title, "Monthly payments check-in")
        self.assertEqual(created_item.description, "Add a monthly performance check-in obligation.")
        self.assertEqual(created_item.item_type, LifecycleItem.TYPE_PAYMENT)
        self.assertEqual(created_item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(created_item.due_date.date().isoformat(), "2026-09-15")
        self.assertEqual(str(created_item.amount), "30.00")
        self.assertEqual(created_item.metadata["proposal_id"], str(proposal.id))
        self.assertEqual(LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_type=LifecycleItem.SOURCE_ADD_ON, source_id=f"lifecycle_change_proposal:{proposal.id}").count(), 1)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)

        event = LifecycleEvent.objects.get(lifecycle_agreement=agreement, event_type="add_on_accepted")
        self.assertEqual(event.metadata["proposal_id"], str(proposal.id))
        self.assertEqual(event.metadata["created_item_id"], str(created_item.id))
        notification = Notification.objects.get(user=self.initiator, metadata__source="agreement_performance_change_proposal", metadata__action=LifecycleChangeProposal.STATUS_ACCEPTED)
        self.assertEqual(notification.metadata["proposal_type"], LifecycleChangeProposal.TYPE_ADD_ON)
        self.assertEqual(notification.metadata["proposal_id"], str(proposal.id))
        self.assertEqual(notification.metadata["created_item_id"], str(created_item.id))
        self.assertEqual(notification.metadata["lifecycle_event_id"], str(event.id))
        self.assertEqual(notification.metadata["redirect_url"], "/agreement-performance")
        self.assertEqual(Notification.objects.filter(user=self.counterparty, metadata__source="agreement_performance_change_proposal", metadata__action=LifecycleChangeProposal.STATUS_ACCEPTED).count(), 0)

        initiator_board = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        counterparty_board = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        self.assertEqual(initiator_board.status_code, 200)
        self.assertEqual(counterparty_board.status_code, 200)
        payment = next(row for row in initiator_board.data["views"]["payments"] if row["id"] == str(created_item.id))
        deadline = next(row for row in initiator_board.data["views"]["due_dates"] if row["id"] == str(created_item.id))
        counterparty_obligation = next(row for row in counterparty_board.data["views"]["my_obligations"] if row["id"] == str(created_item.id))
        self.assertEqual(payment["amount"], "30.00")
        self.assertIn("2026-09-15T00:00:00", payment["due_date"])
        self.assertEqual(deadline["id"], str(created_item.id))
        self.assertTrue(counterparty_obligation["can_upload_proof"])
        self.assertFalse(any(row["id"] == str(created_item.id) for row in initiator_board.data["views"]["my_obligations"]))
        self.assertTrue(any(event_row["event_type"] == "add_on_accepted" for event_row in initiator_board.data["views"]["activity"]))

    def test_accept_add_on_reuses_existing_created_obligation(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        proposal = LifecycleChangeProposal.objects.create(
            lifecycle_agreement=agreement,
            contract=self.contract,
            proposal_type=LifecycleChangeProposal.TYPE_ADD_ON,
            status=LifecycleChangeProposal.STATUS_PROPOSED,
            proposed_by=self.initiator,
            title="Monthly repayment check-in",
            description="Add a check-in obligation.",
            responsible_party=LifecycleChangeProposal.RESPONSIBLE_COUNTERPARTY,
        )
        existing_item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_RESPONSIBILITY,
            title=proposal.title,
            description=proposal.description,
            responsible_party=self.contract.counterparty_name or self.contract.counterparty_email,
            source_type=LifecycleItem.SOURCE_ADD_ON,
            source_id=f"lifecycle_change_proposal:{proposal.id}",
            status=LifecycleItem.STATUS_PENDING,
            created_by=self.initiator,
        )

        response = self.counterparty_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {"decision": "accepted"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_item_id"], str(existing_item.id))
        self.assertEqual(LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_type=LifecycleItem.SOURCE_ADD_ON, source_id=f"lifecycle_change_proposal:{proposal.id}").count(), 1)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="add_on_accepted", metadata__proposal_id=str(proposal.id)).count(), 1)

    def test_change_proposal_can_be_rejected_by_non_proposer(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        proposal = LifecycleChangeProposal.objects.create(
            lifecycle_agreement=agreement,
            contract=self.contract,
            proposal_type=LifecycleChangeProposal.TYPE_ADD_ON,
            status=LifecycleChangeProposal.STATUS_PROPOSED,
            proposed_by=self.initiator,
            title="Extra check-in",
            description="Add an extra check-in.",
            responsible_party=LifecycleChangeProposal.RESPONSIBLE_INITIATOR,
        )

        response = self.counterparty_client.post(
            f"/api/lifecycle/proposals/{proposal.id}/decision/",
            {"decision": "rejected", "note": "Not needed for this agreement."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], LifecycleChangeProposal.STATUS_REJECTED)
        proposal.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(proposal.status, LifecycleChangeProposal.STATUS_REJECTED)
        self.assertEqual(proposal.decision_note, "Not needed for this agreement.")
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement, event_type="change_proposal_rejected").count(), 1)
        self.assertEqual(LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_type=LifecycleItem.SOURCE_ADD_ON).count(), 0)
        self.assertEqual(self.contract.status, "signed")
        notification = Notification.objects.get(user=self.initiator, metadata__source="agreement_performance_change_proposal")
        self.assertEqual(notification.metadata["action"], LifecycleChangeProposal.STATUS_REJECTED)

    def test_manual_timeline_item_defaults_origin_fields(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        response = self.initiator_client.post(
            f"/api/lifecycle/{agreement.id}/items/",
            {"item_type": "note", "title": "Manual note"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        item = LifecycleItem.objects.get(pk=response.data["id"])
        self.assertEqual(item.source_type, LifecycleItem.SOURCE_MANUAL)
        self.assertFalse(item.is_contract_derived)
        self.assertEqual(item.locked_fields, [])
        self.assertEqual(response.data["source_type"], LifecycleItem.SOURCE_MANUAL)
        self.assertFalse(response.data["is_contract_derived"])
        self.assertEqual(response.data["locked_fields"], [])

    def test_timeline_item_response_includes_origin_fields(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        source_version = self.version
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Origin aware payment",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_PAYMENT_RECORD,
            source_id="payment-123",
            source_label="Payment record 123",
            source_version=source_version,
            source_exchange=self._make_signed_exchange(source_version),
            is_contract_derived=True,
            locked_fields=["title", "amount"],
        )

        response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        payments = response.data["items"]["payments"]
        serialized = next(entry for entry in payments if entry["id"] == str(item.id))
        self.assertEqual(serialized["source_type"], LifecycleItem.SOURCE_PAYMENT_RECORD)
        self.assertEqual(serialized["source"], LifecycleItem.SOURCE_PAYMENT_RECORD)
        self.assertEqual(serialized["source_id"], "payment-123")
        self.assertEqual(serialized["source_label"], "Payment record 123")
        self.assertEqual(serialized["source_version_id"], str(source_version.id))
        self.assertEqual(serialized["source_exchange_id"], str(item.source_exchange_id))
        self.assertTrue(serialized["is_contract_derived"])
        self.assertEqual(serialized["locked_fields"], ["title", "amount"])

    def test_old_creation_payload_without_origin_fields_still_works(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)

        response = self.initiator_client.post(
            f"/api/lifecycle/{agreement.id}/items/",
            {"item_type": "payment", "title": "First payment", "amount": "100.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["source_type"], LifecycleItem.SOURCE_MANUAL)
        self.assertFalse(response.data["is_contract_derived"])
        self.assertEqual(response.data["locked_fields"], [])

    def test_manual_timeline_item_can_still_be_patched(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_NOTE,
            title="Original manual note",
            description="Original description",
            created_by=self.initiator,
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()

        response = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            {"title": "Updated manual note", "description": "Updated description", "notes": "Private note"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.title, "Original manual note")
        self.assertEqual(item.description, "Original description")
        overlay = LifecycleItemUserState.objects.get(lifecycle_item=item, user=self.initiator)
        self.assertEqual(overlay.title_override, "Updated manual note")
        self.assertEqual(overlay.description_override, "Updated description")
        self.assertEqual(overlay.notes, "Private note")
        self.assertEqual(response.data["title"], "Updated manual note")
        self.assertEqual(response.data["description"], "Updated description")
        self.assertEqual(response.data["baseline_values"]["title"], "Original manual note")
        self.assertEqual(response.data["baseline_values"]["description"], "Original description")
        self.assertTrue(response.data["has_personal_overrides"])
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events)

    def test_protected_origin_fields_cannot_be_patched(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_NOTE,
            title="Origin protected note",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            source_id="original-1",
            source_label="Original source",
            is_contract_derived=True,
            locked_fields=[],
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()

        response = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            {"source_type": LifecycleItem.SOURCE_MANUAL},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("origin fields cannot be edited", response.data["detail"])
        item.refresh_from_db()
        self.assertEqual(item.source_type, LifecycleItem.SOURCE_ORIGINAL_CONTRACT)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events)

    def test_contract_derived_item_can_be_corrected_without_changing_source_fields(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Extracted payment",
            description="Extracted description",
            responsible_party="Borrower",
            beneficiary_party="Lender",
            due_date=datetime(2026, 8, 1, 0, 0, tzinfo=dt_timezone.utc),
            amount="400.00",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            source_id="repayment_schedule:test:1",
            source_label="Repayment schedule",
            source_version=self.version,
            source_exchange=self._make_signed_exchange(self.version),
            is_contract_derived=True,
            locked_fields=["title", "description", "amount", "due_date", "responsible_party", "status"],
            metadata={"payment_method": "bank transfer"},
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()
        before_notifications = Notification.objects.count()

        response = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            {
                "title": "Corrected payment installment 1",
                "description": "Corrected description",
                "responsible_party": "Borrower",
                "amount": "450.00",
                "due_date": "2026-08-15T00:00:00Z",
                "status": LifecycleItem.STATUS_CONFIRMED,
                "payment_method": "ACH transfer",
                "notes": "Personal follow-up note",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.title, "Extracted payment")
        self.assertEqual(item.description, "Extracted description")
        self.assertEqual(item.responsible_party, "Borrower")
        self.assertEqual(str(item.amount), "400.00")
        self.assertEqual(item.due_date.isoformat(), "2026-08-01T00:00:00+00:00")
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        self.assertEqual(item.metadata["payment_method"], "bank transfer")
        overlay = LifecycleItemUserState.objects.get(lifecycle_item=item, user=self.initiator)
        self.assertEqual(overlay.title_override, "Corrected payment installment 1")
        self.assertEqual(overlay.description_override, "Corrected description")
        self.assertEqual(overlay.responsible_party_override, "Borrower")
        self.assertEqual(str(overlay.amount_override), "450.00")
        self.assertEqual(overlay.due_date_override.isoformat(), "2026-08-15T00:00:00+00:00")
        self.assertEqual(overlay.status_override, LifecycleItem.STATUS_CONFIRMED)
        self.assertEqual(overlay.payment_method_override, "ACH transfer")
        self.assertEqual(overlay.notes, "Personal follow-up note")
        self.assertEqual(overlay.metadata["original_values"]["title"], "Extracted payment")
        self.assertEqual(overlay.metadata["original_values"]["amount"], "400.00")
        self.assertEqual(overlay.metadata["original_values"]["due_date"], "2026-08-01T00:00:00+00:00")
        self.assertEqual(overlay.metadata["corrections"][-1]["updated_fields"], ["title", "description", "responsible_party", "amount", "due_date", "status", "payment_method", "notes"])
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events)
        self.assertEqual(Notification.objects.count(), before_notifications)
        self.assertEqual(response.data["payment_method"], "ACH transfer")
        self.assertEqual(response.data["amount"], "450.00")
        self.assertEqual(response.data["due_date"], "2026-08-15T00:00:00+00:00")
        self.assertEqual(response.data["baseline_values"]["title"], "Extracted payment")
        self.assertEqual(response.data["baseline_values"]["amount"], "400.00")
        self.assertEqual(response.data["baseline_values"]["due_date"], "2026-08-01T00:00:00+00:00")
        self.assertTrue(response.data["has_personal_overrides"])

    def test_contract_derived_item_can_patch_status_and_preserve_original_source_values(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_NOTE,
            title="Unlocked status item",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            is_contract_derived=True,
            locked_fields=["title", "description", "amount", "due_date"],
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()

        response = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            {"status": LifecycleItem.STATUS_CONFIRMED, "notes": "Status corrected privately"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, LifecycleItem.STATUS_PENDING)
        overlay = LifecycleItemUserState.objects.get(lifecycle_item=item, user=self.initiator)
        self.assertEqual(overlay.status_override, LifecycleItem.STATUS_CONFIRMED)
        self.assertEqual(overlay.notes, "Status corrected privately")
        self.assertEqual(response.data["status"], LifecycleItem.STATUS_CONFIRMED)
        self.assertEqual(response.data["baseline_values"]["status"], LifecycleItem.STATUS_PENDING)
        self.assertTrue(response.data["has_personal_overrides"])
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events)

    def test_protected_origin_fields_cannot_be_patched(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_NOTE,
            title="Origin protected note",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            source_id="original-1",
            source_label="Original source",
            is_contract_derived=True,
            locked_fields=[],
        )
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()

        response = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            {"source_type": LifecycleItem.SOURCE_MANUAL},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("origin fields cannot be edited", response.data["detail"])
        item.refresh_from_db()
        self.assertEqual(item.source_type, LifecycleItem.SOURCE_ORIGINAL_CONTRACT)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events)

    def test_timeline_loads_with_contract_derived_item_without_activation(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_NOTE,
            title="Derived source note",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            is_contract_derived=True,
            locked_fields=["title"],
        )

        response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["contract"]["id"], str(self.contract.id))
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)

    def test_personal_overlay_is_user_specific_and_persists_across_refresh(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Shared payment",
            description="Shared payment baseline",
            responsible_party="Borrower",
            beneficiary_party="Lender",
            due_date=datetime(2026, 9, 1, 0, 0, tzinfo=dt_timezone.utc),
            amount="400.00",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            source_id="repayment_schedule:test:2",
            source_label="Repayment schedule",
            source_version=self.version,
            source_exchange=self._make_signed_exchange(self.version),
            is_contract_derived=True,
            locked_fields=["title", "amount", "due_date"],
            metadata={"payment_method": "bank transfer"},
        )

        response = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            {"due_date": "2026-09-15T00:00:00Z", "amount": "450.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["due_date"], "2026-09-15T00:00:00+00:00")
        self.assertEqual(response.data["amount"], "450.00")
        self.assertEqual(response.data["baseline_values"]["due_date"], "2026-09-01T00:00:00+00:00")
        self.assertEqual(response.data["baseline_values"]["amount"], "400.00")

        initiator_response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        counterparty_response = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        self.assertEqual(initiator_response.status_code, 200)
        self.assertEqual(counterparty_response.status_code, 200)
        initiator_payment = next(entry for entry in initiator_response.data["items"]["payments"] if entry["id"] == str(item.id))
        counterparty_payment = next(entry for entry in counterparty_response.data["items"]["payments"] if entry["id"] == str(item.id))
        self.assertEqual(initiator_payment["due_date"], "2026-09-15T00:00:00+00:00")
        self.assertEqual(initiator_payment["amount"], "450.00")
        self.assertTrue(initiator_payment["has_personal_overrides"])
        self.assertEqual(counterparty_payment["due_date"], "2026-09-01T00:00:00+00:00")
        self.assertEqual(counterparty_payment["amount"], "400.00")
        self.assertFalse(counterparty_payment["has_personal_overrides"])

        repeat_response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        repeat_payment = next(entry for entry in repeat_response.data["items"]["payments"] if entry["id"] == str(item.id))
        self.assertEqual(repeat_payment["due_date"], "2026-09-15T00:00:00+00:00")
        self.assertEqual(repeat_payment["amount"], "450.00")
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_id="repayment_schedule:test:2").count(), 1)

    def test_personal_overlay_repeated_patch_updates_existing_user_state(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        source_exchange = self._make_signed_exchange(self.version)
        item = LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_PAYMENT,
            title="Payment installment 2",
            description="Scheduled repayment from the signed agreement.",
            responsible_party="Borrower",
            beneficiary_party="Lender",
            due_date=datetime(2026, 9, 1, 0, 0, tzinfo=dt_timezone.utc),
            amount="400.00",
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            source_id="repayment_schedule:test:repeat:2",
            source_label="Repayment schedule",
            source_version=self.version,
            source_exchange=source_exchange,
            is_contract_derived=True,
            locked_fields=["title", "description", "amount", "due_date", "source_type", "source_id", "source_label", "source_version", "source_exchange", "is_contract_derived", "locked_fields"],
            metadata={"payment_method": "bank transfer"},
        )
        signed_snapshot = self.version.content_snapshot
        before_events = LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count()
        before_notifications = Notification.objects.count()

        initiator_first_payload = {"due_date": "2026-09-01T00:00:00.000Z"}
        initiator_first = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            initiator_first_payload,
            format="json",
        )
        self.assertEqual(initiator_first.status_code, 200)

        initiator_second_payload = dict(initiator_first.data)
        initiator_second_payload["amount"] = "450"
        initiator_second = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            initiator_second_payload,
            format="json",
        )
        self.assertEqual(initiator_second.status_code, 200)
        self.assertEqual(initiator_second.data["amount"], "450.00")

        initiator_third_payload = dict(initiator_second.data)
        initiator_third_payload["description"] = "Initiator private description."
        initiator_third_payload["notes"] = "Initiator private note."
        initiator_third = self.initiator_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            initiator_third_payload,
            format="json",
        )
        self.assertEqual(initiator_third.status_code, 200)
        self.assertEqual(initiator_third.data["description"], "Initiator private description.")
        self.assertEqual(initiator_third.data["notes"], "Initiator private note.")

        counterparty_get = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        self.assertEqual(counterparty_get.status_code, 200)
        counterparty_initial = next(entry for entry in counterparty_get.data["items"]["payments"] if entry["id"] == str(item.id))
        self.assertEqual(counterparty_initial["due_date"], "2026-09-01T00:00:00+00:00")
        self.assertEqual(counterparty_initial["amount"], "400.00")
        self.assertFalse(counterparty_initial["has_personal_overrides"])

        counterparty_first_payload = {"due_date": "2026-09-03T00:00:00.000Z"}
        counterparty_first = self.counterparty_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            counterparty_first_payload,
            format="json",
        )
        self.assertEqual(counterparty_first.status_code, 200)
        self.assertEqual(counterparty_first.data["due_date"], "2026-09-03T00:00:00+00:00")

        counterparty_second_payload = dict(counterparty_first.data)
        counterparty_second_payload["amount"] = "425"
        counterparty_second = self.counterparty_client.patch(
            f"/api/lifecycle/items/{item.id}/",
            counterparty_second_payload,
            format="json",
        )
        self.assertEqual(counterparty_second.status_code, 200)
        self.assertEqual(counterparty_second.data["amount"], "425.00")

        initiator_get = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        counterparty_get = self.counterparty_client.get(f"/api/lifecycle/?contract={self.contract.id}")
        initiator_payment = next(entry for entry in initiator_get.data["items"]["payments"] if entry["id"] == str(item.id))
        counterparty_payment = next(entry for entry in counterparty_get.data["items"]["payments"] if entry["id"] == str(item.id))
        self.assertEqual(initiator_payment["amount"], "450.00")
        self.assertEqual(initiator_payment["description"], "Initiator private description.")
        self.assertEqual(counterparty_payment["due_date"], "2026-09-03T00:00:00+00:00")
        self.assertEqual(counterparty_payment["amount"], "425.00")

        item.refresh_from_db()
        self.version.refresh_from_db()
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(LifecycleItemUserState.objects.filter(lifecycle_item=item, user=self.initiator).count(), 1)
        self.assertEqual(LifecycleItemUserState.objects.filter(lifecycle_item=item, user=self.counterparty).count(), 1)
        self.assertEqual(LifecycleItemUserState.objects.filter(lifecycle_item=item).count(), 2)
        self.assertEqual(str(item.amount), "400.00")
        self.assertEqual(item.due_date.isoformat(), "2026-09-01T00:00:00+00:00")
        self.assertEqual(item.description, "Scheduled repayment from the signed agreement.")
        self.assertEqual(self.version.content_snapshot, signed_snapshot)
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)
        self.assertEqual(LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_id="repayment_schedule:test:repeat:2").count(), 1)
        self.assertEqual(LifecycleEvent.objects.filter(lifecycle_agreement=agreement).count(), before_events)
        self.assertEqual(Notification.objects.count(), before_notifications)

    def _make_signed_exchange(self, source_version):
        exchange = AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=source_version,
            source_contract_version=source_version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_SIGNED,
            current_actor=AgreementExchange.ACTOR_NONE,
        )
        return exchange

    def test_whole_contract_service_obligation_is_not_returned_as_timeline_item(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        whole_contract_text = "\n".join([
            "PERSONAL REPAYMENT AGREEMENT",
            "This Personal Repayment Agreement is made between the Lender and Borrower.",
            "Borrower shall repay the Lender under the terms of this agreement.",
            "Governing law applies to this agreement.",
            "Signatures are set out below.",
        ]) * 20
        ContractServiceObligation.objects.create(
            contract=self.contract,
            version=self.version,
            obligor=self.counterparty,
            obligee=self.initiator,
            description=whole_contract_text,
            due_date=datetime(2030, 1, 1, 12, 0, tzinfo=dt_timezone.utc),
        )

        response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"]["services"], [])
        self.assertEqual(response.data["views"]["work_services"], [])
        self.assertFalse(any("PERSONAL REPAYMENT AGREEMENT" in item.get("title", "") for item in response.data["views"]["upcoming"]))
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)

    def test_original_contract_document_is_not_returned_as_timeline_item(self):
        agreement = get_or_create_lifecycle_for_signed_contract(self.contract, self.initiator)
        LifecycleItem.objects.create(
            lifecycle_agreement=agreement,
            item_type=LifecycleItem.TYPE_DOCUMENT,
            title="Signed Agreement v1",
            description=self.snapshot,
            created_by=self.initiator,
            source_type=LifecycleItem.SOURCE_ORIGINAL_CONTRACT,
            source_version=self.version,
            is_contract_derived=True,
            locked_fields=["title", "description"],
        )

        response = self.initiator_client.get(f"/api/lifecycle/?contract={self.contract.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["signed_version"]["content_snapshot"], self.snapshot)
        self.assertEqual(response.data["items"]["documents"], [])
        self.assertEqual(response.data["views"]["documents"], [])
        self.contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)

    def test_signed_loan_repayment_schedule_creates_structured_timeline_items(self):
        loan_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        loan_contract.title = "Personal Loan and Repayment Agreement"
        loan_contract.status = "signed"
        loan_contract.save(update_fields=["title", "status"])
        loan_snapshot = json.dumps({
            "editor_html": """
                <h2>PERSONAL REPAYMENT AGREEMENT</h2>
                <p>The Lender agrees to lend the Borrower the total amount of Two Thousand Four Hundred Dollars ($2,400).</p>
                <p>The Lender will provide the loan funds to the Borrower no later than July 5, 2026.</p>
                <p>The loan may be delivered by bank transfer, electronic payment, or another method agreed to by both parties in writing.</p>
                <p>The Borrower will repay the loan in six monthly payments of Four Hundred Dollars ($400) each.</p>
                <p>Payment 1: $400 due August 1, 2026</p>
                <p>Payment 2: $400 due September 1, 2026</p>
                <p>Payment 3: $400 due October 1, 2026</p>
                <p>Payment 4: $400 due November 1, 2026</p>
                <p>Payment 5: $400 due December 1, 2026</p>
                <p>Payment 6: $400 due January 1, 2027</p>
                <p>The Borrower may make payments by bank transfer, electronic payment, cash with written receipt, or another method agreed to by both parties in writing.</p>
                <p>The Borrower is responsible for making each payment on time.</p>
                <p>The Borrower is responsible for keeping proof of payment.</p>
                <p>The Borrower must notify the Lender before a due date if the Borrower believes a payment may be late.</p>
                <p>The Lender is responsible for confirming receipt of each payment within three business days.</p>
                <p>The Lender is responsible for keeping a record of payments received.</p>
                <p>If a payment is late, the Borrower must contact the Lender and provide an expected payment date.</p>
                <p>If default occurs, both parties should first attempt to resolve the issue through written communication.</p>
            """
        })
        loan_version = make_version(loan_contract, self.initiator, content_snapshot=loan_snapshot, status="signed")
        ContractObligation.objects.create(
            contract=loan_contract,
            version=loan_version,
            obligor=self.counterparty,
            obligee=self.initiator,
            installment_number=1,
            amount_due="2400.00",
            due_date=datetime(2026, 6, 21, 12, 0, tzinfo=dt_timezone.utc),
            state="active",
        )

        first_response = self.initiator_client.get(f"/api/lifecycle/?contract={loan_contract.id}")
        second_response = self.initiator_client.get(f"/api/lifecycle/?contract={loan_contract.id}")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        agreement = LifecycleAgreement.objects.get(contract=loan_contract)
        generated_payments = LifecycleItem.objects.filter(
            lifecycle_agreement=agreement,
            source_id__startswith=f"repayment_schedule:{loan_version.id}:",
        ).order_by("due_date")
        self.assertEqual(generated_payments.count(), 6)
        self.assertEqual(
            [item.title for item in generated_payments],
            [f"Payment installment {number}" for number in range(1, 7)],
        )
        self.assertEqual([str(item.amount) for item in generated_payments], ["400.00"] * 6)
        self.assertEqual(
            [item.due_date.date().isoformat() for item in generated_payments],
            ["2026-08-01", "2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01"],
        )
        first_payment = generated_payments.first()
        self.assertEqual(first_payment.source_type, LifecycleItem.SOURCE_ORIGINAL_CONTRACT)
        self.assertEqual(first_payment.source_version_id, loan_version.id)
        self.assertTrue(first_payment.is_contract_derived)
        self.assertIn("title", first_payment.locked_fields)
        self.assertIn("amount", first_payment.locked_fields)
        self.assertIn("due_date", first_payment.locked_fields)
        self.assertIn("source_type", first_payment.locked_fields)

        response_payments = first_response.data["views"]["payments"]
        self.assertEqual(len(response_payments), 6)
        self.assertEqual([item["amount"] for item in response_payments], ["400.00"] * 6)
        self.assertFalse(any(item["amount"] == "2400.00" for item in response_payments))
        self.assertTrue(any(item["title"] == "Loan funds delivery deadline" for item in first_response.data["views"]["due_dates"]))
        work_items = first_response.data["views"]["work_services"]
        self.assertTrue(any(item["title"] == "Provide loan funds" for item in work_items))
        delivery_work = next(item for item in work_items if item["title"] == "Provide loan funds")
        self.assertEqual(delivery_work["amount"], "2400.00")
        self.assertEqual(delivery_work["due_date"], "2026-07-05T00:00:00+00:00")
        self.assertEqual(delivery_work["responsible_party"], "Lender")
        self.assertTrue(delivery_work["is_contract_derived"])
        self.assertTrue(any("confirm receipt" in item["title"].lower() for item in first_response.data["views"]["to_dos"]))
        loan_contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(loan_contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)

    def test_signed_loan_repayment_schedule_uses_contract_values_for_different_terms(self):
        loan_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        loan_contract.title = "Different Personal Loan Agreement"
        loan_contract.status = "signed"
        loan_contract.save(update_fields=["title", "status"])
        loan_snapshot = json.dumps({
            "editor_html": """
                <h2>PERSONAL LOAN AND REPAYMENT AGREEMENT</h2>
                <p>The Lender agrees to lend the Borrower the total amount of One Thousand Five Hundred Dollars ($1,500).</p>
                <p>The Lender will provide the loan funds to the Borrower no later than 7/10/2026.</p>
                <p>The loan may be delivered by wire transfer or certified check.</p>
                <p>The Borrower will repay the loan in three monthly payments of Five Hundred Dollars ($500) each.</p>
                <p>Payment 1: $500 due 8/15/2026</p>
                <p>Payment 2: $500 due 9/15/2026</p>
                <p>Payment 3: $500 due 10/15/2026</p>
                <p>The Borrower is responsible for making each payment on time.</p>
                <p>The Lender is responsible for confirming receipt of each payment within two business days.</p>
            """
        })
        loan_version = make_version(loan_contract, self.initiator, content_snapshot=loan_snapshot, status="signed")

        first_response = self.initiator_client.get(f"/api/lifecycle/?contract={loan_contract.id}")
        second_response = self.initiator_client.get(f"/api/lifecycle/?contract={loan_contract.id}")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        agreement = LifecycleAgreement.objects.get(contract=loan_contract)
        generated_payments = LifecycleItem.objects.filter(
            lifecycle_agreement=agreement,
            source_id__startswith=f"repayment_schedule:{loan_version.id}:",
        ).order_by("due_date")
        self.assertEqual(generated_payments.count(), 3)
        self.assertEqual([str(item.amount) for item in generated_payments], ["500.00"] * 3)
        self.assertEqual(
            [item.due_date.date().isoformat() for item in generated_payments],
            ["2026-08-15", "2026-09-15", "2026-10-15"],
        )
        response_payments = second_response.data["views"]["payments"]
        self.assertEqual(len(response_payments), 3)
        self.assertEqual([item["amount"] for item in response_payments], ["500.00"] * 3)
        self.assertEqual(
            [item["due_date"] for item in response_payments],
            ["2026-08-15T00:00:00+00:00", "2026-09-15T00:00:00+00:00", "2026-10-15T00:00:00+00:00"],
        )
        work_items = second_response.data["views"]["work_services"]
        self.assertEqual(len([item for item in work_items if item["title"] == "Provide loan funds"]), 1)
        delivery_work = next(item for item in work_items if item["title"] == "Provide loan funds")
        self.assertEqual(delivery_work["amount"], "1500.00")
        self.assertEqual(delivery_work["due_date"], "2026-07-10T00:00:00+00:00")
        self.assertEqual(delivery_work["responsible_party"], "Lender")
        self.assertIn("wire transfer", delivery_work["description"])
        self.assertTrue(delivery_work["is_contract_derived"])
        self.assertEqual(
            LifecycleItem.objects.filter(lifecycle_agreement=agreement, source_id__startswith=f"repayment_schedule:{loan_version.id}:").count(),
            3,
        )
        loan_contract.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(loan_contract.status, "signed")
        self.assertEqual(agreement.status, LifecycleAgreement.STATUS_SETUP)

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
