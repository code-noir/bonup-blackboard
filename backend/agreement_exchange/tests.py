import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from backend.agreement_exchange.services import exchange_notification_metadata, notify_counterparty
from backend.agreement_exchange.models import (
    AgreementExchange,
    AgreementExchangeEvent,
    AgreementExchangeRequest,
    AgreementExchangeSignature,
)
from backend.api.tests.helpers import authed_client, make_contract, make_user, make_version
from backend.contracts.models import ContractObligation, ContractServiceObligation, ContractVersion
from backend.notifications.models import Notification


class AgreementExchangeMVPAPITests(TestCase):
    def setUp(self):
        self.initiator = make_user("ae_initiator", "ae-initiator@example.com")
        self.counterparty = make_user("ae_counterparty", "ae-counterparty@example.com")
        self.initiator_client = authed_client(self.initiator)
        self.counterparty_client = authed_client(self.counterparty)
        self.contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        self.contract.title = "Service Agreement"
        self.contract.save(update_fields=["title"])
        self.snapshot = json.dumps({
            "sections": [
                {"id": "payment", "number": 1, "name": "Payment Terms", "content_html": "<p>Payment due on the 1st.</p>"},
                {"id": "services", "number": 2, "name": "Services", "content_html": "<p>Provide monthly service.</p>"},
            ],
            "editor_html": "<h2>Payment Terms</h2><p>Payment due on the 1st.</p><h2>Services</h2><p>Provide monthly service.</p>",
        })
        self.version = make_version(self.contract, self.initiator, content_snapshot=self.snapshot, status="sent")

    def create_exchange(self):
        response = self.initiator_client.post(
            "/api/agreement-exchange/",
            {
                "contract_id": str(self.contract.id),
                "contract_version_id": str(self.version.id),
                "counterparty_email": self.counterparty.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return AgreementExchange.objects.get(id=response.data["exchange"]["id"]), response

    def send_initial(self, exchange):
        return self.initiator_client.post(f"/api/agreement-exchange/{exchange.id}/send-initial/", {}, format="json")

    def submit_request(self, exchange):
        return self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "payment",
                "target_section_title": "Payment Terms",
                "request_category": "payment_terms",
                "action_type": "replace_clause",
                "template_key": "payment_due_date_change",
                "proposed_text": "Change payment due date to the 15th.",
                "reason": "I need payment due on the 15th instead of the 1st.",
            },
            format="json",
        )

    def restart_exchange(self, exchange, source_version=None, client=None):
        return (client or self.initiator_client).post(
            f"/api/agreement-exchange/{exchange.id}/restart/",
            {"source_version_id": str((source_version or exchange.current_contract_version).id)},
            format="json",
        )

    def snapshot_data(self, version):
        return json.loads(version.content_snapshot)

    def notification_for(self, user):
        return Notification.objects.filter(user=user).latest("created_at")

    def make_rejected_exchange_at_v3(self, reject=True):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        for text in ["Payment is due on the 15th.", "Payment is due on the 20th."]:
            self.submit_request(exchange)
            change = AgreementExchangeRequest.objects.filter(exchange=exchange).order_by("created_at").last()
            response = self.initiator_client.post(
                f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
                {"decision": "accept", "final_text": text},
                format="json",
            )
            self.assertEqual(response.status_code, 200)
            exchange.refresh_from_db()
        if reject:
            response = self.counterparty_client.post(
                f"/api/agreement-exchange/{exchange.id}/reject/",
                {"reason": "No agreement after final version."},
                format="json",
            )
            self.assertEqual(response.status_code, 200)
            exchange.refresh_from_db()
        return exchange

    def test_create_exchange(self):
        exchange, response = self.create_exchange()

        self.assertEqual(exchange.status, AgreementExchange.STATUS_DRAFT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(response.data["viewer_role"], "initiator")
        self.assertEqual(response.data["screen_state"], "initiator_send_initial_version")
        self.assertEqual(response.data["available_actions"], ["send_initial_version"])
        self.assertEqual(response.data["current_contract"]["version_label"], "v1")
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="exchange_created").count(), 1)
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="exchange_sent").count(), 0)

    def test_detail_returns_viewer_role_screen_state_and_actions(self):
        exchange, _ = self.create_exchange()

        initiator_response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        counterparty_response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(initiator_response.status_code, 200)
        self.assertEqual(initiator_response.data["viewer_role"], "initiator")
        self.assertEqual(initiator_response.data["screen_state"], "initiator_send_initial_version")
        self.assertEqual(initiator_response.data["available_actions"], ["send_initial_version"])
        self.assertEqual(initiator_response.data["current_contract"]["sections"][0]["id"], "payment")
        self.assertEqual(initiator_response.data["current_contract"]["sections"][0]["anchor_id"], "contract-section-payment")
        self.assertEqual(initiator_response.data["current_contract"]["sections"][0]["order"], 1)
        self.assertEqual(initiator_response.data["current_contract"]["sections"][0]["content_html"], "<p>Payment due on the 1st.</p>")
        self.assertEqual(counterparty_response.status_code, 403)
        self.assertEqual(counterparty_response.data["detail"], "Agreement Exchange is not available yet.")

    def test_create_open_prefers_active_pending_exchange_over_newer_draft_duplicate(self):
        active, _ = self.create_exchange()
        self.send_initial(active)
        AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            source_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_DRAFT,
            current_actor=AgreementExchange.ACTOR_INITIATOR,
        )

        response = self.initiator_client.post(
            "/api/agreement-exchange/",
            {
                "contract_id": str(self.contract.id),
                "contract_version_id": str(self.version.id),
                "counterparty_email": self.counterparty.email,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["exchange"]["id"], str(active.id))
        counterparty_detail = self.counterparty_client.get(f"/api/agreement-exchange/{active.id}/")
        self.assertEqual(counterparty_detail.status_code, 200)
        self.assertEqual(counterparty_detail.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_detail.data["available_actions"], ["sign", "request_change", "reject"])

    def test_prepared_contract_dashboard_visibility_before_initial_send(self):
        self.contract.state = "prepared"
        self.contract.save(update_fields=["state"])

        initiator_response = self.initiator_client.get("/api/contracts/")
        counterparty_response = self.counterparty_client.get("/api/contracts/")

        self.assertEqual(initiator_response.status_code, 200)
        self.assertIn(str(self.contract.id), [item["id"] for item in initiator_response.data])
        self.assertEqual(counterparty_response.status_code, 200)
        self.assertNotIn(str(self.contract.id), [item["id"] for item in counterparty_response.data])

    def test_draft_exchange_dashboard_and_open_negotiation_are_private_to_initiator(self):
        exchange, _ = self.create_exchange()
        self.contract.state = "prepared"
        self.contract.save(update_fields=["state"])

        initiator_response = self.initiator_client.get("/api/contracts/")
        counterparty_response = self.counterparty_client.get("/api/contracts/")
        counterparty_detail = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")
        open_response = self.counterparty_client.post(
            "/api/ai/workflows/for-contract/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )

        self.assertIn(str(self.contract.id), [item["id"] for item in initiator_response.data])
        self.assertNotIn(str(self.contract.id), [item["id"] for item in counterparty_response.data])
        self.assertEqual(counterparty_detail.status_code, 403)
        self.assertEqual(open_response.status_code, 403)
        self.assertEqual(Notification.objects.filter(user=self.counterparty).count(), 0)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_DRAFT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)

    def test_after_initial_send_counterparty_dashboard_includes_contract(self):
        exchange, _ = self.create_exchange()
        self.contract.state = "prepared"
        self.contract.save(update_fields=["state"])

        self.send_initial(exchange)
        response = self.counterparty_client.get("/api/contracts/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(str(self.contract.id), [item["id"] for item in response.data])

    def test_open_negotiation_returns_active_exchange_for_counterparty(self):
        active, _ = self.create_exchange()
        self.send_initial(active)
        active.refresh_from_db()
        original_status = active.status
        original_actor = active.current_actor
        self.contract.state = "prepared"
        self.contract.save(update_fields=["state"])

        response = self.counterparty_client.post(
            "/api/ai/workflows/for-contract/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["exchange_id"], str(active.id))
        self.assertEqual(response.data["redirect_url"], f"/agreement-exchange/{active.id}")
        self.assertEqual(AgreementExchange.objects.count(), 1)
        active.refresh_from_db()
        self.assertEqual(active.status, original_status)
        self.assertEqual(active.current_actor, original_actor)
        detail = self.counterparty_client.get(f"/api/agreement-exchange/{active.id}/")
        self.assertEqual(detail.data["screen_state"], "counterparty_review")
        self.assertEqual(detail.data["available_actions"], ["sign", "request_change", "reject"])

    def test_open_negotiation_returns_active_exchange_for_initiator_waiting_view(self):
        active, _ = self.create_exchange()
        self.send_initial(active)
        self.contract.state = "prepared"
        self.contract.save(update_fields=["state"])

        response = self.initiator_client.post(
            "/api/ai/workflows/for-contract/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["exchange_id"], str(active.id))
        self.assertEqual(response.data["redirect_url"], f"/agreement-exchange/{active.id}")
        detail = self.initiator_client.get(f"/api/agreement-exchange/{active.id}/")
        self.assertEqual(detail.data["screen_state"], "initiator_waiting")
        self.assertEqual(detail.data["available_actions"], [])

    def test_open_negotiation_prefers_active_exchange_over_newer_draft_duplicate(self):
        active, _ = self.create_exchange()
        self.send_initial(active)
        self.contract.state = "prepared"
        self.contract.save(update_fields=["state"])
        AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            source_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_DRAFT,
            current_actor=AgreementExchange.ACTOR_INITIATOR,
        )

        response = self.counterparty_client.post(
            "/api/ai/workflows/for-contract/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AgreementExchange.objects.count(), 2)
        self.assertEqual(response.data["exchange_id"], str(active.id))
        self.assertEqual(response.data["redirect_url"], f"/agreement-exchange/{active.id}")

    def test_open_negotiation_returns_terminal_exchange_read_only_when_no_active_exists(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        reject_response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/reject/",
            {"reason": "No agreement."},
            format="json",
        )
        self.assertEqual(reject_response.status_code, 200)
        self.contract.state = "prepared"
        self.contract.save(update_fields=["state"])

        response = self.counterparty_client.post(
            "/api/ai/workflows/for-contract/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["exchange_id"], str(exchange.id))
        detail = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")
        self.assertEqual(detail.data["screen_state"], "rejected")
        self.assertEqual(detail.data["available_actions"], [])

    def test_send_initial_changes_actor_to_counterparty_without_creating_v2(self):
        exchange, _ = self.create_exchange()
        original_version_count = ContractVersion.objects.count()
        original_version_id = exchange.current_contract_version_id

        response = self.send_initial(exchange)

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(exchange.current_contract_version_id, original_version_id)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(response.data["screen_state"], "initiator_waiting")
        self.assertEqual(response.data["current_contract"]["version_label"], "v1")
        self.assertEqual(AgreementExchangeEvent.objects.filter(exchange=exchange, event_type="initial_version_sent").count(), 1)

    def test_after_send_counterparty_sees_review_actions(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)

        initiator_response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        counterparty_response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(initiator_response.data["screen_state"], "initiator_waiting")
        self.assertEqual(initiator_response.data["available_actions"], [])
        self.assertEqual(counterparty_response.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_counterparty_actions_persist_after_repeated_detail_fetches(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)

        for _ in range(3):
            response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["screen_state"], "counterparty_review")
            self.assertEqual(response.data["available_actions"], ["sign", "request_change", "reject"])

        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)

    def test_mark_viewed_does_not_consume_counterparty_pending_action(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        exchange.refresh_from_db()
        original_status = exchange.status
        original_actor = exchange.current_actor

        viewed_response = self.counterparty_client.post(f"/api/agreement-exchange/{exchange.id}/viewed/", {}, format="json")
        detail_response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(viewed_response.status_code, 200)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, original_status)
        self.assertEqual(exchange.current_actor, original_actor)
        self.assertEqual(viewed_response.data["available_actions"], ["sign", "request_change", "reject"])
        self.assertEqual(detail_response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_initial_send_creates_counterparty_notification_with_exchange_link(self):
        exchange, _ = self.create_exchange()

        response = self.send_initial(exchange)

        self.assertEqual(response.status_code, 200)
        notification = self.notification_for(self.counterparty)
        self.assertEqual(notification.metadata["exchange_id"], str(exchange.id))
        self.assertEqual(notification.metadata["redirect_url"], f"/agreement-exchange/{exchange.id}")

    def test_initial_send_creates_email_matched_counterparty_notification(self):
        exchange, _ = self.create_exchange()
        exchange.counterparty_user = None
        exchange.save(update_fields=["counterparty_user", "updated_at"])

        response = self.send_initial(exchange)

        self.assertEqual(response.status_code, 200)
        notification = self.notification_for(self.counterparty)
        self.assertEqual(notification.notification_type, "agreement_exchange")
        self.assertFalse(notification.is_read)
        self.assertEqual(notification.title, "Initial version sent")
        self.assertEqual(notification.metadata["exchange_id"], str(exchange.id))
        self.assertEqual(notification.metadata["contract_id"], str(self.contract.id))
        self.assertEqual(notification.metadata["action_type"], "review_initial_version")
        self.assertEqual(notification.metadata["source_event"], "initial_version_sent")
        self.assertEqual(notification.metadata["redirect_url"], f"/agreement-exchange/{exchange.id}")
        self.assertIn(self.contract.title, notification.message)
        self.assertIn(self.initiator.email, notification.message)
        self.assertIn("Action: Review and respond", notification.message)

    @override_settings(DEFAULT_FROM_EMAIL="noreply@example.com")
    @patch("backend.agreement_exchange.notifications.send_mail", side_effect=Exception("mail unavailable"))
    def test_initial_send_creates_in_app_notification_when_email_fails(self, _send_mail):
        exchange, _ = self.create_exchange()

        response = self.send_initial(exchange)

        self.assertEqual(response.status_code, 200)
        notification = self.notification_for(self.counterparty)
        self.assertEqual(notification.metadata["exchange_id"], str(exchange.id))
        event = AgreementExchangeEvent.objects.get(exchange=exchange, event_type="initial_version_sent")
        self.assertTrue(event.metadata["notification"]["in_app_created"])
        self.assertIn("error", event.metadata["notification"])

    def test_duplicate_notification_source_event_does_not_create_duplicate_unread(self):
        exchange, _ = self.create_exchange()
        metadata = exchange_notification_metadata(
            exchange,
            action_type="review_initial_version",
            source_event="initial_version_sent",
        )

        first = notify_counterparty(exchange, "Version 1 is ready for review.", metadata, title="Version 1 is ready for review")
        second = notify_counterparty(exchange, "Version 1 is ready for review.", metadata, title="Version 1 is ready for review")

        self.assertTrue(first["in_app_created"])
        self.assertTrue(second["in_app_created"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(Notification.objects.filter(user=self.counterparty, is_read=False, metadata__source_event="initial_version_sent").count(), 1)

    def test_unread_notifications_endpoint_returns_only_current_user_notifications(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        Notification.objects.create(
            user=self.initiator,
            notification_type="agreement_exchange",
            title="Other notification",
            message="Not for counterparty",
            related_contract=self.contract,
            metadata={"redirect_url": "/agreement-exchange/other"},
        )

        response = self.counterparty_client.get("/api/notifications/unread/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["metadata"]["exchange_id"], str(exchange.id))
        self.assertEqual(response.data["results"][0]["redirect_url"], f"/agreement-exchange/{exchange.id}")

    def test_mark_read_endpoint_marks_only_current_users_notification(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        notification = self.notification_for(self.counterparty)

        forbidden = self.initiator_client.post(f"/api/notifications/{notification.id}/read/")
        allowed = self.counterparty_client.post(f"/api/notifications/{notification.id}/read/")

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_after_send_role_action_matrix_is_viewer_specific(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)

        initiator_response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        counterparty_response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(initiator_response.status_code, 200)
        self.assertEqual(initiator_response.data["viewer_role"], "initiator")
        self.assertEqual(initiator_response.data["exchange"]["status"], AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(initiator_response.data["exchange"]["current_actor"], AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(initiator_response.data["screen_state"], "initiator_waiting")
        self.assertEqual(initiator_response.data["available_actions"], [])

        self.assertEqual(counterparty_response.status_code, 200)
        self.assertEqual(counterparty_response.data["viewer_role"], "counterparty")
        self.assertEqual(counterparty_response.data["exchange"]["status"], AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(counterparty_response.data["exchange"]["current_actor"], AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(counterparty_response.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_counterparty_email_matching_is_case_insensitive(self):
        exchange, _ = self.create_exchange()
        exchange.counterparty_email = self.counterparty.email.upper()
        exchange.counterparty_user = None
        exchange.save(update_fields=["counterparty_email", "counterparty_user", "updated_at"])
        self.send_initial(exchange)

        response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["viewer_role"], "counterparty")
        self.assertEqual(response.data["screen_state"], "counterparty_review")
        self.assertEqual(response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_counterparty_email_match_works_when_counterparty_user_is_null(self):
        exchange, _ = self.create_exchange()
        exchange.counterparty_user = None
        exchange.save(update_fields=["counterparty_user", "updated_at"])
        self.send_initial(exchange)

        response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["viewer_role"], "counterparty")
        self.assertEqual(response.data["screen_state"], "counterparty_review")
        self.assertEqual(response.data["available_actions"], ["sign", "request_change", "reject"])
        exchange.refresh_from_db()
        self.assertEqual(exchange.counterparty_user, self.counterparty)

    def test_counterparty_user_match_still_resolves_after_binding(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        exchange.counterparty_user = self.counterparty
        exchange.save(update_fields=["counterparty_user", "updated_at"])

        response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["viewer_role"], "counterparty")
        self.assertEqual(response.data["screen_state"], "counterparty_review")
        self.assertEqual(response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_role_action_resolution_is_not_tied_to_contract_title_or_exchange_id(self):
        other_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        other_contract.title = "Unrelated Vendor Form"
        other_contract.save(update_fields=["title"])
        other_snapshot = json.dumps({
            "sections": [{"id": "scope", "number": 1, "name": "Scope", "content_html": "<p>Do the work.</p>"}],
            "editor_html": "<h2>Scope</h2><p>Do the work.</p>",
        })
        other_version = make_version(other_contract, self.initiator, content_snapshot=other_snapshot, status="sent")
        response = self.initiator_client.post(
            "/api/agreement-exchange/",
            {
                "contract_id": str(other_contract.id),
                "contract_version_id": str(other_version.id),
                "counterparty_email": self.counterparty.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        exchange = AgreementExchange.objects.get(id=response.data["exchange"]["id"])
        self.send_initial(exchange)

        counterparty_response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(counterparty_response.status_code, 200)
        self.assertEqual(counterparty_response.data["viewer_role"], "counterparty")
        self.assertEqual(counterparty_response.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_non_initiator_cannot_send_initial_version(self):
        exchange, _ = self.create_exchange()

        response = self.counterparty_client.post(f"/api/agreement-exchange/{exchange.id}/send-initial/", {}, format="json")

        self.assertEqual(response.status_code, 403)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_DRAFT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)

    def test_counterparty_marks_viewed(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)

        response = self.counterparty_client.post(f"/api/agreement-exchange/{exchange.id}/viewed/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(AgreementExchangeEvent.objects.filter(exchange=exchange, event_type="exchange_viewed").count(), 1)

    def test_submit_request_saves_and_changes_current_actor_to_initiator(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)

        response = self.submit_request(exchange)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(AgreementExchangeRequest.objects.count(), 1)
        change = AgreementExchangeRequest.objects.get()
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_PENDING)
        self.assertEqual(change.requested_by_user, self.counterparty)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(response.data["exchange"]["screen_state"], "counterparty_waiting")
        self.assertEqual(response.data["exchange"]["available_actions"], [])
        initiator_detail = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        self.assertEqual(initiator_detail.data["available_actions"], ["apply_change", "edit_updated_version", "reject"])
        event = AgreementExchangeEvent.objects.get(event_type="counterparty_request_created")
        self.assertEqual(event.metadata["redirect_url"], f"/agreement-exchange/{exchange.id}")
        notification = self.notification_for(self.initiator)
        self.assertEqual(notification.title, "Change request received")
        self.assertEqual(notification.metadata["redirect_url"], f"/agreement-exchange/{exchange.id}")
        self.assertIn(self.contract.title, notification.message)
        self.assertIn(self.counterparty.email, notification.message)
        self.assertIn("Action: Accept, edit, or reject", notification.message)

    def test_initiator_sees_request(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)

        response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["screen_state"], "initiator_review_requested_change")
        self.assertEqual(response.data["available_actions"], ["apply_change", "edit_updated_version", "reject"])
        self.assertEqual(response.data["requests"][0]["proposed_text"], "Change payment due date to the 15th.")

    def test_initiator_request_actions_persist_after_repeated_detail_fetches(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)

        for _ in range(3):
            response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["screen_state"], "initiator_review_requested_change")
            self.assertEqual(response.data["available_actions"], ["apply_change", "edit_updated_version", "reject"])

        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)

    def test_initiator_reject_request_works(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "reject", "initiator_response": "Keep original due date."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        exchange.refresh_from_db()
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_REJECTED)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="initiator_request_rejected").count(), 1)

    def test_apply_change_stages_full_updated_version_without_handoff(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        original_version_count = ContractVersion.objects.count()
        original_snapshot = self.version.content_snapshot
        before_notifications = Notification.objects.filter(user=self.counterparty).count()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {
                "decision": "accept",
                "final_text": "Payment is due on the 15th.",
                "initiator_response": "Accepted for full contract review.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        exchange.refresh_from_db()
        self.version.refresh_from_db()
        staged = ContractVersion.objects.exclude(id=self.version.id).get()
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_ACCEPTED)
        self.assertEqual(change.pending_next_version_text, "Payment is due on the 15th.")
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_EDITING)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(exchange.current_contract_version_id, self.version.id)
        self.assertEqual(ContractVersion.objects.count(), original_version_count + 1)
        self.assertEqual(staged.version_number, 2)
        self.assertEqual(staged.previous_version, self.version)
        self.assertEqual(staged.status, "draft")
        self.assertEqual(self.version.content_snapshot, original_snapshot)
        self.assertEqual(self.version.status, "sent")
        self.assertEqual(Notification.objects.filter(user=self.counterparty).count(), before_notifications)
        self.assertEqual(exchange.staged_contract_version_id, staged.id)
        self.assertEqual(response.data["exchange"]["staged_contract_version_id"], str(staged.id))
        self.assertEqual(response.data["exchange"]["staged_update"]["id"], str(staged.id))
        snapshot = self.snapshot_data(staged)
        self.assertEqual(len(snapshot["sections"]), 2)
        self.assertEqual(snapshot["sections"][0]["content_html"], "<p>Payment is due on the 15th.</p>")
        self.assertEqual(snapshot["sections"][1]["content_html"], "<p>Provide monthly service.</p>")
        self.assertIn("<h2>Payment Terms</h2><p>Payment is due on the 15th.</p>", snapshot["editor_html"])
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["matched_by"], "id")
        self.assertFalse(snapshot["agreement_exchange_latest_update"]["fallback_used"])
        self.assertTrue(snapshot["agreement_exchange_latest_update"]["staged_for_agreement_exchange"])

    def test_send_staged_updated_version_hands_off_to_counterparty_and_notifies(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
            format="json",
        )
        staged = ContractVersion.objects.exclude(id=self.version.id).get()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/send-updated-version/",
            {"staged_version_id": str(staged.id), "full_content_html": "<h2>Payment Terms</h2><p>Payment is due on the 15th.</p>"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        self.version.refresh_from_db()
        staged.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(exchange.current_contract_version_id, staged.id)
        self.assertIsNone(exchange.staged_contract_version_id)
        self.assertEqual(staged.status, "sent")
        self.assertEqual(self.version.status, "superseded")
        notification = self.notification_for(self.counterparty)
        self.assertEqual(notification.title, "Updated version ready for review")
        self.assertEqual(notification.metadata["redirect_url"], f"/agreement-exchange/{exchange.id}")
        self.assertIn(self.contract.title, notification.message)
        self.assertIn(self.initiator.email, notification.message)
        self.assertIn("Action: Review changes", notification.message)

    def test_both_participants_see_same_current_version_after_send(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()

        stage_response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
            format="json",
        )
        self.assertEqual(stage_response.status_code, 200)
        staged = ContractVersion.objects.exclude(id=self.version.id).get()
        self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/send-updated-version/",
            {"staged_version_id": str(staged.id)},
            format="json",
        )
        exchange.refresh_from_db()
        new_version = exchange.current_contract_version

        initiator_response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        counterparty_response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(initiator_response.status_code, 200)
        self.assertEqual(counterparty_response.status_code, 200)
        self.assertEqual(initiator_response.data["current_contract"]["id"], str(new_version.id))
        self.assertEqual(counterparty_response.data["current_contract"]["id"], str(new_version.id))
        self.assertEqual(initiator_response.data["current_contract"]["version_label"], "v2")
        self.assertEqual(counterparty_response.data["current_contract"]["version_label"], "v2")
        self.assertEqual(initiator_response.data["exchange"]["current_contract_version_id"], str(new_version.id))
        self.assertEqual(counterparty_response.data["exchange"]["current_contract_version_id"], str(new_version.id))
        self.assertEqual(initiator_response.data["screen_state"], "initiator_waiting")
        self.assertEqual(counterparty_response.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_counterparty_cannot_sign_request_or_reject_before_initial_send(self):
        exchange, _ = self.create_exchange()
        original_version_count = ContractVersion.objects.count()
        original_exchange_version_id = exchange.current_contract_version_id

        sign_response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/sign/",
            {"typed_name": "Counter Party", "signature_text": "Counter Party"},
            format="json",
        )
        request_response = self.submit_request(exchange)
        reject_response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/reject/",
            {"reason": "Not acceptable."},
            format="json",
        )

        self.assertEqual(sign_response.status_code, 403)
        self.assertEqual(request_response.status_code, 409)
        self.assertEqual(reject_response.status_code, 403)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_DRAFT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(exchange.current_contract_version_id, original_exchange_version_id)
        self.assertEqual(AgreementExchangeRequest.objects.count(), 0)
        self.assertEqual(AgreementExchangeSignature.objects.count(), 0)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)

    def test_repeated_apply_does_not_duplicate_staged_version(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        original_version_count = ContractVersion.objects.count()

        first = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
            format="json",
        )
        second = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
            format="json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ContractVersion.objects.count(), original_version_count + 1)
        self.assertEqual(first.data["exchange"]["staged_update"]["id"], second.data["exchange"]["staged_update"]["id"])
        exchange.refresh_from_db()
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_EDITING)
        self.assertIsNotNone(exchange.staged_contract_version_id)

    def test_counterparty_cannot_respond_to_their_own_change_request(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        original_version_count = ContractVersion.objects.count()
        original_exchange_version_id = exchange.current_contract_version_id

        response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        change.refresh_from_db()
        exchange.refresh_from_db()
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_PENDING)
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(exchange.current_contract_version_id, original_exchange_version_id)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)

    def test_complete_turn_version_workflow_from_draft_to_v2(self):
        exchange, create_response = self.create_exchange()
        v1_id = exchange.current_contract_version_id
        original_version_count = ContractVersion.objects.count()

        self.assertEqual(exchange.status, AgreementExchange.STATUS_DRAFT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(create_response.data["screen_state"], "initiator_send_initial_version")
        self.assertEqual(create_response.data["available_actions"], ["send_initial_version"])
        self.assertEqual(create_response.data["current_contract"]["version_label"], "v1")

        send_response = self.send_initial(exchange)
        self.assertEqual(send_response.status_code, 200)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(exchange.current_contract_version_id, v1_id)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(send_response.data["current_contract"]["version_label"], "v1")

        counterparty_review = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")
        self.assertEqual(counterparty_review.status_code, 200)
        self.assertEqual(counterparty_review.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_review.data["available_actions"], ["sign", "request_change", "reject"])

        request_response = self.submit_request(exchange)
        self.assertEqual(request_response.status_code, 201)
        self.assertEqual(AgreementExchangeRequest.objects.count(), 1)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        change = AgreementExchangeRequest.objects.get()
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_PENDING)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(exchange.current_contract_version_id, v1_id)

        initiator_review = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        self.assertEqual(initiator_review.status_code, 200)
        self.assertEqual(initiator_review.data["screen_state"], "initiator_review_requested_change")
        self.assertEqual(initiator_review.data["available_actions"], ["apply_change", "edit_updated_version", "reject"])

        accept_response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {
                "decision": "accept",
                "final_text": "Payment is due on the 15th.",
                "initiator_response": "Accepted and sent back for review.",
            },
            format="json",
        )
        self.assertEqual(accept_response.status_code, 200)
        exchange.refresh_from_db()
        staged_v2 = ContractVersion.objects.exclude(id=v1_id).get()
        self.assertEqual(exchange.current_contract_version_id, v1_id)
        self.assertEqual(staged_v2.version_number, 2)
        self.assertEqual(staged_v2.previous_version_id, v1_id)
        self.assertEqual(staged_v2.status, "draft")
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_EDITING)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(ContractVersion.objects.count(), original_version_count + 1)
        self.assertEqual(exchange.staged_contract_version_id, staged_v2.id)
        self.assertEqual(accept_response.data["exchange"]["staged_contract_version_id"], str(staged_v2.id))
        self.assertEqual(accept_response.data["exchange"]["staged_update"]["id"], str(staged_v2.id))

        send_updated_response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/send-updated-version/",
            {"staged_version_id": str(staged_v2.id)},
            format="json",
        )
        self.assertEqual(send_updated_response.status_code, 200)
        exchange.refresh_from_db()
        v2 = exchange.current_contract_version
        self.assertEqual(v2.id, staged_v2.id)
        self.assertIsNone(exchange.staged_contract_version_id)
        self.assertEqual(exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)

        initiator_v2 = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        counterparty_v2 = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")
        self.assertEqual(initiator_v2.status_code, 200)
        self.assertEqual(counterparty_v2.status_code, 200)
        for response in [initiator_v2, counterparty_v2]:
            self.assertEqual(response.data["exchange"]["current_contract_version_id"], str(v2.id))
            self.assertEqual(response.data["current_contract"]["id"], str(v2.id))
            self.assertEqual(response.data["current_contract"]["version_label"], "v2")
        self.assertEqual(initiator_v2.data["screen_state"], "initiator_waiting")
        self.assertEqual(initiator_v2.data["available_actions"], [])
        self.assertEqual(counterparty_v2.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_v2.data["available_actions"], ["sign", "request_change", "reject"])

    def test_edit_updated_version_stages_editable_full_version_without_handoff(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        original_version_count = ContractVersion.objects.count()
        before_notifications = Notification.objects.filter(user=self.counterparty).count()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit", "final_text": "Payment is due on the 10th.", "initiator_response": "Edited before review."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        exchange.refresh_from_db()
        staged = ContractVersion.objects.exclude(id=self.version.id).get()
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_EDITED)
        self.assertEqual(change.pending_next_version_text, "Payment is due on the 10th.")
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_EDITING)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(exchange.current_contract_version_id, self.version.id)
        self.assertEqual(ContractVersion.objects.count(), original_version_count + 1)
        self.assertEqual(staged.version_number, 2)
        self.assertEqual(staged.previous_version, self.version)
        self.assertEqual(staged.status, "draft")
        self.assertEqual(response.data["exchange"]["screen_state"], "initiator_editing")
        self.assertEqual(response.data["exchange"]["staged_update"]["version_label"], "v2")
        snapshot = self.snapshot_data(staged)
        self.assertEqual(snapshot["sections"][0]["content_html"], "<p>Payment due on the 1st.</p>")
        self.assertIn("Payment due on the 1st.", snapshot["editor_html"])
        self.assertNotIn("Payment is due on the 10th.", snapshot["editor_html"])
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["application_status"], "manual_edit_required")
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["request_id"], str(change.id))
        self.assertTrue(snapshot["agreement_exchange_latest_update"]["staged_for_agreement_exchange"])
        self.assertEqual(Notification.objects.filter(user=self.counterparty).count(), before_notifications)

    def test_exchange_does_not_enter_initiator_editing_when_no_full_content_can_be_staged(self):
        empty_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        empty_version = make_version(
            empty_contract,
            self.initiator,
            content_snapshot=json.dumps({"content_html": "", "sections": []}),
            status="sent",
        )
        response = self.initiator_client.post(
            "/api/agreement-exchange/",
            {
                "contract_id": str(empty_contract.id),
                "contract_version_id": str(empty_version.id),
                "counterparty_email": self.counterparty.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        exchange = AgreementExchange.objects.get(id=response.data["exchange"]["id"])
        self.initiator_client.post(f"/api/agreement-exchange/{exchange.id}/send-initial/", {}, format="json")
        request_response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "payment",
                "target_section_title": "Payment Terms",
                "request_category": "payment_terms",
                "action_type": "replace_clause",
                "proposed_text": "Change payment due date.",
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 201)
        change = AgreementExchangeRequest.objects.get(exchange=exchange)

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "The current contract version has no full contract content to stage.")
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_REVIEW)
        self.assertIsNone(exchange.staged_contract_version_id)

    def test_edit_updated_version_uses_previous_full_content_when_current_snapshot_is_empty(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        empty_v2 = ContractVersion.objects.create(
            contract=self.contract,
            version_number=2,
            created_by=self.initiator,
            previous_version=self.version,
            content_snapshot=json.dumps({"content_html": "", "sections": []}),
            status="sent",
        )
        exchange.current_contract_version = empty_v2
        exchange.save(update_fields=["current_contract_version", "updated_at"])
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit", "initiator_response": "Manual edit from empty v2."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        staged = exchange.staged_contract_version
        snapshot = self.snapshot_data(staged)
        self.assertIn("Payment due on the 1st.", snapshot["editor_html"])
        self.assertNotEqual(snapshot.get("editor_html"), '{"content_html":"","sections":[]}')
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["request_id"], str(change.id))
        self.assertEqual(response.data["exchange"]["staged_update"]["content_html"], snapshot["editor_html"])

    def test_rebuild_staged_updated_version_restores_full_content_without_mutating_current(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit"},
            format="json",
        )
        exchange.refresh_from_db()
        staged = exchange.staged_contract_version
        original_current_snapshot = exchange.current_contract_version.content_snapshot
        ContractVersion.objects.filter(pk=staged.pk).update(content_snapshot=json.dumps({
            "content_html": "",
            "sections": [],
            "agreement_exchange_latest_update": {
                "request_id": str(change.id),
                "staged_for_agreement_exchange": True,
            },
            "agreement_exchange_updates": [{
                "request_id": str(change.id),
                "staged_for_agreement_exchange": True,
            }],
        }))

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/rebuild-staged-version/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        staged.refresh_from_db()
        snapshot = self.snapshot_data(staged)
        self.assertIn("Payment due on the 1st.", snapshot["editor_html"])
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["request_id"], str(change.id))
        self.assertEqual(exchange.current_contract_version.content_snapshot, original_current_snapshot)
        self.assertEqual(response.data["exchange"]["staged_update"]["content_html"], snapshot["editor_html"])

    def test_detail_auto_rebuilds_invalid_staged_version_for_initiator(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit", "initiator_response": "Preparing manual edit."},
            format="json",
        )
        exchange.refresh_from_db()
        staged = exchange.staged_contract_version
        staged_id = staged.id
        original_current_snapshot = exchange.current_contract_version.content_snapshot
        original_version_count = ContractVersion.objects.count()
        ContractVersion.objects.filter(pk=staged.pk).update(content_snapshot=json.dumps({
            "content_html": "",
            "sections": [],
            "agreement_exchange_latest_update": {
                "request_id": str(change.id),
                "staged_for_agreement_exchange": True,
            },
            "agreement_exchange_updates": [{
                "request_id": str(change.id),
                "staged_for_agreement_exchange": True,
            }],
        }))

        response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        staged.refresh_from_db()
        snapshot = self.snapshot_data(staged)
        self.assertEqual(exchange.staged_contract_version_id, staged_id)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(exchange.current_contract_version.content_snapshot, original_current_snapshot)
        self.assertEqual(response.data["screen_state"], "initiator_editing")
        self.assertEqual(response.data["available_actions"], ["save_staged_version", "send_updated_version", "reject"])
        self.assertEqual(response.data["staged_update"]["id"], str(staged_id))
        self.assertEqual(response.data["staged_update"]["content_html"], snapshot["editor_html"])
        self.assertIn("Payment due on the 1st.", snapshot["editor_html"])
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["request_id"], str(change.id))
        self.assertTrue(snapshot["agreement_exchange_latest_update"]["staged_for_agreement_exchange"])

    def test_send_updated_version_fails_clearly_without_request_context(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        staged = ContractVersion.objects.create(
            contract=self.contract,
            version_number=2,
            created_by=self.initiator,
            previous_version=self.version,
            content_snapshot=json.dumps({"editor_html": "<p>Edited contract.</p>", "sections": []}),
            status="draft",
        )
        exchange.staged_contract_version = staged
        exchange.status = AgreementExchange.STATUS_INITIATOR_EDITING
        exchange.current_actor = AgreementExchange.ACTOR_INITIATOR
        exchange.save(update_fields=["staged_contract_version", "status", "current_actor", "updated_at"])

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/send-updated-version/",
            {"staged_version_id": str(staged.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "The staged version is missing request context.")
        exchange.refresh_from_db()
        self.assertEqual(exchange.current_contract_version_id, self.version.id)
        self.assertEqual(exchange.staged_contract_version_id, staged.id)

    def test_staged_version_drives_send_actions_even_if_status_is_initiator_review(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit", "initiator_response": "Preparing manual edit."},
            format="json",
        )
        exchange.refresh_from_db()
        staged = exchange.staged_contract_version
        exchange.status = AgreementExchange.STATUS_INITIATOR_REVIEW
        exchange.save(update_fields=["status", "updated_at"])

        response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["screen_state"], "initiator_editing")
        self.assertEqual(response.data["exchange"]["staged_contract_version_id"], str(staged.id))
        self.assertEqual(response.data["staged_update"]["id"], str(staged.id))
        self.assertEqual(response.data["available_actions"], ["save_staged_version", "send_updated_version", "reject"])

    def test_save_staged_updated_version_updates_content_without_handoff(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit", "initiator_response": "Preparing manual edit."},
            format="json",
        )
        staged = ContractVersion.objects.exclude(id=self.version.id).get()
        before_notifications = Notification.objects.filter(user=self.counterparty).count()
        before_version_count = ContractVersion.objects.count()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/save-staged-version/",
            {
                "staged_version_id": str(staged.id),
                "full_content_html": "<h2>Payment Terms</h2><p>Payment is due on the 10th.</p><h2>Services</h2><p>Provide monthly service.</p>",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        staged.refresh_from_db()
        snapshot = self.snapshot_data(staged)
        self.assertEqual(exchange.current_contract_version_id, self.version.id)
        self.assertEqual(exchange.staged_contract_version_id, staged.id)
        self.assertEqual(exchange.status, AgreementExchange.STATUS_INITIATOR_EDITING)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(ContractVersion.objects.count(), before_version_count)
        self.assertEqual(staged.status, "draft")
        self.assertIn("Payment is due on the 10th.", snapshot["editor_html"])
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["request_id"], str(change.id))
        self.assertTrue(snapshot["agreement_exchange_latest_update"]["staged_saved"])
        self.assertFalse(snapshot["agreement_exchange_latest_update"]["sent_to_counterparty"])
        self.assertEqual(Notification.objects.filter(user=self.counterparty).count(), before_notifications)
        self.assertEqual(AgreementExchangeEvent.objects.filter(exchange=exchange, event_type="staged_update_saved").count(), 1)

    def test_initiator_accept_add_request_appends_to_target_section(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "services",
                "target_section_title": "Services",
                "request_category": "obligations",
                "action_type": "add_clause",
                "proposed_text": "Provider will deliver a monthly status report.",
                "reason": "Reporting cadence should be explicit.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        change = AgreementExchangeRequest.objects.get()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Provider will deliver a monthly status report."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        snapshot = self.snapshot_data(exchange.current_contract_version)
        self.assertEqual(len(snapshot["sections"]), 2)
        self.assertIn("Payment due on the 1st.", snapshot["sections"][0]["content_html"])
        self.assertIn("Provide monthly service.", snapshot["sections"][1]["content_html"])
        self.assertIn("Provider will deliver a monthly status report.", snapshot["sections"][1]["content_html"])
        self.assertIn("Payment due on the 1st.", snapshot["editor_html"])
        self.assertIn("Provider will deliver a monthly status report.", snapshot["editor_html"])
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["application_status"], "section_appended")

    def test_missing_target_section_uses_agreement_exchange_updates_fallback(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "missing-section",
                "target_section_title": "Missing Section",
                "request_category": "terms_and_conditions",
                "action_type": "replace_clause",
                "proposed_text": "Add this reviewed fallback language.",
                "reason": "The target could not be selected cleanly.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        change = AgreementExchangeRequest.objects.get()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Add this reviewed fallback language."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        snapshot = self.snapshot_data(exchange.current_contract_version)
        fallback = snapshot["sections"][-1]
        self.assertEqual(len(snapshot["sections"]), 3)
        self.assertEqual(snapshot["sections"][0]["content_html"], "<p>Payment due on the 1st.</p>")
        self.assertEqual(snapshot["sections"][1]["content_html"], "<p>Provide monthly service.</p>")
        self.assertIn("Payment due on the 1st.", snapshot["editor_html"])
        self.assertIn("Provide monthly service.", snapshot["editor_html"])
        self.assertEqual(fallback["name"], "Agreement Exchange Updates")
        self.assertTrue(fallback["agreement_exchange_fallback"])
        self.assertIn("Add this reviewed fallback language.", fallback["content_html"])
        self.assertTrue(snapshot["agreement_exchange_latest_update"]["fallback_used"])
        self.assertEqual(snapshot["agreement_exchange_latest_update"]["application_status"], "fallback_appended")

    def test_v3_preserves_full_contract_from_v2_and_changes_only_target_section(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        self.submit_request(exchange)
        first_change = AgreementExchangeRequest.objects.get()
        first_response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{first_change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)
        exchange.refresh_from_db()
        v2 = exchange.current_contract_version
        v2_snapshot = self.snapshot_data(v2)
        self.assertEqual(v2_snapshot["sections"][0]["content_html"], "<p>Payment is due on the 15th.</p>")
        self.assertEqual(v2_snapshot["sections"][1]["content_html"], "<p>Provide monthly service.</p>")

        request_response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "services",
                "target_section_title": "Services",
                "request_category": "obligations",
                "action_type": "replace_clause",
                "proposed_text": "Provide weekly service.",
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 201)
        second_change = AgreementExchangeRequest.objects.filter(exchange=exchange).order_by("created_at").last()

        second_response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{second_change.id}/respond/",
            {"decision": "accept", "final_text": "Provide weekly service."},
            format="json",
        )

        self.assertEqual(second_response.status_code, 200)
        exchange.refresh_from_db()
        v3 = exchange.current_contract_version
        snapshot = self.snapshot_data(v3)
        self.assertEqual(v3.version_number, 3)
        self.assertEqual(v3.previous_version_id, v2.id)
        self.assertEqual(exchange.current_contract_version_id, v3.id)
        self.assertEqual(len(snapshot["sections"]), 2)
        self.assertEqual(snapshot["sections"][0]["content_html"], "<p>Payment is due on the 15th.</p>")
        self.assertEqual(snapshot["sections"][1]["content_html"], "<p>Provide weekly service.</p>")
        self.assertIn("Payment is due on the 15th.", snapshot["editor_html"])
        self.assertIn("Provide weekly service.", snapshot["editor_html"])
        self.assertNotIn("Provide monthly service.", snapshot["sections"][1]["content_html"])

    def test_replace_with_title_only_sections_preserves_full_original_body(self):
        full_editor_html = (
            "<h2>Introduction</h2><p>Intro body unique alpha remains in the contract.</p>"
            "<h2>Scope of Services</h2><p>Scope body unique beta remains unchanged.</p>"
            "<h2>Payment Terms</h2><p>Original payment body unique gamma should not be the only body.</p>"
            "<h2>Termination</h2><p>Termination body unique delta remains unchanged.</p>"
        )
        snapshot = json.dumps({
            "sections": [
                {"id": "intro", "number": 1, "name": "Introduction"},
                {"id": "scope", "number": 2, "name": "Scope of Services"},
                {"id": "payment", "number": 3, "name": "Payment Terms"},
                {"id": "termination", "number": 4, "name": "Termination"},
            ],
            "editor_html": full_editor_html,
            "body": "Intro body unique alpha remains in the contract. Scope body unique beta remains unchanged. Original payment body unique gamma should not be the only body. Termination body unique delta remains unchanged.",
            "text": "Intro body unique alpha remains in the contract. Scope body unique beta remains unchanged. Original payment body unique gamma should not be the only body. Termination body unique delta remains unchanged.",
        })
        contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        version = make_version(contract, self.initiator, content_snapshot=snapshot, status="sent")
        create_response = self.initiator_client.post(
            "/api/agreement-exchange/",
            {
                "contract_id": str(contract.id),
                "contract_version_id": str(version.id),
                "counterparty_email": self.counterparty.email,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        exchange = AgreementExchange.objects.get(id=create_response.data["exchange"]["id"])
        self.send_initial(exchange)

        request_response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "payment",
                "target_section_title": "Payment Terms",
                "request_category": "payment_terms",
                "action_type": "replace_clause",
                "proposed_text": "Updated payment terms unique epsilon are accepted.",
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 201)
        change = AgreementExchangeRequest.objects.get(exchange=exchange)

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Updated payment terms unique epsilon are accepted."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        new_version = exchange.current_contract_version
        updated = self.snapshot_data(new_version)
        self.assertEqual(new_version.version_number, 2)
        self.assertEqual(exchange.current_contract_version_id, new_version.id)
        self.assertIn("Intro body unique alpha remains in the contract.", updated["editor_html"])
        self.assertIn("Scope body unique beta remains unchanged.", updated["editor_html"])
        self.assertIn("Termination body unique delta remains unchanged.", updated["editor_html"])
        self.assertIn("Updated payment terms unique epsilon are accepted.", updated["editor_html"])
        self.assertIn("Intro body unique alpha remains in the contract.", updated["body"])
        self.assertIn("Scope body unique beta remains unchanged.", updated["text"])
        self.assertEqual(len(updated["sections"]), 5)
        self.assertEqual(updated["sections"][-1]["name"], "Agreement Exchange Updates")
        self.assertTrue(updated["agreement_exchange_latest_update"]["fallback_used"])
        self.assertNotEqual(
            updated["editor_html"],
            "<h2>Introduction</h2><h2>Scope of Services</h2><h2>Payment Terms</h2><p>Updated payment terms unique epsilon are accepted.</p><h2>Termination</h2>",
        )

    def test_v3_title_only_sections_preserve_full_body_from_v2(self):
        full_editor_html = (
            "<h2>Introduction</h2><p>Intro body unique one persists.</p>"
            "<h2>Scope of Services</h2><p>Scope body unique two persists.</p>"
            "<h2>Payment Terms</h2><p>Payment body unique three persists.</p>"
            "<h2>Termination</h2><p>Termination body unique four persists.</p>"
        )
        snapshot = json.dumps({
            "sections": [
                {"id": "intro", "number": 1, "name": "Introduction"},
                {"id": "scope", "number": 2, "name": "Scope of Services"},
                {"id": "payment", "number": 3, "name": "Payment Terms"},
                {"id": "termination", "number": 4, "name": "Termination"},
            ],
            "editor_html": full_editor_html,
            "body": "Intro body unique one persists. Scope body unique two persists. Payment body unique three persists. Termination body unique four persists.",
            "text": "Intro body unique one persists. Scope body unique two persists. Payment body unique three persists. Termination body unique four persists.",
        })
        contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        version = make_version(contract, self.initiator, content_snapshot=snapshot, status="sent")
        create_response = self.initiator_client.post(
            "/api/agreement-exchange/",
            {
                "contract_id": str(contract.id),
                "contract_version_id": str(version.id),
                "counterparty_email": self.counterparty.email,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        exchange = AgreementExchange.objects.get(id=create_response.data["exchange"]["id"])
        self.send_initial(exchange)

        first_request = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "payment",
                "target_section_title": "Payment Terms",
                "request_category": "payment_terms",
                "action_type": "replace_clause",
                "proposed_text": "First accepted update unique five.",
            },
            format="json",
        )
        self.assertEqual(first_request.status_code, 201)
        first_change = AgreementExchangeRequest.objects.get(exchange=exchange)
        first_response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{first_change.id}/respond/",
            {"decision": "accept", "final_text": "First accepted update unique five."},
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)
        exchange.refresh_from_db()
        v2 = exchange.current_contract_version

        second_request = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {
                "target_section_id": "scope",
                "target_section_title": "Scope of Services",
                "request_category": "obligations",
                "action_type": "add_clause",
                "proposed_text": "Second accepted update unique six.",
            },
            format="json",
        )
        self.assertEqual(second_request.status_code, 201)
        second_change = AgreementExchangeRequest.objects.filter(exchange=exchange).order_by("created_at").last()
        second_response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{second_change.id}/respond/",
            {"decision": "accept", "final_text": "Second accepted update unique six."},
            format="json",
        )

        self.assertEqual(second_response.status_code, 200)
        exchange.refresh_from_db()
        v3 = exchange.current_contract_version
        updated = self.snapshot_data(v3)
        self.assertEqual(v3.version_number, 3)
        self.assertEqual(v3.previous_version_id, v2.id)
        self.assertIn("Intro body unique one persists.", updated["editor_html"])
        self.assertIn("Scope body unique two persists.", updated["editor_html"])
        self.assertIn("Payment body unique three persists.", updated["editor_html"])
        self.assertIn("Termination body unique four persists.", updated["editor_html"])
        self.assertIn("First accepted update unique five.", updated["editor_html"])
        self.assertIn("Second accepted update unique six.", updated["editor_html"])
        self.assertIn("Intro body unique one persists.", updated["body"])
        self.assertIn("Termination body unique four persists.", updated["text"])
        self.assertEqual(exchange.current_contract_version_id, v3.id)

    def test_initiator_accept_respects_exchange_local_version_cap(self):
        exchange = self.make_rejected_exchange_at_v3(reject=False)
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.filter(exchange=exchange).order_by("created_at").last()
        original_version_count = ContractVersion.objects.count()
        original_exchange_version_id = exchange.current_contract_version_id

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the final date."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        change.refresh_from_db()
        exchange.refresh_from_db()
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_PENDING)
        self.assertEqual(exchange.current_contract_version_id, original_exchange_version_id)

    def test_counterparty_sign_works(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        original_version_count = ContractVersion.objects.count()
        signed_version_id = exchange.current_contract_version_id

        response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/sign/",
            {"typed_name": "Counter Party", "signature_text": "Counter Party"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        self.version.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_SIGNED)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_NONE)
        self.assertEqual(AgreementExchangeSignature.objects.count(), 1)
        signature = AgreementExchangeSignature.objects.get()
        self.assertEqual(signature.signed_version_id, signed_version_id)
        self.assertEqual(self.version.status, "signed")
        self.assertEqual(self.contract.status, "signed")
        self.assertNotEqual(self.contract.status, "active")
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="signed").count(), 1)
        self.assertEqual(response.data["exchange"]["screen_state"], "signed")
        self.assertEqual(response.data["exchange"]["available_actions"], [])
        notification = self.notification_for(self.initiator)
        self.assertEqual(notification.title, "Contract signed")
        self.assertEqual(notification.metadata["redirect_url"], f"/lifecycle?contract={self.contract.id}")
        self.assertIn(self.contract.title, notification.message)
        self.assertIn(self.counterparty.email, notification.message)
        self.assertIn("Action: Open Agreement Timeline", notification.message)

        dashboard_response = self.counterparty_client.get("/api/contracts/")
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_contract = next(item for item in dashboard_response.data if item["id"] == str(self.contract.id))
        self.assertEqual(dashboard_contract["display_status"], "signed")
        self.assertEqual(dashboard_contract["display_status_label"], "Signed")
        self.assertEqual(dashboard_contract["latest_exchange_status"], AgreementExchange.STATUS_SIGNED)
        self.assertEqual(dashboard_contract["signed_version_id"], str(signed_version_id))
        self.assertTrue(dashboard_contract["lifecycle_ready"])
        self.assertEqual(dashboard_contract["primary_action"], "open_lifecycle")
        self.assertEqual(dashboard_contract["primary_action_url"], f"/lifecycle?contract={self.contract.id}")

        open_response = self.counterparty_client.post(
            "/api/ai/workflows/for-contract/",
            {"contract_id": str(self.contract.id)},
            format="json",
        )
        self.assertEqual(open_response.status_code, 200)
        self.assertEqual(open_response.data["redirect_url"], f"/lifecycle?contract={self.contract.id}")
        self.assertEqual(open_response.data["primary_action"], "open_lifecycle")
        self.assertNotIn("exchange_id", open_response.data)
        self.assertEqual(AgreementExchange.objects.count(), 1)

    def test_reject_exchange_works(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)

        response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/reject/",
            {"reason": "Not acceptable."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_REJECTED)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_NONE)
        self.assertEqual(response.data["screen_state"], "rejected")
        self.assertEqual(response.data["available_actions"], [])
        initiator_detail = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        counterparty_detail = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")
        self.assertEqual(initiator_detail.data["available_actions"], [])
        self.assertEqual(counterparty_detail.data["available_actions"], [])
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="exchange_rejected").count(), 1)
        notification = self.notification_for(self.initiator)
        self.assertEqual(notification.title, "Contract rejected")
        self.assertEqual(notification.metadata["redirect_url"], f"/agreement-exchange/{exchange.id}")
        self.assertIn(self.contract.title, notification.message)
        self.assertIn(self.counterparty.email, notification.message)
        self.assertIn("Action: View negotiation", notification.message)

    def test_rejected_exchange_can_be_restarted_by_initiator(self):
        old_exchange = self.make_rejected_exchange_at_v3()
        old_version_id = old_exchange.current_contract_version_id
        old_event_count = old_exchange.events.count()
        old_request_count = old_exchange.requests.count()
        original_version_count = ContractVersion.objects.count()

        response = self.restart_exchange(old_exchange)

        self.assertEqual(response.status_code, 201)
        old_exchange.refresh_from_db()
        new_exchange = AgreementExchange.objects.get(id=response.data["exchange_id"])
        self.assertNotEqual(new_exchange.id, old_exchange.id)
        self.assertEqual(old_exchange.status, AgreementExchange.STATUS_REJECTED)
        self.assertEqual(old_exchange.current_actor, AgreementExchange.ACTOR_NONE)
        self.assertEqual(old_exchange.current_contract_version_id, old_version_id)
        self.assertEqual(old_exchange.requests.count(), old_request_count)
        self.assertEqual(old_exchange.events.count(), old_event_count + 1)
        self.assertEqual(new_exchange.restarted_from_exchange, old_exchange)
        self.assertEqual(new_exchange.source_contract_version_id, old_version_id)
        self.assertEqual(new_exchange.current_contract_version_id, old_version_id)
        self.assertEqual(new_exchange.status, AgreementExchange.STATUS_DRAFT)
        self.assertEqual(new_exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(response.data["redirect_path"], f"/agreement-exchange/{new_exchange.id}")
        self.assertEqual(response.data["current_contract"]["version_label"], "v1")
        self.assertEqual(AgreementExchangeEvent.objects.filter(exchange=old_exchange, event_type="exchange_restarted").count(), 1)
        self.assertEqual(AgreementExchangeEvent.objects.filter(exchange=new_exchange, event_type="exchange_restarted_from_rejected").count(), 1)
        self.assertEqual(AgreementExchangeEvent.objects.filter(exchange=new_exchange, event_type="initial_version_sent").count(), 0)

    def test_counterparty_cannot_restart_rejected_exchange(self):
        old_exchange = self.make_rejected_exchange_at_v3()
        original_exchange_count = AgreementExchange.objects.count()

        response = self.restart_exchange(old_exchange, client=self.counterparty_client)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(AgreementExchange.objects.count(), original_exchange_count)

    def test_non_rejected_exchange_cannot_restart(self):
        exchange, _ = self.create_exchange()

        response = self.restart_exchange(exchange)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(AgreementExchange.objects.count(), 1)

    def test_restart_requires_source_version_from_exchange_history(self):
        old_exchange = self.make_rejected_exchange_at_v3()
        other_contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        other_version = make_version(other_contract, self.initiator, content_snapshot=self.snapshot, status="sent")

        response = self.restart_exchange(old_exchange, source_version=other_version)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AgreementExchange.objects.count(), 1)

    def test_restart_does_not_notify_counterparty_before_initial_send(self):
        old_exchange = self.make_rejected_exchange_at_v3()
        before_count = Notification.objects.filter(user=self.counterparty).count()

        response = self.restart_exchange(old_exchange)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Notification.objects.filter(user=self.counterparty).count(), before_count)

    def test_restarted_exchange_can_send_initial_version(self):
        old_exchange = self.make_rejected_exchange_at_v3()
        response = self.restart_exchange(old_exchange)
        new_exchange = AgreementExchange.objects.get(id=response.data["exchange_id"])
        original_version_count = ContractVersion.objects.count()

        detail = self.initiator_client.get(f"/api/agreement-exchange/{new_exchange.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["screen_state"], "initiator_send_initial_version")
        self.assertEqual(detail.data["available_actions"], ["send_initial_version"])
        self.assertEqual(detail.data["current_contract"]["version_label"], "v1")
        counterparty_detail = self.counterparty_client.get(f"/api/agreement-exchange/{new_exchange.id}/")
        self.assertEqual(counterparty_detail.status_code, 403)

        send_response = self.send_initial(new_exchange)

        self.assertEqual(send_response.status_code, 200)
        new_exchange.refresh_from_db()
        self.assertEqual(new_exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(new_exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(new_exchange.current_contract_version_id, new_exchange.source_contract_version_id)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(send_response.data["current_contract"]["version_label"], "v1")
        for _ in range(2):
            counterparty_detail = self.counterparty_client.get(f"/api/agreement-exchange/{new_exchange.id}/")
            self.assertEqual(counterparty_detail.data["screen_state"], "counterparty_review")
            self.assertEqual(counterparty_detail.data["available_actions"], ["sign", "request_change", "reject"])

    def test_restarted_exchange_version_cap_is_independent(self):
        old_exchange = self.make_rejected_exchange_at_v3()
        response = self.restart_exchange(old_exchange)
        new_exchange = AgreementExchange.objects.get(id=response.data["exchange_id"])
        self.send_initial(new_exchange)
        original_version_count = ContractVersion.objects.count()

        self.submit_request(new_exchange)
        change = AgreementExchangeRequest.objects.filter(exchange=new_exchange).order_by("created_at").last()
        accept_response = self.initiator_client.post(
            f"/api/agreement-exchange/{new_exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Restarted payment date is the 25th."},
            format="json",
        )

        self.assertEqual(accept_response.status_code, 200)
        new_exchange.refresh_from_db()
        self.assertEqual(ContractVersion.objects.count(), original_version_count + 1)
        self.assertEqual(new_exchange.current_contract_version.version_number, 4)
        self.assertEqual(accept_response.data["exchange"]["current_contract"]["version_label"], "v2")
        old_exchange.refresh_from_db()
        self.assertEqual(old_exchange.status, AgreementExchange.STATUS_REJECTED)

    def test_request_creation_does_not_mutate_contract_or_version_or_lifecycle(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)
        original_contract_status = self.contract.status
        original_contract_state = self.contract.state
        original_snapshot = self.version.content_snapshot
        original_version_count = ContractVersion.objects.count()
        self.assertEqual(ContractObligation.objects.count(), 0)
        self.assertEqual(ContractServiceObligation.objects.count(), 0)

        response = self.submit_request(exchange)

        self.assertEqual(response.status_code, 201)
        self.contract.refresh_from_db()
        self.version.refresh_from_db()
        self.assertEqual(self.contract.status, original_contract_status)
        self.assertEqual(self.contract.state, original_contract_state)
        self.assertEqual(self.version.content_snapshot, original_snapshot)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(ContractObligation.objects.count(), 0)
        self.assertEqual(ContractServiceObligation.objects.count(), 0)

    def test_missing_proposed_text_is_rejected(self):
        exchange, _ = self.create_exchange()
        self.send_initial(exchange)

        response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/",
            {"request_category": "payment_terms", "action_type": "replace_clause"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(AgreementExchangeRequest.objects.count(), 0)

    def test_templates_endpoint_returns_categories(self):
        response = self.counterparty_client.get("/api/agreement-exchange/templates/")

        self.assertEqual(response.status_code, 200)
        categories = response.data["categories"]
        self.assertIn("recitals_background", categories)
        self.assertIn("terms_and_conditions", categories)
        self.assertIn("obligations", categories)
        self.assertIn("payment_terms", categories)
        self.assertIn("confidentiality", categories)
        self.assertIn("intellectual_property", categories)
        self.assertIn("termination", categories)
        self.assertIn("dispute_resolution", categories)
        self.assertIn("governing_law", categories)
        self.assertNotIn("parties", categories)


class AgreementExchangeFromWorkflowAPITests(TestCase):
    def setUp(self):
        from backend.ai.models import WorkflowState

        self.initiator = make_user("ae_fw_initiator", "ae-fw-initiator@example.com")
        self.counterparty = make_user("ae_fw_counterparty", "ae-fw-counterparty@example.com")
        self.client = authed_client(self.initiator)
        self.counterparty_client = authed_client(self.counterparty)
        self.contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        self.snapshot = json.dumps({
            "sections": [{"id": "payment", "number": 1, "name": "Payment Terms"}],
            "editor_html": "<h2>Payment Terms</h2><p>Payment due on the 1st.</p>",
        })
        self.version = make_version(self.contract, self.initiator, content_snapshot=self.snapshot, status="sent")
        self.workflow = WorkflowState.objects.create(
            user=self.initiator,
            contract=self.contract,
            created_version=self.version,
            source_label="Service Agreement",
            counterparty_email=self.counterparty.email,
            sent_to_counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            current_state=WorkflowState.STATE_SENT_TO_COUNTERPARTY,
            completed_states=[WorkflowState.STATE_UPLOADED, WorkflowState.STATE_VERSION_CREATED, WorkflowState.STATE_SENT_TO_COUNTERPARTY],
            pending_states=[WorkflowState.STATE_COUNTERPARTY_VIEWED],
            state_timestamps={},
        )

    def post_from_workflow(self):
        return self.client.post(
            "/api/agreement-exchange/from-workflow/",
            {"workflow_id": str(self.workflow.id)},
            format="json",
        )

    def test_from_workflow_creates_exchange(self):
        response = self.post_from_workflow()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AgreementExchange.objects.count(), 1)
        exchange = AgreementExchange.objects.get()
        self.assertEqual(exchange.contract, self.contract)
        self.assertEqual(exchange.current_contract_version, self.version)
        self.assertEqual(exchange.initiator, self.initiator)
        self.assertEqual(exchange.counterparty_email, self.counterparty.email)
        self.assertEqual(exchange.counterparty_user, self.counterparty)
        self.assertEqual(exchange.status, AgreementExchange.STATUS_DRAFT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_INITIATOR)
        detail_response = self.client.get(f"/api/agreement-exchange/{exchange.id}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["screen_state"], "initiator_send_initial_version")
        self.assertEqual(detail_response.data["available_actions"], ["send_initial_version"])

    def test_from_workflow_reuses_existing_exchange(self):
        existing = AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_DRAFT,
            current_actor=AgreementExchange.ACTOR_INITIATOR,
        )

        response = self.post_from_workflow()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AgreementExchange.objects.count(), 1)
        self.assertEqual(response.data["exchange_id"], str(existing.id))

    def test_from_workflow_reuses_latest_existing_exchange_when_duplicates_exist(self):
        AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
            current_actor=AgreementExchange.ACTOR_COUNTERPARTY,
        )
        latest = AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_INITIATOR_REVIEW,
            current_actor=AgreementExchange.ACTOR_INITIATOR,
        )
        AgreementExchangeRequest.objects.create(
            exchange=latest,
            requested_by_user=self.counterparty,
            requested_by_email=self.counterparty.email,
            target_section_id="payment",
            target_section_title="Payment Terms",
            request_category="payment_terms",
            action_type="replace_clause",
            template_key="payment_terms",
            proposed_text="Change payment due date to the 15th.",
            status=AgreementExchangeRequest.STATUS_PENDING,
        )

        response = self.post_from_workflow()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AgreementExchange.objects.count(), 2)
        self.assertEqual(response.data["exchange_id"], str(latest.id))
        detail_response = self.client.get(f"/api/agreement-exchange/{response.data['exchange_id']}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["screen_state"], "initiator_review_requested_change")
        self.assertEqual(detail_response.data["requests"][0]["proposed_text"], "Change payment due date to the 15th.")

    def test_from_workflow_prefers_active_pending_exchange_over_newer_draft_duplicate(self):
        active = AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            source_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
            current_actor=AgreementExchange.ACTOR_COUNTERPARTY,
        )
        AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            source_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_DRAFT,
            current_actor=AgreementExchange.ACTOR_INITIATOR,
        )

        response = self.post_from_workflow()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AgreementExchange.objects.count(), 2)
        self.assertEqual(response.data["exchange_id"], str(active.id))
        detail_response = self.counterparty_client.get(f"/api/agreement-exchange/{response.data['exchange_id']}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["screen_state"], "counterparty_review")
        self.assertEqual(detail_response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_from_workflow_response_includes_exchange_id_and_redirect_url(self):
        response = self.post_from_workflow()

        self.assertEqual(response.status_code, 200)
        self.assertIn("exchange_id", response.data)
        self.assertEqual(response.data["redirect_url"], f"/agreement-exchange/{response.data['exchange_id']}")

    def test_from_workflow_current_contract_version_is_populated(self):
        response = self.post_from_workflow()
        exchange = AgreementExchange.objects.get(id=response.data["exchange_id"])

        self.assertEqual(exchange.current_contract_version_id, self.version.id)

    def test_from_workflow_does_not_mutate_contract_version_or_lifecycle(self):
        original_snapshot = self.version.content_snapshot
        original_version_count = ContractVersion.objects.count()
        self.assertEqual(ContractObligation.objects.count(), 0)
        self.assertEqual(ContractServiceObligation.objects.count(), 0)

        response = self.post_from_workflow()

        self.assertEqual(response.status_code, 200)
        self.version.refresh_from_db()
        self.assertEqual(self.version.content_snapshot, original_snapshot)
        self.assertEqual(ContractVersion.objects.count(), original_version_count)
        self.assertEqual(ContractObligation.objects.count(), 0)
        self.assertEqual(ContractServiceObligation.objects.count(), 0)
