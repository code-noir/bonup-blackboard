# backend/api/tests/test_contract_creation.py
#
# Regression tests for the contract creation endpoint.
#
# These tests guard the active contract creation flow:
#   POST /api/contracts/  →  returns id used to navigate to /contracts/create?id=...
#
# NOTE ON ARCHITECTURE:
#   The active ContractViewSet is at:
#     backend/api/contracts/viewsets/contract_viewset.py
#   loaded via:
#     backend/api/contracts/views/__init__.py
#
#   The file backend/api/contracts/views.py is an older version that is
#   SHADOWED by the views/ package and is NOT executed. Any changes to
#   views.py have no effect. Work in contract_viewset.py.
#
# What is verified:
#   - Full payload (as sent by NewContract.tsx) creates a contract (201)
#   - Response includes the id field the frontend uses for editor routing
#   - Initiator is always the authenticated user regardless of payload
#   - Unauthenticated request is rejected (401)
#   - Minimal payload still succeeds
#   - entity_type and entity fields are stored as provided

from django.test import TestCase

from backend.contracts.models import Contract
from backend.users.models import BusinessEntity

from .helpers import authed_client, make_subscription, make_user

CONTRACT_URL = "/api/contracts/"

# Payload shape sent by NewContract.tsx after the form is submitted
FULL_PAYLOAD = {
    "title": "Lawn Care Service Agreement",
    "contract_type": "Service Agreement",
    "language": "English",
    "start_date": "2026-05-01",
    "end_date": "2026-10-31",
    "contract_value": "1200.00",
    "currency": "USD",
    "description": "Weekly lawn care for the season.",
    "jurisdiction": "New York, USA",
    "governing_law": "Laws of New York State",
    "confidentiality": "Not confidential",
    "dispute_resolution": "Negotiation",
    "counterparty_name": "Jane Smith",
    "counterparty_email": "jane@example.com",
    "structure_type": "ONE_TIME",
    "entity_type": "personal",
    "status": "draft",
}


class ContractCreateTests(TestCase):
    def setUp(self):
        self.user = make_user("creator", "creator@example.com")
        make_subscription(self.user)
        self.client = authed_client(self.user)

    def test_full_payload_creates_contract(self):
        """NewContract.tsx full payload returns 201."""
        r = self.client.post(CONTRACT_URL, FULL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 201)

    def test_response_includes_id_for_editor_routing(self):
        """
        The frontend uses the returned id to build /contracts/create?id=<id>.
        This id must be present in the response.
        """
        r = self.client.post(CONTRACT_URL, FULL_PAYLOAD, format="json")
        self.assertIn("id", r.data)
        self.assertTrue(r.data["id"])  # non-empty UUID string

    def test_response_entity_type_matches_submitted(self):
        r = self.client.post(CONTRACT_URL, FULL_PAYLOAD, format="json")
        self.assertEqual(r.data["entity_type"], "personal")

    def test_response_title_matches_submitted(self):
        r = self.client.post(CONTRACT_URL, FULL_PAYLOAD, format="json")
        self.assertEqual(r.data["title"], FULL_PAYLOAD["title"])

    def test_initiator_is_always_authenticated_user(self):
        """
        Callers cannot override the initiator — it is always set to the
        authenticated user by the view, not taken from the payload.
        """
        other = make_user("other", "other@example.com")
        payload = {**FULL_PAYLOAD, "initiator": other.pk}
        r = self.client.post(CONTRACT_URL, payload, format="json")
        self.assertEqual(r.status_code, 201)
        contract = Contract.objects.get(pk=r.data["id"])
        self.assertEqual(contract.initiator, self.user)

    def test_minimal_payload_succeeds(self):
        """
        Only a small set of fields is truly required by the backend.
        NewContract.tsx always sends more, but the minimal case must work.
        """
        minimal = {
            "title": "Quick NDA",
            "contract_type": "NDA / Confidentiality Agreement",
            "structure_type": "ONE_TIME",
            "entity_type": "personal",
            "counterparty_email": "pending@bonup.placeholder",
        }
        r = self.client.post(CONTRACT_URL, minimal, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("id", r.data)

    def test_unauthenticated_request_rejected(self):
        from rest_framework.test import APIClient
        anon = APIClient()
        r = anon.post(CONTRACT_URL, FULL_PAYLOAD, format="json")
        self.assertEqual(r.status_code, 401)

    def test_business_entity_type_stored(self):
        """entity_type='business' is preserved in the created contract."""
        entity = BusinessEntity.objects.create(
            owner=self.user, name="Acme LLC", business_type="LLC"
        )
        payload = {
            **FULL_PAYLOAD,
            "entity_type": "business",
            "entity": str(entity.id),
        }
        r = self.client.post(CONTRACT_URL, payload, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["entity_type"], "business")

    def test_created_contract_is_retrievable_by_id(self):
        """
        After creation, the id returned can be used to retrieve the contract —
        this is the backend half of /contracts/create?id=<id> working.
        """
        r_create = self.client.post(CONTRACT_URL, FULL_PAYLOAD, format="json")
        contract_id = r_create.data["id"]
        r_get = self.client.get(f"{CONTRACT_URL}{contract_id}/")
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.data["id"], contract_id)
        self.assertEqual(r_get.data["title"], FULL_PAYLOAD["title"])


class ContractListTests(TestCase):
    """
    Guard the list endpoint behavior.

    NOTE: The active list() in contract_viewset.py returns ALL contracts for
    the user (personal and business) without entity-type filtering. The
    frontend currently passes ?entity= params but the backend ignores them.
    This is a known gap — tracked separately. These tests document the
    actual current behavior.
    """

    def setUp(self):
        self.user = make_user("lister", "lister@example.com")
        make_subscription(self.user)
        self.client = authed_client(self.user)
        self.entity = BusinessEntity.objects.create(
            owner=self.user, name="My Corp", business_type="Corp"
        )

    def _create(self, entity_type, entity_id=None):
        payload = {**FULL_PAYLOAD, "entity_type": entity_type}
        if entity_id:
            payload["entity"] = str(entity_id)
        r = self.client.post(CONTRACT_URL, payload, format="json")
        self.assertEqual(r.status_code, 201)
        return r.data["id"]

    def test_list_returns_contracts_for_authenticated_user(self):
        self._create("personal")
        r = self.client.get(CONTRACT_URL)
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data), 1)

    def test_list_includes_both_personal_and_business_contracts(self):
        """
        Current backend behavior: list returns all user contracts regardless
        of entity_type. The frontend entity filter is not applied server-side.
        """
        self._create("personal")
        self._create("business", self.entity.id)
        r = self.client.get(CONTRACT_URL)
        entity_types = {c["entity_type"] for c in r.data}
        # Both entity types appear in the list
        self.assertIn("personal", entity_types)
        self.assertIn("business", entity_types)

    def test_unauthenticated_list_rejected(self):
        from rest_framework.test import APIClient
        anon = APIClient()
        r = anon.get(CONTRACT_URL)
        self.assertEqual(r.status_code, 401)
