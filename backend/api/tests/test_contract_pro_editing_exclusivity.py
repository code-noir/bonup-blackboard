# backend/api/tests/test_contract_pro_editing_exclusivity.py
#
# API-layer enforcement tests for Contract Pro editing exclusivity.
#
# Guarded paths:
#   PATCH /api/contracts/<pk>/          — ContractViewSet.update()
#   POST  /api/contracts/<pk>/versions/ — ContractVersionCreateAPIView.post()
#
# Rule: while an active Contract Pro delegation controls a contract,
# the owner/initiator's direct editing is blocked (HTTP 403).
# Revocation or absence of delegation restores owner editing.

from django.test import TestCase

from backend.contracts.models import Contract
from backend.users.models import BusinessEntity
from backend.contract_pro.models import (
    ContractProAccessGrant,
    ContractProContractAssignment,
    ContractProOversightEvent,
)

from .helpers import authed_client, make_subscription, make_user


# ------------------------------------------------------------------
# Shared setup helpers
# ------------------------------------------------------------------

def _make_business_contract(owner):
    """Create a contract linked to a BusinessEntity owned by `owner`."""
    entity = BusinessEntity.objects.create(
        owner=owner, name="Test Biz", business_type="LLC"
    )
    contract = Contract.objects.create(
        initiator=owner,
        counterparty_email="cp@example.com",
        structure_type="ONE_TIME",
        max_versions=5,
        entity=entity,
        entity_type="business",
    )
    return contract, entity


def _active_business_wide_grant(entity, pro_user):
    return ContractProAccessGrant.objects.create(
        business=entity,
        contract_pro_user=pro_user,
        access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
        access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
        access_status=ContractProAccessGrant.STATUS_ACTIVE,
    )


def _active_selected_grant(entity, pro_user, contract):
    grant = ContractProAccessGrant.objects.create(
        business=entity,
        contract_pro_user=pro_user,
        access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
        access_scope=ContractProAccessGrant.SCOPE_SELECTED,
        access_status=ContractProAccessGrant.STATUS_ACTIVE,
    )
    ContractProContractAssignment.objects.create(grant=grant, contract=contract)
    return grant


def _revoked_selected_grant(entity, pro_user, contract):
    grant = ContractProAccessGrant.objects.create(
        business=entity,
        contract_pro_user=pro_user,
        access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
        access_scope=ContractProAccessGrant.SCOPE_SELECTED,
        access_status=ContractProAccessGrant.STATUS_REVOKED,
    )
    ContractProContractAssignment.objects.create(grant=grant, contract=contract)
    return grant


# ------------------------------------------------------------------
# PATCH /api/contracts/<pk>/
# ------------------------------------------------------------------

