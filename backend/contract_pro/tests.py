# backend/contract_pro/tests.py
#
# Focused tests for the Contract Pro access-grant backbone.
# Tests the model layer and ContractProGrantService enforcement.
# No API layer, no routes, no permissions matrix.

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from backend.users.models import BusinessEntity
from backend.contracts.models import Contract

from .models import (
    ContractProAccessGrant,
    ContractProAction,
    ContractProContractAssignment,
    ContractProOversightEvent,
    ContractProPermissionRule,
)
from .services import (
    ContractProEditingService,
    ContractProGrantError,
    ContractProGrantService,
    ContractProOversightService,
    ContractProPermissionService,
)

User = get_user_model()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def make_user(username, email):
    return User.objects.create_user(username=username, email=email, password="testpass123")


def make_business(owner, name="Acme LLC"):
    return BusinessEntity.objects.create(
        owner=owner,
        name=name,
        business_type="LLC",
    )


def make_contract(initiator, counterparty_email="cp@example.com"):
    return Contract.objects.create(
        initiator=initiator,
        counterparty_email=counterparty_email,
        structure_type="ONE_TIME",
        max_versions=3,
    )


def make_pending_full_grant(business, pro_user, scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE):
    return ContractProAccessGrant.objects.create(
        business=business,
        contract_pro_user=pro_user,
        access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
        access_scope=scope,
        access_status=ContractProAccessGrant.STATUS_PENDING,
    )


def make_pending_temp_grant(business, pro_user):
    return ContractProAccessGrant.objects.create(
        business=business,
        contract_pro_user=pro_user,
        access_kind=ContractProAccessGrant.ACCESS_KIND_TEMP,
        access_scope=ContractProAccessGrant.SCOPE_SELECTED,
        access_status=ContractProAccessGrant.STATUS_PENDING,
    )


# ------------------------------------------------------------------
# Test: active full grant creation
# ------------------------------------------------------------------

class ActivateFullGrantTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.pro = make_user("pro", "pro@example.com")
        self.business = make_business(self.owner)

    def test_activate_full_grant_succeeds(self):
        grant = make_pending_full_grant(self.business, self.pro)
        ContractProGrantService.activate_grant(grant)
        grant.refresh_from_db()
        self.assertEqual(grant.access_status, ContractProAccessGrant.STATUS_ACTIVE)
        self.assertIsNotNone(grant.accepted_at)

    def test_owner_derivable_from_business(self):
        grant = make_pending_full_grant(self.business, self.pro)
        ContractProGrantService.activate_grant(grant)
        grant.refresh_from_db()
        self.assertEqual(grant.business.owner, self.owner)


# ------------------------------------------------------------------
# Test: one active full Contract Pro per business — service-level
# ------------------------------------------------------------------

class CardinalityEnforcementServiceTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.pro1 = make_user("pro1", "pro1@example.com")
        self.pro2 = make_user("pro2", "pro2@example.com")
        self.business = make_business(self.owner)

    def test_second_active_full_grant_rejected_by_service(self):
        grant1 = make_pending_full_grant(self.business, self.pro1)
        ContractProGrantService.activate_grant(grant1)

        grant2 = make_pending_full_grant(self.business, self.pro2)
        with self.assertRaises(ContractProGrantError):
            ContractProGrantService.activate_grant(grant2)

    def test_second_grant_status_unchanged_after_rejection(self):
        grant1 = make_pending_full_grant(self.business, self.pro1)
        ContractProGrantService.activate_grant(grant1)

        grant2 = make_pending_full_grant(self.business, self.pro2)
        try:
            ContractProGrantService.activate_grant(grant2)
        except ContractProGrantError:
            pass

        grant2.refresh_from_db()
        self.assertEqual(grant2.access_status, ContractProAccessGrant.STATUS_PENDING)


# ------------------------------------------------------------------
# Test: one active full Contract Pro per business — DB-level backstop
# ------------------------------------------------------------------

class CardinalityEnforcementDBTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.pro1 = make_user("pro1", "pro1@example.com")
        self.pro2 = make_user("pro2", "pro2@example.com")
        self.business = make_business(self.owner)

    def test_db_constraint_blocks_second_active_full_grant(self):
        ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro1,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_ACTIVE,
        )
        with self.assertRaises(IntegrityError):
            ContractProAccessGrant.objects.create(
                business=self.business,
                contract_pro_user=self.pro2,
                access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
                access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
                access_status=ContractProAccessGrant.STATUS_ACTIVE,
            )


