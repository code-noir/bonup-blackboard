# backend/api/tests/test_business_isolation.py
#
# B1 — Same-owner multi-business isolation verification.
#
# Purpose: document and confirm that same-owner multi-business isolation
# holds as expected across entity, contract, and Contract Pro paths.
#
# What these tests verify:
#   1. Entity list returns all businesses for the owner and no others.
#   2. Entity detail resolves the correct business by PK — no ID bleed.
#   3. Contract list is owner-wide by design: contracts from all of an
#      owner's businesses appear together (intentional, documented).
#   4. Contract Pro grant cardinality is per-business, not per-owner:
#      one owner with two businesses can hold independent active grants.
#
# Separate issue (NOT covered here):
#   ContractSerializer has no ownership check on the entity FK — a user
#   can attach another user's BusinessEntity to a contract. This is a
#   cross-owner bug, not a same-owner multi-business isolation issue.
#   It should be fixed as a separate task.

from django.test import TestCase

from backend.contracts.models import Contract
from backend.contract_pro.models import ContractProAccessGrant
from backend.contract_pro.services import ContractProGrantService
from backend.users.models import BusinessEntity
from .helpers import authed_client, make_subscription, make_user


def make_entity(owner, name):
    return BusinessEntity.objects.create(
        owner=owner,
        name=name,
        business_type="LLC",
    )


def make_business_contract(initiator, entity, counterparty_email="cp@example.com"):
    return Contract.objects.create(
        initiator=initiator,
        counterparty_email=counterparty_email,
        structure_type="ONE_TIME",
        max_versions=3,
        entity=entity,
        entity_type="business",
    )


def make_pending_grant(business, contract_pro_user):
    return ContractProAccessGrant.objects.create(
        business=business,
        contract_pro_user=contract_pro_user,
        access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
        access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
        access_status=ContractProAccessGrant.STATUS_PENDING,
    )


# -----------------------------------------------------------------------
# 1. Entity paths
# -----------------------------------------------------------------------

