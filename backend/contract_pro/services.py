# backend/contract_pro/services.py

from typing import Optional

from django.utils import timezone

from .models import (
    ContractProAccessGrant,
    ContractProAction,
    ContractProContractAssignment,
    ContractProOversightEvent,
    ContractProPermissionRule,
)


class ContractProGrantError(Exception):
    pass


class ContractProGrantService:
    """
    Application-level enforcement for ContractProAccessGrant state transitions.

    activate_grant() is the single guarded path for moving a grant to active.
    The DB UniqueConstraint acts as a hard backstop; this service layer provides
    the clear error message before that constraint is reached.
    """

    @staticmethod
    def activate_grant(grant: ContractProAccessGrant) -> None:
        """
        Transition grant to active status.

        For full_contract_pro grants: enforces the one-active-full-per-business rule.
        For temp_contract_pro grants: no cardinality check (multiple temp grants may
        exist on different contracts within the same business).

        Raises ContractProGrantError if the cardinality rule would be violated.
        Raises ValueError if the grant is not in a state that can be activated
        (must be pending).
        """
        if grant.access_status != ContractProAccessGrant.STATUS_PENDING:
            raise ValueError(
                f"Only pending grants can be activated. "
                f"Current status: {grant.access_status}"
            )

        if grant.access_kind == ContractProAccessGrant.ACCESS_KIND_FULL:
            conflict = ContractProAccessGrant.objects.filter(
                business=grant.business,
                access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
                access_status=ContractProAccessGrant.STATUS_ACTIVE,
            ).exclude(pk=grant.pk).exists()

            if conflict:
                raise ContractProGrantError(
                    "This business already has an active full Contract Pro. "
                    "Revoke the existing grant before activating a new one."
                )

        grant.access_status = ContractProAccessGrant.STATUS_ACTIVE
        grant.accepted_at = timezone.now()
        grant.save(update_fields=["access_status", "accepted_at"])

        ContractProOversightService.record(
            event_type=ContractProOversightEvent.EVENT_GRANT_ACTIVATED,
            business=grant.business,
            grant=grant,
        )


class ContractProPermissionService:
    """
    Evaluates the effective permission state for a Contract Pro grant + action,
    applying the business-level ceiling rule.

    Callers:
        state = ContractProPermissionService.get_effective_state(grant, action)
        state = ContractProPermissionService.get_effective_state(grant, action, contract=c)

    Returns:
        ContractProPermissionRule.STATE_ACCESSIBLE or
        ContractProPermissionRule.STATE_BLOCKED
    """

    @staticmethod
    def get_effective_state(
        grant: ContractProAccessGrant,
        action: str,
        contract=None,
    ) -> str:
        """
        Return the effective permission state for the given grant and action.

        Evaluation order:
        1. If a contract-level rule exists and is blocked → return blocked immediately.
        2. Resolve the business-level state (explicit rule or default).
        3. If a contract-level rule exists and is accessible, cap it at the
           business-level state (contract cannot expand beyond ceiling).
        4. If no contract-level rule exists, return the business-level state.

        Default when no rule is stored:
          - Sensitive actions → blocked
          - All other actions → accessible
        """
        business_level_state = ContractProPermissionService._resolve_business_level(
            grant, action
        )

        if contract is not None:
            contract_rule = ContractProPermissionRule.objects.filter(
                grant=grant,
                action=action,
                contract=contract,
            ).first()

            if contract_rule is not None:
                if contract_rule.state == ContractProPermissionRule.STATE_BLOCKED:
                    return ContractProPermissionRule.STATE_BLOCKED
                # contract-level accessible: cap at business-level ceiling
                return business_level_state

        return business_level_state

    @staticmethod
    def _resolve_business_level(grant: ContractProAccessGrant, action: str) -> str:
        """
        Return the business-level state for the given grant and action.
        Checks for an explicit rule first; falls back to hardcoded defaults.
        """
        rule = ContractProPermissionRule.objects.filter(
            grant=grant,
            action=action,
            contract=None,
        ).first()

        if rule is not None:
            return rule.state

        # Default: sensitive actions blocked, everything else accessible
        if action in ContractProAction.SENSITIVE_ACTIONS:
            return ContractProPermissionRule.STATE_BLOCKED
        return ContractProPermissionRule.STATE_ACCESSIBLE