class ContractUpdateExclusivityTests(TestCase):

    def setUp(self):
        self.owner = make_user("owner_upd", "owner_upd@example.com")
        make_subscription(self.owner)
        self.pro = make_user("pro_upd", "pro_upd@example.com")
        self.contract, self.entity = _make_business_contract(self.owner)
        self.url = f"/api/contracts/{self.contract.id}/"
        self.patch_payload = {"counterparty_name": "Updated Name"}

    def test_active_business_wide_grant_blocks_owner_patch(self):
        _active_business_wide_grant(self.entity, self.pro)
        r = authed_client(self.owner).patch(self.url, self.patch_payload, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Contract Pro", r.data["error"])

    def test_active_selected_assignment_blocks_owner_patch(self):
        _active_selected_grant(self.entity, self.pro, self.contract)
        r = authed_client(self.owner).patch(self.url, self.patch_payload, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Contract Pro", r.data["error"])

    def test_revoked_grant_allows_owner_patch(self):
        _revoked_selected_grant(self.entity, self.pro, self.contract)
        r = authed_client(self.owner).patch(self.url, self.patch_payload, format="json")
        self.assertEqual(r.status_code, 200)

    def test_no_delegation_allows_owner_patch(self):
        r = authed_client(self.owner).patch(self.url, self.patch_payload, format="json")
        self.assertEqual(r.status_code, 200)


# ------------------------------------------------------------------
# POST /api/contracts/<pk>/versions/
# ------------------------------------------------------------------

class VersionCreateExclusivityTests(TestCase):

    def setUp(self):
        self.owner = make_user("owner_ver", "owner_ver@example.com")
        make_subscription(self.owner)
        self.pro = make_user("pro_ver", "pro_ver@example.com")
        self.contract, self.entity = _make_business_contract(self.owner)
        self.url = f"/api/contracts/{self.contract.id}/versions/"
        self.version_payload = {"content_snapshot": "Draft terms v1."}

    def test_active_business_wide_grant_blocks_owner_version_create(self):
        _active_business_wide_grant(self.entity, self.pro)
        r = authed_client(self.owner).post(self.url, self.version_payload, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Contract Pro", r.data["error"])

    def test_active_selected_assignment_blocks_owner_version_create(self):
        _active_selected_grant(self.entity, self.pro, self.contract)
        r = authed_client(self.owner).post(self.url, self.version_payload, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Contract Pro", r.data["error"])

    def test_revoked_grant_allows_owner_version_create(self):
        _revoked_selected_grant(self.entity, self.pro, self.contract)
        r = authed_client(self.owner).post(self.url, self.version_payload, format="json")
        self.assertEqual(r.status_code, 201)

    def test_no_delegation_allows_owner_version_create(self):
        r = authed_client(self.owner).post(self.url, self.version_payload, format="json")
        self.assertEqual(r.status_code, 201)


# ------------------------------------------------------------------
# Oversight event recording on blocked paths
# ------------------------------------------------------------------

class OversightEventOnBlockedPatchTest(TestCase):

    def setUp(self):
        self.owner = make_user("owner_oep", "owner_oep@example.com")
        make_subscription(self.owner)
        self.pro = make_user("pro_oep", "pro_oep@example.com")
        self.contract, self.entity = _make_business_contract(self.owner)
        self.url = f"/api/contracts/{self.contract.id}/"
        self.patch_payload = {"counterparty_name": "OEP Name"}

    def test_blocked_patch_creates_owner_edit_blocked_event(self):
        _active_business_wide_grant(self.entity, self.pro)
        authed_client(self.owner).patch(self.url, self.patch_payload, format="json")
        events = ContractProOversightEvent.objects.filter(
            event_type=ContractProOversightEvent.EVENT_OWNER_EDIT_BLOCKED,
        )
        self.assertEqual(events.count(), 1)

    def test_blocked_patch_event_has_correct_business_and_contract(self):
        _active_business_wide_grant(self.entity, self.pro)
        authed_client(self.owner).patch(self.url, self.patch_payload, format="json")
        event = ContractProOversightEvent.objects.get(
            event_type=ContractProOversightEvent.EVENT_OWNER_EDIT_BLOCKED,
        )
        self.assertEqual(event.business, self.entity)
        self.assertEqual(event.contract, self.contract)
        self.assertEqual(event.actor, self.owner)


class OversightEventOnBlockedVersionCreateTest(TestCase):

    def setUp(self):
        self.owner = make_user("owner_oev", "owner_oev@example.com")
        make_subscription(self.owner)
        self.pro = make_user("pro_oev", "pro_oev@example.com")
        self.contract, self.entity = _make_business_contract(self.owner)
        self.url = f"/api/contracts/{self.contract.id}/versions/"
        self.version_payload = {"content_snapshot": "OEV Draft."}

    def test_blocked_version_create_creates_owner_edit_blocked_event(self):
        _active_business_wide_grant(self.entity, self.pro)
        authed_client(self.owner).post(self.url, self.version_payload, format="json")
        events = ContractProOversightEvent.objects.filter(
            event_type=ContractProOversightEvent.EVENT_OWNER_EDIT_BLOCKED,
        )
        self.assertEqual(events.count(), 1)

    def test_blocked_version_create_event_has_correct_business_and_contract(self):
        _active_business_wide_grant(self.entity, self.pro)
        authed_client(self.owner).post(self.url, self.version_payload, format="json")
        event = ContractProOversightEvent.objects.get(
            event_type=ContractProOversightEvent.EVENT_OWNER_EDIT_BLOCKED,
        )
        self.assertEqual(event.business, self.entity)
        self.assertEqual(event.contract, self.contract)
        self.assertEqual(event.actor, self.owner)
