from django.test import TestCase

from backend.ai.models import WorkflowState
from backend.api.tests.helpers import authed_client, make_contract, make_user, make_version


class WorkflowForContractTests(TestCase):
    endpoint = "/api/ai/workflows/for-contract/"

    def setUp(self):
        self.initiator = make_user("initiator", "initiator@example.com")
        self.counterparty = make_user("counterparty", "counterparty@example.com")
        self.other_user = make_user("other", "other@example.com")

    def make_prepared_contract(self):
        contract = make_contract(self.initiator, "counterparty@example.com")
        contract.title = "Prepared Lawn Agreement"
        contract.state = "prepared"
        contract.save(update_fields=["title", "state"])
        version = make_version(contract, self.initiator, content_snapshot="Prepared contract body.")
        return contract, version

    def test_prepared_contract_creates_workflow(self):
        contract, version = self.make_prepared_contract()
        client = authed_client(self.initiator)

        response = client.post(self.endpoint, {"contract_id": str(contract.id)}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["contract_id"], str(contract.id))
        self.assertEqual(response.data["created_version_id"], str(version.id))
        self.assertEqual(response.data["redirect_url"], f"/workflows/{response.data['workflow_id']}")
        workflow = WorkflowState.objects.get(id=response.data["workflow_id"])
        self.assertEqual(workflow.contract_id, contract.id)
        self.assertEqual(workflow.created_version_id, version.id)
        self.assertEqual(workflow.current_state, WorkflowState.STATE_VERSION_CREATED)

    def test_prepared_contract_reuses_existing_workflow(self):
        contract, _version = self.make_prepared_contract()
        client = authed_client(self.initiator)

        first_response = client.post(self.endpoint, {"contract_id": str(contract.id)}, format="json")
        second_response = client.post(self.endpoint, {"contract_id": str(contract.id)}, format="json")

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.data["workflow_id"], second_response.data["workflow_id"])
        self.assertEqual(WorkflowState.objects.filter(contract=contract, user=self.initiator).count(), 1)

    def test_draft_contract_is_rejected(self):
        contract = make_contract(self.initiator, "counterparty@example.com")
        make_version(contract, self.initiator, content_snapshot="Draft contract body.")
        client = authed_client(self.initiator)

        response = client.post(self.endpoint, {"contract_id": str(contract.id)}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertIn("Prepare the contract", response.data["error"])
        self.assertFalse(WorkflowState.objects.filter(contract=contract).exists())

    def test_unrelated_user_is_rejected(self):
        contract, _version = self.make_prepared_contract()
        client = authed_client(self.other_user)

        response = client.post(self.endpoint, {"contract_id": str(contract.id)}, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(WorkflowState.objects.filter(contract=contract, user=self.other_user).exists())

    def test_counterparty_email_is_carried_into_workflow(self):
        contract, _version = self.make_prepared_contract()
        client = authed_client(self.initiator)

        response = client.post(self.endpoint, {"contract_id": str(contract.id)}, format="json")

        self.assertEqual(response.status_code, 201)
        workflow = WorkflowState.objects.get(id=response.data["workflow_id"])
        self.assertEqual(workflow.counterparty_email, contract.counterparty_email)
        self.assertEqual(workflow.sent_to_counterparty_email, "")
