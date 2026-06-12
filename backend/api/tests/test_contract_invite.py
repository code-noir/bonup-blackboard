from unittest.mock import ANY, Mock, patch

from django.test import TestCase, override_settings

from backend.activity.models import ContractActivity
from backend.ai.models import WorkflowShareLink, WorkflowState
from backend.contracts.models import ContractVersion

from .helpers import authed_client, make_contract, make_user, make_version


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@bonup.cloud",
    RESEND_API_KEY="test-resend-api-key",
    RESEND_API_URL="https://api.resend.com/emails",
    RESEND_TIMEOUT=10,
)
class ContractInviteTests(TestCase):
    def setUp(self):
        self.initiator = make_user("invite_initiator", "invite-initiator@example.com")
        self.counterparty = make_user("invite_counterparty", "invite-counterparty@example.com")
        self.client = authed_client(self.initiator)
        self.contract = make_contract(self.initiator, counterparty_email=self.counterparty.email)
        self.version = make_version(self.contract, self.initiator, content_snapshot="Prepared contract content.")
        self.contract.state = "prepared"
        self.contract.status = "draft"
        self.contract.save(update_fields=["state", "status"])

    @patch("backend.core.email_backends.requests.post")
    def test_contract_invite_sends_email_and_creates_workflow(self, mock_post):
        resend_response = Mock()
        resend_response.raise_for_status.return_value = None
        mock_post.return_value = resend_response

        response = self.client.post(
            f"/api/contracts/{self.contract.id}/invite/",
            {"counterparty_email": self.counterparty.email},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["email_sent"])
        self.assertIn("invite_url", response.data)
        self.assertEqual(response.data["counterparty_email"], self.counterparty.email)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.state, "sent")
        self.assertEqual(self.contract.status, "sent")
        mock_post.assert_called_once_with(
            "https://api.resend.com/emails",
            headers={
                "Authorization": "Bearer test-resend-api-key",
                "Content-Type": "application/json",
            },
            json={
                "from": "noreply@bonup.cloud",
                "to": [self.counterparty.email],
                "subject": f"bonUP contract invite: {self.contract.title or 'Agreement'}",
                "text": ANY,
            },
            timeout=10,
        )
        self.assertEqual(WorkflowState.objects.count(), 1)
        self.assertEqual(WorkflowShareLink.objects.count(), 1)
        self.assertTrue(
            ContractActivity.objects.filter(
                contract=self.contract,
                activity_type="contract_updated",
                metadata__workflow_id=response.data["workflow_id"],
                metadata__email_sent=True,
            ).exists()
        )

    @patch("backend.core.email_backends.requests.post", side_effect=Exception("smtp down"))
    def test_contract_invite_rolls_back_when_email_fails(self, mock_post):
        response = self.client.post(
            f"/api/contracts/{self.contract.id}/invite/",
            {"counterparty_email": self.counterparty.email},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.state, "prepared")
        self.assertEqual(self.contract.status, "draft")
        self.assertEqual(WorkflowState.objects.count(), 0)
        self.assertEqual(WorkflowShareLink.objects.count(), 0)
        mock_post.assert_called_once_with(
            "https://api.resend.com/emails",
            headers={
                "Authorization": "Bearer test-resend-api-key",
                "Content-Type": "application/json",
            },
            json={
                "from": "noreply@bonup.cloud",
                "to": [self.counterparty.email],
                "subject": f"bonUP contract invite: {self.contract.title or 'Agreement'}",
                "text": ANY,
            },
            timeout=10,
        )
        self.assertFalse(
            ContractActivity.objects.filter(contract=self.contract, activity_type="contract_updated").exists()
        )
