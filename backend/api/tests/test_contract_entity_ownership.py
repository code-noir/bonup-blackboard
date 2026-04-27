# backend/api/tests/test_contract_entity_ownership.py
#
# Regression tests for the cross-owner BusinessEntity attachment bug.
#
# Bug: ContractSerializer did not validate ownership of the entity FK.
# A user could POST {"entity": <other_users_entity_id>} and attach a
# BusinessEntity they do not own to a contract.
#
# Fix: ContractSerializer.validate() checks entity.owner_id against
# request.user.pk when request is present in serializer context.
# ContractViewSet passes context={'request': request} on create and update.

from django.test import TestCase

from backend.users.models import BusinessEntity
from .helpers import authed_client, make_contract, make_subscription, make_user


def make_entity(owner, name="Test Biz"):
    return BusinessEntity.objects.create(
        owner=owner,
        name=name,
        business_type="LLC",
    )


class ContractEntityOwnershipCreateTests(TestCase):
    """POST /api/contracts/ — entity ownership enforcement on create."""

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        make_subscription(self.alice)
        make_subscription(self.bob)
        self.bobs_entity = make_entity(self.bob, "Bob Corp")
        self.alices_entity = make_entity(self.alice, "Alice LLC")
        self.client = authed_client(self.alice)

    def test_create_with_foreign_entity_is_rejected(self):
        """
        POST with another user's entity PK → 400 with entity error.
        """
        payload = {
            "entity": str(self.bobs_entity.pk),
            "entity_type": "business",
            "counterparty_email": "cp@example.com",
            "structure_type": "ONE_TIME",
            "max_versions": 3,
        }
        response = self.client.post("/api/contracts/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("entity", response.data)

    def test_create_with_own_entity_is_allowed(self):
        """
        POST with own entity PK → 201.
        """
        payload = {
            "entity": str(self.alices_entity.pk),
            "entity_type": "business",
            "counterparty_email": "cp@example.com",
            "structure_type": "ONE_TIME",
            "max_versions": 3,
        }
        response = self.client.post("/api/contracts/", payload, format="json")
        self.assertEqual(response.status_code, 201)


class ContractEntityOwnershipUpdateTests(TestCase):
    """PATCH /api/contracts/<id>/ — entity ownership enforcement on update."""

    def setUp(self):
        self.alice = make_user("alice2", "alice2@example.com")
        self.bob = make_user("bob2", "bob2@example.com")
        make_subscription(self.alice)
        make_subscription(self.bob)
        self.bobs_entity = make_entity(self.bob, "Bob Corp 2")
        self.alices_entity = make_entity(self.alice, "Alice LLC 2")
        self.contract = make_contract(self.alice, "cp@example.com")
        self.client = authed_client(self.alice)

    def test_patch_with_foreign_entity_is_rejected(self):
        """
        PATCH attaching another user's entity → 400 with entity error.
        """
        payload = {
            "entity": str(self.bobs_entity.pk),
            "entity_type": "business",
        }
        response = self.client.patch(
            f"/api/contracts/{self.contract.pk}/", payload, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("entity", response.data)

    def test_patch_with_own_entity_is_allowed(self):
        """
        PATCH attaching own entity → 200.
        """
        payload = {
            "entity": str(self.alices_entity.pk),
            "entity_type": "business",
        }
        response = self.client.patch(
            f"/api/contracts/{self.contract.pk}/", payload, format="json"
        )
        self.assertEqual(response.status_code, 200)