class ContractProEditingService:
    """
    Determines editing authority for a contract under the Contract Pro phase-one
    exclusivity rule:

      While an active delegated relationship controls a contract, only the
      Contract Pro edits the delegated workspace. The owner must revoke or
      unassign the delegation to regain direct editing control.

    Two public methods:

      get_active_editor_for_contract(contract)
          Returns the active ContractProAccessGrant holding editing authority,
          or None if no delegation is active.

      owner_editing_allowed(contract, owner_user)
          Returns True if the given user is the owner of the contract AND no
          active delegation is controlling it. Returns False otherwise.
    """

    @staticmethod
    def get_active_editor_for_contract(
        contract,
    ) -> Optional[ContractProAccessGrant]:
        """
        Return the active grant that currently holds editing authority for
        the given contract, or None.

        Resolution order:
        1. Selected-contract path — any active assignment (unassigned_at=None)
           to this contract from an active grant.
        2. Business-wide path — an active full_contract_pro grant with
           business_wide scope on the contract's business entity.

        The selected-contract path takes priority so that an explicit
        per-contract assignment is always the authoritative record.
        """
        # 1. Selected-contract path
        assignment = (
            ContractProContractAssignment.objects.filter(
                contract=contract,
                unassigned_at=None,
                grant__access_status=ContractProAccessGrant.STATUS_ACTIVE,
            )
            .select_related("grant")
            .first()
        )
        if assignment is not None:
            return assignment.grant

        # 2. Business-wide path (only applicable when contract has a business entity)
        if contract.entity_id is not None:
            biz_grant = ContractProAccessGrant.objects.filter(
                business_id=contract.entity_id,
                access_kind=ContractProAccessGrant.ACCESS_KIND_FULL,
                access_scope=ContractProAccessGrant.SCOPE_BUSINESS_WIDE,
                access_status=ContractProAccessGrant.STATUS_ACTIVE,
            ).first()
            if biz_grant is not None:
                return biz_grant

        return None

    @staticmethod
    def owner_editing_allowed(contract, owner_user) -> bool:
        """
        Return True if owner_user may directly edit the contract.

        Two conditions must both hold:
        1. owner_user is the owner of the contract.
           - Business contract (entity set): contract.entity.owner_id == owner_user.pk
           - Personal contract (entity not set): contract.initiator_id == owner_user.pk
        2. No active delegation is currently controlling editing for this contract.

        Returns False if either condition fails.

        Note: callers that traverse contract.entity in a loop should
        select_related("entity") on the contract queryset to avoid N+1 queries.
        """
        # Verify ownership
        if contract.entity_id is not None:
            if contract.entity.owner_id != owner_user.pk:
                return False
        else:
            if contract.initiator_id != owner_user.pk:
                return False

        # Check for active delegation
        active_editor = ContractProEditingService.get_active_editor_for_contract(
            contract
        )
        return active_editor is None


class ContractProOversightService:
    """
    Narrow helper for recording Contract Pro Oversight events.

    Only event types tied to already-implemented foundation paths are recorded here.
    Call sites must not invent event types — use the constants on
    ContractProOversightEvent.
    """

    @staticmethod
    def record(
        event_type: str,
        business,
        contract=None,
        grant=None,
        actor=None,
    ) -> ContractProOversightEvent:
        """
        Create and persist a ContractProOversightEvent.

        business is required (authority anchor).
        All other scope fields are optional — pass only what is naturally available
        at the call site without extra queries.
        """
        return ContractProOversightEvent.objects.create(
            event_type=event_type,
            business=business,
            contract=contract,
            grant=grant,
            actor=actor,
        )
