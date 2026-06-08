import json

from django.test import TestCase

from backend.agreement_exchange.models import (
    AgreementExchange,
    AgreementExchangeEvent,
    AgreementExchangeRequest,
    AgreementExchangeSignature,
)
from backend.api.tests.helpers import authed_client, make_contract, make_user, make_version
from backend.contracts.models import ContractObligation, ContractServiceObligation, ContractVersion


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

    def test_create_exchange(self):
        exchange, response = self.create_exchange()

        self.assertEqual(exchange.status, AgreementExchange.STATUS_COUNTERPARTY_REVIEW)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(response.data["viewer_role"], "initiator")
        self.assertEqual(response.data["screen_state"], "initiator_waiting")
        self.assertEqual(response.data["current_contract"]["version_label"], "v1")
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="exchange_sent").count(), 1)

    def test_detail_returns_viewer_role_screen_state_and_actions(self):
        exchange, _ = self.create_exchange()

        initiator_response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")
        counterparty_response = self.counterparty_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(initiator_response.status_code, 200)
        self.assertEqual(initiator_response.data["viewer_role"], "initiator")
        self.assertEqual(initiator_response.data["screen_state"], "initiator_waiting")
        self.assertEqual(counterparty_response.data["viewer_role"], "counterparty")
        self.assertEqual(counterparty_response.data["screen_state"], "counterparty_review")
        self.assertEqual(counterparty_response.data["available_actions"], ["sign", "request_change", "reject"])
        self.assertEqual(counterparty_response.data["current_contract"]["sections"][0]["id"], "payment")

    def test_counterparty_marks_viewed(self):
        exchange, _ = self.create_exchange()

        response = self.counterparty_client.post(f"/api/agreement-exchange/{exchange.id}/viewed/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(AgreementExchangeEvent.objects.filter(exchange=exchange, event_type="exchange_viewed").count(), 1)

    def test_submit_request_saves_and_changes_current_actor_to_initiator(self):
        exchange, _ = self.create_exchange()

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
        event = AgreementExchangeEvent.objects.get(event_type="counterparty_request_created")
        self.assertEqual(event.metadata["redirect_url"], f"/agreement-exchange/{exchange.id}")

    def test_initiator_sees_request(self):
        exchange, _ = self.create_exchange()
        self.submit_request(exchange)

        response = self.initiator_client.get(f"/api/agreement-exchange/{exchange.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["screen_state"], "initiator_review_requested_change")
        self.assertEqual(response.data["available_actions"], ["accept_request", "edit_request", "reject_request"])
        self.assertEqual(response.data["requests"][0]["proposed_text"], "Change payment due date to the 15th.")

    def test_initiator_reject_request_works(self):
        exchange, _ = self.create_exchange()
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

    def test_initiator_accept_creates_next_contract_version_and_updates_exchange_pointer(self):
        exchange, _ = self.create_exchange()
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        original_version_count = ContractVersion.objects.count()
        original_snapshot = self.version.content_snapshot

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {
                "decision": "accept",
                "final_text": "Payment is due on the 15th.",
                "initiator_response": "Accepted and sent back for review.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        exchange.refresh_from_db()
        self.version.refresh_from_db()
        new_version = exchange.current_contract_version
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_ACCEPTED)
        self.assertEqual(change.pending_next_version_text, "Payment is due on the 15th.")
        self.assertEqual(exchange.status, AgreementExchange.STATUS_UPDATED_VERSION_SENT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(ContractVersion.objects.count(), original_version_count + 1)
        self.assertEqual(new_version.version_number, 2)
        self.assertEqual(new_version.previous_version, self.version)
        self.assertEqual(new_version.status, "sent")
        self.assertEqual(self.version.content_snapshot, original_snapshot)
        self.assertEqual(self.version.status, "superseded")
        self.assertEqual(response.data["exchange"]["exchange"]["current_contract_version_id"], str(new_version.id))
        self.assertEqual(response.data["exchange"]["current_contract"]["version_label"], "v2")
        self.assertIn("Payment is due on the 15th.", new_version.content_snapshot)

    def test_both_participants_see_same_current_version_after_accept(self):
        exchange, _ = self.create_exchange()
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(counterparty_response.data["screen_state"], "counterparty_review_updated_version")
        self.assertEqual(counterparty_response.data["available_actions"], ["sign", "request_change", "reject"])

    def test_initiator_edit_creates_next_contract_version_and_updates_exchange_pointer(self):
        exchange, _ = self.create_exchange()
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        original_version_count = ContractVersion.objects.count()

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "edit", "final_text": "Payment is due on the 10th.", "initiator_response": "Edited before sending."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        exchange.refresh_from_db()
        new_version = exchange.current_contract_version
        self.assertEqual(change.status, AgreementExchangeRequest.STATUS_EDITED)
        self.assertEqual(exchange.status, AgreementExchange.STATUS_UPDATED_VERSION_SENT)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_COUNTERPARTY)
        self.assertEqual(ContractVersion.objects.count(), original_version_count + 1)
        self.assertEqual(new_version.version_number, 2)
        self.assertEqual(new_version.previous_version, self.version)
        self.assertEqual(response.data["exchange"]["screen_state"], "initiator_waiting")
        self.assertEqual(response.data["exchange"]["current_contract"]["version_label"], "v2")
        self.assertIn("Payment is due on the 10th.", new_version.content_snapshot)

    def test_initiator_accept_respects_contract_version_cap(self):
        exchange, _ = self.create_exchange()
        make_version(self.contract, self.initiator, content_snapshot=self.snapshot, status="sent")
        make_version(self.contract, self.initiator, content_snapshot=self.snapshot, status="sent")
        self.submit_request(exchange)
        change = AgreementExchangeRequest.objects.get()
        original_version_count = ContractVersion.objects.count()
        original_exchange_version_id = exchange.current_contract_version_id

        response = self.initiator_client.post(
            f"/api/agreement-exchange/{exchange.id}/requests/{change.id}/respond/",
            {"decision": "accept", "final_text": "Payment is due on the 15th."},
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

        response = self.counterparty_client.post(
            f"/api/agreement-exchange/{exchange.id}/sign/",
            {"typed_name": "Counter Party", "signature_text": "Counter Party"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, AgreementExchange.STATUS_SIGNED)
        self.assertEqual(exchange.current_actor, AgreementExchange.ACTOR_NONE)
        self.assertEqual(AgreementExchangeSignature.objects.count(), 1)
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="signed").count(), 1)
        self.assertEqual(response.data["exchange"]["screen_state"], "signed")

    def test_reject_exchange_works(self):
        exchange, _ = self.create_exchange()

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
        self.assertEqual(AgreementExchangeEvent.objects.filter(event_type="exchange_rejected").count(), 1)

    def test_request_creation_does_not_mutate_contract_or_version_or_lifecycle(self):
        exchange, _ = self.create_exchange()
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

    def test_from_workflow_reuses_existing_exchange(self):
        existing = AgreementExchange.objects.create(
            contract=self.contract,
            current_contract_version=self.version,
            initiator=self.initiator,
            counterparty_email=self.counterparty.email,
            counterparty_user=self.counterparty,
            status=AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
            current_actor=AgreementExchange.ACTOR_COUNTERPARTY,
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