# ------------------------------------------------------------------
# Test: revoked / declined records do not block new active full grant
# ------------------------------------------------------------------

class HistoricalRecordsCoexistenceTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.pro1 = make_user("pro1", "pro1@example.com")
        self.pro2 = make_user("pro2", "pro2@example.com")
        self.business = make_business(self.owner)

    def test_revoked_record_does_not_block_new_active_grant(self):
        ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro1,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_REVOKED,
        )
        grant2 = make_pending_full_grant(self.business, self.pro2)
        ContractProGrantService.activate_grant(grant2)
        grant2.refresh_from_db()
        self.assertEqual(grant2.access_status, ContractProAccessGrant.STATUS_ACTIVE)

    def test_declined_record_does_not_block_new_active_grant(self):
        ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro1,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_DECLINED,
        )
        grant2 = make_pending_full_grant(self.business, self.pro2)
        ContractProGrantService.activate_grant(grant2)
        grant2.refresh_from_db()
        self.assertEqual(grant2.access_status, ContractProAccessGrant.STATUS_ACTIVE)

    def test_pending_record_does_not_block_new_active_grant(self):
        # A pending grant from a different pro must not block activation of another
        make_pending_full_grant(self.business, self.pro1)
        grant2 = make_pending_full_grant(self.business, self.pro2)
        ContractProGrantService.activate_grant(grant2)
        grant2.refresh_from_db()
        self.assertEqual(grant2.access_status, ContractProAccessGrant.STATUS_ACTIVE)


# ------------------------------------------------------------------
# Test: temp grant rules
# ------------------------------------------------------------------

class TempGrantTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.temp_user = make_user("temp", "temp@example.com")
        self.business = make_business(self.owner)

    def test_temp_grant_with_selected_scope_succeeds(self):
        grant = make_pending_temp_grant(self.business, self.temp_user)
        self.assertEqual(grant.access_kind, ContractProAccessGrant.ACCESS_KIND_TEMP)
        self.assertEqual(grant.access_scope, ContractProAccessGrant.SCOPE_SELECTED)

    def test_temp_grant_with_business_wide_scope_fails_clean(self):
        grant = ContractProAccessGrant(
            business=self.business,
            contract_pro_user=self.temp_user,
            access_kind=ContractProAccessGrant.ACCESS_KIND_TEMP,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_PENDING,
        )
        with self.assertRaises(ValidationError):
            grant.clean()

    def test_temp_grant_activate_succeeds(self):
        grant = make_pending_temp_grant(self.business, self.temp_user)
        ContractProGrantService.activate_grant(grant)
        grant.refresh_from_db()
        self.assertEqual(grant.access_status, ContractProAccessGrant.STATUS_ACTIVE)

    def test_multiple_temp_grants_allowed_on_same_business(self):
        # Temp has no one-per-business cardinality restriction
        temp2 = make_user("temp2", "temp2@example.com")
        grant1 = make_pending_temp_grant(self.business, self.temp_user)
        grant2 = make_pending_temp_grant(self.business, temp2)
        ContractProGrantService.activate_grant(grant1)
        ContractProGrantService.activate_grant(grant2)
        grant1.refresh_from_db()
        grant2.refresh_from_db()
        self.assertEqual(grant1.access_status, ContractProAccessGrant.STATUS_ACTIVE)
        self.assertEqual(grant2.access_status, ContractProAccessGrant.STATUS_ACTIVE)


# ------------------------------------------------------------------
# Test: contract assignment
# ------------------------------------------------------------------

class ContractAssignmentTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.pro = make_user("pro", "pro@example.com")
        self.business = make_business(self.owner)
        self.contract = make_contract(self.owner)

    def test_contract_assignment_creation_succeeds(self):
        grant = make_pending_full_grant(
            self.business, self.pro, scope=ContractProAccessGrant.SCOPE_SELECTED
        )
        assignment = ContractProContractAssignment.objects.create(
            grant=grant,
            contract=self.contract,
        )
        self.assertEqual(assignment.grant, grant)
        self.assertEqual(assignment.contract, self.contract)
        self.assertIsNone(assignment.unassigned_at)

    def test_assignment_linked_to_grant_via_related_manager(self):
        grant = make_pending_full_grant(
            self.business, self.pro, scope=ContractProAccessGrant.SCOPE_SELECTED
        )
        ContractProContractAssignment.objects.create(grant=grant, contract=self.contract)
        self.assertEqual(grant.contract_assignments.count(), 1)