class SameOwnerMultiBusinessEntityTests(TestCase):
    """
    An owner with two businesses can see and manage both independently.
    Entity list returns all owner businesses; entity detail resolves the
    correct one by PK without cross-business bleed.
    """

    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        make_subscription(self.owner)
        self.entity_a = make_entity(self.owner, "Biz A")
        self.entity_b = make_entity(self.owner, "Biz B")
        self.client = authed_client(self.owner)

    def test_entity_list_returns_all_owner_businesses(self):
        """
        GET /api/entities/ returns both businesses for the owner.
        """
        response = self.client.get("/api/entities/")
        self.assertEqual(response.status_code, 200)
        returned_ids = {str(e["id"]) for e in response.data["results"]}
        self.assertIn(str(self.entity_a.pk), returned_ids)
        self.assertIn(str(self.entity_b.pk), returned_ids)
        self.assertEqual(response.data["count"], 2)

    def test_entity_detail_returns_correct_business_a(self):
        """
        GET /api/entities/<id>/ for entity A returns entity A data, not entity B.
        """
        response = self.client.get(f"/api/entities/{self.entity_a.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.entity_a.pk))
        self.assertEqual(response.data["name"], "Biz A")

    def test_entity_detail_returns_correct_business_b(self):
        """
        GET /api/entities/<id>/ for entity B returns entity B data, not entity A.
        """
        response = self.client.get(f"/api/entities/{self.entity_b.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.entity_b.pk))
        self.assertEqual(response.data["name"], "Biz B")


# -----------------------------------------------------------------------
# 2. Contract list — owner-wide by design
# -----------------------------------------------------------------------

class OwnerWideContractListDocumentedTests(TestCase):
    """
    The contract list is owner-wide by design.

    An owner with two businesses sees contracts from both businesses in a
    single list. This is intentional: the backend does not filter by entity.
    The frontend may pass ?entity= but the backend ignores it (documented in
    test_contract_creation.py as a known gap tracked separately).

    These tests document and confirm that intentional behavior.
    """

    def setUp(self):
        self.owner = make_user("owner2", "owner2@example.com")
        self.other = make_user("other", "other@example.com")
        make_subscription(self.owner)
        make_subscription(self.other)

        self.entity_a = make_entity(self.owner, "Owner Biz A")
        self.entity_b = make_entity(self.owner, "Owner Biz B")
        self.other_entity = make_entity(self.other, "Other Biz")

        self.contract_a = make_business_contract(self.owner, self.entity_a)
        self.contract_b = make_business_contract(self.owner, self.entity_b)
        self.other_contract = make_business_contract(self.other, self.other_entity)

        self.owner_client = authed_client(self.owner)
        self.other_client = authed_client(self.other)

    def test_owner_sees_contracts_from_both_businesses(self):
        """
        Owner-wide list: owner sees contracts from entity A and entity B together.
        This is the intended behavior — not a bug.
        """
        response = self.owner_client.get("/api/contracts/")
        self.assertEqual(response.status_code, 200)
        returned_ids = {str(c["id"]) for c in response.data}
        self.assertIn(str(self.contract_a.pk), returned_ids)
        self.assertIn(str(self.contract_b.pk), returned_ids)

    def test_owner_does_not_see_other_users_contracts(self):
        """
        Owner-wide list does not include contracts from a different user's business.
        """
        response = self.owner_client.get("/api/contracts/")
        self.assertEqual(response.status_code, 200)
        returned_ids = {str(c["id"]) for c in response.data}
        self.assertNotIn(str(self.other_contract.pk), returned_ids)

    def test_other_user_does_not_see_owner_contracts(self):
        """
        The other user's list does not include the owner's contracts.
        """
        response = self.other_client.get("/api/contracts/")
        self.assertEqual(response.status_code, 200)
        returned_ids = {str(c["id"]) for c in response.data}
        self.assertNotIn(str(self.contract_a.pk), returned_ids)
        self.assertNotIn(str(self.contract_b.pk), returned_ids)


# -----------------------------------------------------------------------
# 3. Contract Pro — per-business grant cardinality
# -----------------------------------------------------------------------

class ContractProPerBusinessAnchoringTests(TestCase):
    """
    Contract Pro grant cardinality is per-business, not per-owner.

    One owner with two businesses can hold independent active full_contract_pro
    grants simultaneously. Activating a grant on business B does not conflict
    with an active grant on business A.
    """

    def setUp(self):
        self.owner = make_user("owner3", "owner3@example.com")
        self.delegatee = make_user("delegatee", "delegatee@example.com")
        make_subscription(self.owner)

        self.entity_a = make_entity(self.owner, "Grant Biz A")
        self.entity_b = make_entity(self.owner, "Grant Biz B")

    def test_owner_can_have_active_grants_on_two_businesses_independently(self):
        """
        Activating a full grant on entity A and then on entity B both succeed.
        The cardinality rule is per-business — having one active grant on A
        does not block activating a grant on B.
        """
        grant_a = make_pending_grant(self.entity_a, self.delegatee)
        grant_b = make_pending_grant(self.entity_b, self.delegatee)

        # Activate grant for business A — should succeed.
        ContractProGrantService.activate_grant(grant_a)
        grant_a.refresh_from_db()
        self.assertEqual(grant_a.access_status, ContractProAccessGrant.STATUS_ACTIVE)

        # Activate grant for business B — should also succeed (different business).
        ContractProGrantService.activate_grant(grant_b)
        grant_b.refresh_from_db()
        self.assertEqual(grant_b.access_status, ContractProAccessGrant.STATUS_ACTIVE)

    def test_second_grant_on_same_business_is_blocked(self):
        """
        Attempting to activate a second full grant on the same business raises
        ContractProGrantError. Confirms the per-business cardinality rule holds.
        """
        from backend.contract_pro.services import ContractProGrantError

        grant_1 = make_pending_grant(self.entity_a, self.delegatee)
        ContractProGrantService.activate_grant(grant_1)

        delegatee_2 = make_user("delegatee2", "delegatee2@example.com")
        grant_2 = make_pending_grant(self.entity_a, delegatee_2)

        with self.assertRaises(ContractProGrantError):
            ContractProGrantService.activate_grant(grant_2)
