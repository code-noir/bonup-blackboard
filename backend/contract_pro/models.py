# backend/contract_pro/models.py

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ContractProAccessGrant(models.Model):
    """
    Records delegated access granted by a business owner to a Contract Pro user.

    Authority anchor: business FK.
    The owner is always derived via grant.business.owner — not stored here to
    avoid duplicate truth and owner/business mismatch risk.

    Cardinality rule: only one active full_contract_pro grant per business at a time.
    Enforced at:
      - application layer: ContractProGrantService.activate_grant()
      - database layer: UniqueConstraint with condition (hard backstop)

    Temp rule: temp_contract_pro must always use selected_contracts_only scope.
    Enforced via clean().
    """

    # --- access_kind choices ---
    ACCESS_KIND_FULL = "full_contract_pro"
    ACCESS_KIND_TEMP = "temp_contract_pro"
    ACCESS_KIND_CHOICES = [
        (ACCESS_KIND_FULL, "Full Contract Pro"),
        (ACCESS_KIND_TEMP, "Temp Contract Pro"),
    ]

    # --- access_scope choices ---
    SCOPE_BUSINESS_WIDE = "business_wide"
    SCOPE_SELECTED = "selected_contracts_only"
    SCOPE_CHOICES = [
        (SCOPE_BUSINESS_WIDE, "Business-wide"),
        (SCOPE_SELECTED, "Selected contracts only"),
    ]

    # --- access_status choices ---
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_DECLINED = "declined"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_REVOKED, "Revoked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    business = models.ForeignKey(
        "users.BusinessEntity",
        on_delete=models.CASCADE,
        related_name="contract_pro_grants",
    )

    contract_pro_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contract_pro_grants",
    )

    access_kind = models.CharField(max_length=30, choices=ACCESS_KIND_CHOICES)
    access_scope = models.CharField(max_length=30, choices=SCOPE_CHOICES)
    access_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    granted_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "access_kind"],
                condition=models.Q(
                    access_status="active",
                    access_kind="full_contract_pro",
                ),
                name="one_active_full_contract_pro_per_business",
            )
        ]

    def clean(self):
        if (
            self.access_kind == self.ACCESS_KIND_TEMP
            and self.access_scope != self.SCOPE_SELECTED
        ):
            raise ValidationError(
                "Temp Contract Pro access must use selected_contracts_only scope."
            )

    def __str__(self):
        return (
            f"{self.access_kind} | {self.business_id} | "
            f"{self.contract_pro_user_id} | {self.access_status}"
        )


# ============================================================
# ACTION CONSTANTS
# ============================================================

class ContractProAction:
    """
    Canonical action key list for the Contract Pro permission matrix.

    Sensitive actions are blocked by default; all others are accessible by default.
    These strings are stored in ContractProPermissionRule.action.
    """

    # --- sensitive: blocked by default ---
    SIGN_FOR_OWNER = "sign_for_owner"
    TRIGGER_PAYMENT_REQUEST = "trigger_payment_request"
    CHANGE_PAYOUT_DESTINATION = "change_payout_destination"
    APPROVE_PAYMENT_RELEASE = "approve_payment_release"
    CHANGE_BUSINESS_SETTINGS = "change_business_settings"

    # --- contract work: accessible by default ---
    CREATE_CONTRACT = "create_contract"
    EDIT_CONTRACT_WORKSPACE = "edit_contract_workspace"
    VIEW_CONTRACT = "view_contract"
    NEGOTIATE_TERMS = "negotiate_terms"
    UPLOAD_CONTRACT_DOCUMENTS = "upload_contract_documents"
    START_BOARDROOM_SESSION = "start_boardroom_session"
    START_EXTERNAL_SESSION = "start_external_session"
    CREATE_OBLIGATION = "create_obligation"
    VIEW_OBLIGATIONS = "view_obligations"
    MESSAGE_OWNER = "message_owner"

    SENSITIVE_ACTIONS = frozenset({
        SIGN_FOR_OWNER,
        TRIGGER_PAYMENT_REQUEST,
        CHANGE_PAYOUT_DESTINATION,
        APPROVE_PAYMENT_RELEASE,
        CHANGE_BUSINESS_SETTINGS,
    })

    ALL_ACTIONS = frozenset({
        SIGN_FOR_OWNER,
        TRIGGER_PAYMENT_REQUEST,
        CHANGE_PAYOUT_DESTINATION,
        APPROVE_PAYMENT_RELEASE,
        CHANGE_BUSINESS_SETTINGS,
        CREATE_CONTRACT,
        EDIT_CONTRACT_WORKSPACE,
        VIEW_CONTRACT,
        NEGOTIATE_TERMS,
        UPLOAD_CONTRACT_DOCUMENTS,
        START_BOARDROOM_SESSION,
        START_EXTERNAL_SESSION,
        CREATE_OBLIGATION,
        VIEW_OBLIGATIONS,
        MESSAGE_OWNER,
    })