# ------------------------------------------------------------------
# Test: independent cardinality across businesses
# ------------------------------------------------------------------

class CrossBusinessCardinalityTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner", "owner@example.com")
        self.pro1 = make_user("pro1", "pro1@example.com")
        self.pro2 = make_user("pro2", "pro2@example.com")
        self.business_a = make_business(self.owner, name="Business A")
        self.business_b = make_business(self.owner, name="Business B")

    def test_each_business_can_have_independent_active_full_grant(self):
        grant_a = make_pending_full_grant(self.business_a, self.pro1)
        grant_b = make_pending_full_grant(self.business_b, self.pro2)
        ContractProGrantService.activate_grant(grant_a)
        ContractProGrantService.activate_grant(grant_b)
        grant_a.refresh_from_db()
        grant_b.refresh_from_db()
        self.assertEqual(grant_a.access_status, ContractProAccessGrant.STATUS_ACTIVE)
        self.assertEqual(grant_b.access_status, ContractProAccessGrant.STATUS_ACTIVE)


# ------------------------------------------------------------------
# Test: permission matrix — defaults
# ------------------------------------------------------------------

class PermissionDefaultsTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner_pm", "owner_pm@example.com")
        self.pro = make_user("pro_pm", "pro_pm@example.com")
        self.business = make_business(self.owner, name="PM Business")
        self.grant = make_pending_full_grant(self.business, self.pro)

    def test_sensitive_action_blocked_by_default(self):
        for action in ContractProAction.SENSITIVE_ACTIONS:
            with self.subTest(action=action):
                state = ContractProPermissionService.get_effective_state(
                    self.grant, action
                )
                self.assertEqual(state, ContractProPermissionRule.STATE_BLOCKED)

    def test_non_sensitive_action_accessible_by_default(self):
        non_sensitive = ContractProAction.ALL_ACTIONS - ContractProAction.SENSITIVE_ACTIONS
        for action in non_sensitive:
            with self.subTest(action=action):
                state = ContractProPermissionService.get_effective_state(
                    self.grant, action
                )
                self.assertEqual(state, ContractProPermissionRule.STATE_ACCESSIBLE)


# ------------------------------------------------------------------
# Test: permission matrix — explicit business-level rules
# ------------------------------------------------------------------

class PermissionBusinessLevelTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner_bl", "owner_bl@example.com")
        self.pro = make_user("pro_bl", "pro_bl@example.com")
        self.business = make_business(self.owner, name="BL Business")
        self.grant = make_pending_full_grant(self.business, self.pro)

    def test_explicit_business_level_accessible_rule(self):
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_ACCESSIBLE,
        )
        state = ContractProPermissionService.get_effective_state(
            self.grant, ContractProAction.CREATE_CONTRACT
        )
        self.assertEqual(state, ContractProPermissionRule.STATE_ACCESSIBLE)

    def test_explicit_business_level_blocked_rule(self):
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_BLOCKED,
        )
        state = ContractProPermissionService.get_effective_state(
            self.grant, ContractProAction.CREATE_CONTRACT
        )
        self.assertEqual(state, ContractProPermissionRule.STATE_BLOCKED)

    def test_owner_can_unblock_sensitive_action_at_business_level(self):
        # Owner may explicitly unlock a sensitive action
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.TRIGGER_PAYMENT_REQUEST,
            state=ContractProPermissionRule.STATE_ACCESSIBLE,
        )
        state = ContractProPermissionService.get_effective_state(
            self.grant, ContractProAction.TRIGGER_PAYMENT_REQUEST
        )
        self.assertEqual(state, ContractProPermissionRule.STATE_ACCESSIBLE)


# ------------------------------------------------------------------
# Test: permission matrix — contract-level override rules
# ------------------------------------------------------------------

class PermissionContractLevelTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner_cl", "owner_cl@example.com")
        self.pro = make_user("pro_cl", "pro_cl@example.com")
        self.business = make_business(self.owner, name="CL Business")
        self.grant = make_pending_full_grant(self.business, self.pro)
        self.contract = make_contract(self.owner)

    def test_contract_level_blocked_restricts_business_level_accessible(self):
        # Business level: accessible (default for create_contract)
        # Contract level: blocked
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=self.contract,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_BLOCKED,
        )
        state = ContractProPermissionService.get_effective_state(
            self.grant, ContractProAction.CREATE_CONTRACT, contract=self.contract
        )
        self.assertEqual(state, ContractProPermissionRule.STATE_BLOCKED)

    def test_contract_level_accessible_cannot_expand_business_level_blocked(self):
        # Business level: explicitly blocked
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_BLOCKED,
        )
        # Contract level: tries to set accessible — ceiling must hold
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=self.contract,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_ACCESSIBLE,
        )
        state = ContractProPermissionService.get_effective_state(
            self.grant, ContractProAction.CREATE_CONTRACT, contract=self.contract
        )
        self.assertEqual(state, ContractProPermissionRule.STATE_BLOCKED)

    def test_contract_level_rule_does_not_affect_different_contract(self):
        other_contract = make_contract(self.owner, counterparty_email="other@example.com")
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=self.contract,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_BLOCKED,
        )
        # Evaluating against other_contract should see the default (accessible)
        state = ContractProPermissionService.get_effective_state(
            self.grant, ContractProAction.CREATE_CONTRACT, contract=other_contract
        )
        self.assertEqual(state, ContractProPermissionRule.STATE_ACCESSIBLE)

    def test_no_contract_level_rule_falls_through_to_business_level(self):
        # Business level: blocked
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.EDIT_CONTRACT_WORKSPACE,
            state=ContractProPermissionRule.STATE_BLOCKED,
        )
        # No contract-level rule stored
        state = ContractProPermissionService.get_effective_state(
            self.grant, ContractProAction.EDIT_CONTRACT_WORKSPACE, contract=self.contract
        )
        self.assertEqual(state, ContractProPermissionRule.STATE_BLOCKED)


# ------------------------------------------------------------------
# Test: permission matrix — grant independence
# ------------------------------------------------------------------

class PermissionGrantIndependenceTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner_gi", "owner_gi@example.com")
        self.pro1 = make_user("pro_gi1", "pro_gi1@example.com")
        self.pro2 = make_user("pro_gi2", "pro_gi2@example.com")
        self.business = make_business(self.owner, name="GI Business")
        self.grant1 = make_pending_full_grant(self.business, self.pro1)
        # grant2 is a temp grant on a second business to avoid cardinality conflict
        self.business2 = make_business(self.owner, name="GI Business 2")
        self.grant2 = make_pending_full_grant(self.business2, self.pro2)

    def test_two_grants_have_independent_rule_sets(self):
        # Block create_contract only on grant1
        ContractProPermissionRule.objects.create(
            grant=self.grant1,
            contract=None,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_BLOCKED,
        )
        state1 = ContractProPermissionService.get_effective_state(
            self.grant1, ContractProAction.CREATE_CONTRACT
        )
        state2 = ContractProPermissionService.get_effective_state(
            self.grant2, ContractProAction.CREATE_CONTRACT
        )
        self.assertEqual(state1, ContractProPermissionRule.STATE_BLOCKED)
        self.assertEqual(state2, ContractProPermissionRule.STATE_ACCESSIBLE)


# ------------------------------------------------------------------
# Test: duplicate permission rule integrity enforcement
# ------------------------------------------------------------------

class PermissionDuplicateRuleTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner_dr", "owner_dr@example.com")
        self.pro = make_user("pro_dr", "pro_dr@example.com")
        self.business = make_business(self.owner, name="DR Business")
        self.grant = make_pending_full_grant(self.business, self.pro)
        self.contract = make_contract(self.owner, counterparty_email="drcp@example.com")

    def test_duplicate_business_level_row_raises_integrity_error(self):
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_ACCESSIBLE,
        )
        with self.assertRaises(IntegrityError):
            ContractProPermissionRule.objects.create(
                grant=self.grant,
                contract=None,
                action=ContractProAction.CREATE_CONTRACT,
                state=ContractProPermissionRule.STATE_BLOCKED,
            )

    def test_business_level_row_for_different_action_succeeds(self):
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.CREATE_CONTRACT,
            state=ContractProPermissionRule.STATE_ACCESSIBLE,
        )
        # Different action — must not be blocked by the constraint
        rule = ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=None,
            action=ContractProAction.VIEW_CONTRACT,
            state=ContractProPermissionRule.STATE_ACCESSIBLE,
        )
        self.assertIsNotNone(rule.pk)

    def test_duplicate_contract_level_row_raises_integrity_error(self):
        ContractProPermissionRule.objects.create(
            grant=self.grant,
            contract=self.contract,
            action=ContractProAction.EDIT_CONTRACT_WORKSPACE,
            state=ContractProPermissionRule.STATE_ACCESSIBLE,
        )
        with self.assertRaises(IntegrityError):
            ContractProPermissionRule.objects.create(
                grant=self.grant,
                contract=self.contract,
                action=ContractProAction.EDIT_CONTRACT_WORKSPACE,
                state=ContractProPermissionRule.STATE_BLOCKED,
            )


# ------------------------------------------------------------------
# Test: editing exclusivity enforcement
# ------------------------------------------------------------------

class EditingExclusivityTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner_ex", "owner_ex@example.com")
        self.pro = make_user("pro_ex", "pro_ex@example.com")
        self.other_user = make_user("other_ex", "other_ex@example.com")
        self.business = make_business(self.owner, name="EX Business")
        # Contract linked to the business entity
        self.contract = Contract.objects.create(
            initiator=self.owner,
            counterparty_email="cp_ex@example.com",
            structure_type="ONE_TIME",
            max_versions=3,
            entity=self.business,
            entity_type="business",
        )

    # --- helpers ---

    def _active_selected_grant(self):
        grant = ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_SELECTED,
            access_status=ContractProAccessGrant.STATUS_ACTIVE,
        )
        ContractProContractAssignment.objects.create(
            grant=grant,
            contract=self.contract,
        )
        return grant

    def _active_business_wide_grant(self):
        return ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_ACTIVE,
        )

    # --- get_active_editor_for_contract ---

    def test_active_selected_assignment_returns_grant(self):
        grant = self._active_selected_grant()
        result = ContractProEditingService.get_active_editor_for_contract(self.contract)
        self.assertEqual(result, grant)

    def test_active_business_wide_grant_returns_grant(self):
        grant = self._active_business_wide_grant()
        result = ContractProEditingService.get_active_editor_for_contract(self.contract)
        self.assertEqual(result, grant)

    def test_no_delegation_returns_none(self):
        result = ContractProEditingService.get_active_editor_for_contract(self.contract)
        self.assertIsNone(result)

    def test_unassigned_assignment_returns_none(self):
        from django.utils import timezone
        grant = ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_SELECTED,
            access_status=ContractProAccessGrant.STATUS_ACTIVE,
        )
        ContractProContractAssignment.objects.create(
            grant=grant,
            contract=self.contract,
            unassigned_at=timezone.now(),
        )
        result = ContractProEditingService.get_active_editor_for_contract(self.contract)
        self.assertIsNone(result)

    # --- owner_editing_allowed ---

    def test_no_delegation_owner_may_edit(self):
        self.assertTrue(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_active_selected_assignment_blocks_owner_editing(self):
        self._active_selected_grant()
        self.assertFalse(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_revoked_grant_restores_owner_editing(self):
        grant = ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_SELECTED,
            access_status=ContractProAccessGrant.STATUS_REVOKED,
        )
        ContractProContractAssignment.objects.create(
            grant=grant,
            contract=self.contract,
        )
        self.assertTrue(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_business_wide_grant_blocks_owner_editing(self):
        self._active_business_wide_grant()
        self.assertFalse(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_pending_grant_does_not_block_owner_editing(self):
        ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_PENDING,
        )
        self.assertTrue(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_declined_grant_does_not_block_owner_editing(self):
        ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=self.pro,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_DECLINED,
        )
        self.assertTrue(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_non_owner_user_always_returns_false(self):
        # No delegation — but not the owner
        self.assertFalse(
            ContractProEditingService.owner_editing_allowed(self.contract, self.other_user)
        )

    def test_non_owner_user_returns_false_even_without_delegation(self):
        # Confirm non-owner blocked regardless of delegation state
        self._active_selected_grant()
        self.assertFalse(
            ContractProEditingService.owner_editing_allowed(self.contract, self.other_user)
        )

    def test_temp_assignment_blocks_owner_editing_on_assigned_contract(self):
        temp_user = make_user("temp_ex", "temp_ex@example.com")
        grant = ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=temp_user,
            access_kind=ContractProAccessGrant.ACCESS_KIND_TEMP,
            access_scope=ContractProAccessGrant.SCOPE_SELECTED,
            access_status=ContractProAccessGrant.STATUS_ACTIVE,
        )
        ContractProContractAssignment.objects.create(
            grant=grant,
            contract=self.contract,
        )
        self.assertFalse(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_temp_on_different_contract_does_not_block_editing_on_this_contract(self):
        temp_user = make_user("temp_ex2", "temp_ex2@example.com")
        other_contract = Contract.objects.create(
            initiator=self.owner,
            counterparty_email="other_cp_ex@example.com",
            structure_type="ONE_TIME",
            max_versions=3,
            entity=self.business,
            entity_type="business",
        )
        grant = ContractProAccessGrant.objects.create(
            business=self.business,
            contract_pro_user=temp_user,
            access_kind=ContractProAccessGrant.ACCESS_KIND_TEMP,
            access_scope=ContractProAccessGrant.SCOPE_SELECTED,
            access_status=ContractProAccessGrant.STATUS_ACTIVE,
        )
        ContractProContractAssignment.objects.create(
            grant=grant,
            contract=other_contract,
        )
        # self.contract has no active delegation
        self.assertTrue(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )

    def test_unrelated_business_grant_does_not_affect_this_contract(self):
        other_owner = make_user("other_owner_ex", "other_owner_ex@example.com")
        other_business = make_business(other_owner, name="Other EX Business")
        other_pro = make_user("other_pro_ex", "other_pro_ex@example.com")
        ContractProAccessGrant.objects.create(
            business=other_business,
            contract_pro_user=other_pro,
            access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
            access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
            access_status=ContractProAccessGrant.STATUS_ACTIVE,
        )
        self.assertTrue(
            ContractProEditingService.owner_editing_allowed(self.contract, self.owner)
        )


# ------------------------------------------------------------------
# Test: Oversight event creation on grant activation
# ------------------------------------------------------------------

class OversightEventActivationTest(TestCase):
    def setUp(self):
        self.owner = make_user("owner_oe", "owner_oe@example.com")
        self.pro = make_user("pro_oe", "pro_oe@example.com")
        self.business = make_business(self.owner, name="OE Business")

    def test_activate_grant_creates_one_oversight_event(self):
        grant = make_pending_full_grant(self.business, self.pro)
        ContractProGrantService.activate_grant(grant)
        events = ContractProOversightEvent.objects.filter(
            event_type=ContractProOversightEvent.EVENT_GRANT_ACTIVATED,
        )
        self.assertEqual(events.count(), 1)

    def test_activation_event_business_matches_grant_business(self):
        grant = make_pending_full_grant(self.business, self.pro)
        ContractProGrantService.activate_grant(grant)
        event = ContractProOversightEvent.objects.get(
            event_type=ContractProOversightEvent.EVENT_GRANT_ACTIVATED,
        )
        self.assertEqual(event.business, self.business)

    def test_activation_event_grant_fk_matches_activated_grant(self):
        grant = make_pending_full_grant(self.business, self.pro)
        ContractProGrantService.activate_grant(grant)
        event = ContractProOversightEvent.objects.get(
            event_type=ContractProOversightEvent.EVENT_GRANT_ACTIVATED,
        )
        self.assertEqual(event.grant, grant)

    def test_activation_event_actor_is_none(self):
        # activate_grant() is a service-layer call with no HTTP actor
        grant = make_pending_full_grant(self.business, self.pro)
        ContractProGrantService.activate_grant(grant)
        event = ContractProOversightEvent.objects.get(
            event_type=ContractProOversightEvent.EVENT_GRANT_ACTIVATED,
        )
        self.assertIsNone(event.actor)