# ============================================================
# PERMISSION RULE MODEL
# ============================================================

class ContractProPermissionRule(models.Model):
    """
    A single explicit action-level permission rule for a Contract Pro access grant.

    Level distinction:
      - contract=None  → business-level rule (applies across all contracts in the grant)
      - contract=<FK>  → contract-level rule (applies to that specific contract only)

    Override rule:
      Business-level rules are the ceiling.
      A contract-level rule may restrict (accessible → blocked) but may not expand
      (blocked → accessible) beyond the business-level ceiling.
      Evaluation is handled by ContractProPermissionService.get_effective_state().

    Default fallback (no rule stored):
      - Sensitive actions (ContractProAction.SENSITIVE_ACTIONS) → blocked
      - All other actions → accessible
    """

    STATE_ACCESSIBLE = "accessible"
    STATE_BLOCKED = "blocked"
    STATE_CHOICES = [
        (STATE_ACCESSIBLE, "Accessible"),
        (STATE_BLOCKED, "Blocked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    grant = models.ForeignKey(
        ContractProAccessGrant,
        on_delete=models.CASCADE,
        related_name="permission_rules",
    )

    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="contract_pro_permission_rules",
        null=True,
        blank=True,
    )

    action = models.CharField(max_length=60)
    state = models.CharField(max_length=20, choices=STATE_CHOICES)
    set_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["grant", "action", "contract"],
                name="unique_permission_rule_per_grant_action_contract",
            ),
            models.UniqueConstraint(
                fields=["grant", "action"],
                condition=models.Q(contract__isnull=True),
                name="unique_business_level_permission_per_grant_action",
            ),
        ]

    def __str__(self):
        level = f"contract={self.contract_id}" if self.contract_id else "business-level"
        return f"{self.action} | {self.state} | {level} | grant={self.grant_id}"


class ContractProContractAssignment(models.Model):
    """
    Links a specific contract to a ContractProAccessGrant.

    Used when access_scope is selected_contracts_only (including all temp grants).
    Not required for business_wide grants.

    unassigned_at=None means the assignment is current.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    grant = models.ForeignKey(
        ContractProAccessGrant,
        on_delete=models.CASCADE,
        related_name="contract_assignments",
    )

    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="contract_pro_assignments",
    )

    assigned_at = models.DateTimeField(auto_now_add=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"assignment | grant={self.grant_id} | contract={self.contract_id}"


# ============================================================
# OVERSIGHT EVENT MODEL
# ============================================================

class ContractProOversightEvent(models.Model):
    """
    A structured record of an important Contract Pro foundation event.

    Scope:
      business  — always set; authority anchor.
      contract  — set for contract-scoped events; null for business-scoped events.
      grant     — set when the event is naturally tied to a specific grant;
                  null when not available at the call site without an extra query.
      actor     — set when the event has a human actor (e.g. request.user);
                  null for system-generated events.

    Only event types tied to already-implemented foundation paths are defined here.
    Speculative future types must not be added until the path exists.
    """

    EVENT_GRANT_ACTIVATED = "grant_activated"
    EVENT_OWNER_EDIT_BLOCKED = "owner_edit_blocked"
    EVENT_TYPE_CHOICES = [
        (EVENT_GRANT_ACTIVATED, "Grant activated"),
        (EVENT_OWNER_EDIT_BLOCKED, "Owner edit blocked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    business = models.ForeignKey(
        "users.BusinessEntity",
        on_delete=models.CASCADE,
        related_name="oversight_events",
    )

    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="oversight_events",
        null=True,
        blank=True,
    )

    grant = models.ForeignKey(
        ContractProAccessGrant,
        on_delete=models.SET_NULL,
        related_name="oversight_events",
        null=True,
        blank=True,
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="contract_pro_oversight_events",
        null=True,
        blank=True,
    )

    event_type = models.CharField(max_length=60, choices=EVENT_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} | business={self.business_id} | {self.created_at}"
