# backend/engine/contracts/services/contract_version_service.py
#
# NOT ON THE LIVE API PATH — DO NOT BUILD ON THIS WITHOUT REPAIR.
#
# The live contract version flow is in:
#   backend/api/contracts/version_views.py
#   (mounted at /api/contracts/<id>/versions/, .../sign/, .../reject/)
#
# This engine-level service is not imported by any live view or factory.
# It is only referenced by test_full_contract_cycle.py, which itself
# runs 0 tests due to an indentation bug (see that file).
#
# KNOWN BREAKAGE:
#   transition_version() and sign_version() both call
#   self.version_repo.get(version_id), but ContractVersionRepository
#   has no get() method — this would raise AttributeError at runtime.
#
# Before activating this path, the repository interface must be extended
# and the engine service must be wired to the API layer.

from backend.engine.contracts.versioning import calculate_next_version

from backend.engine.contracts.state_machine import validate_transition
from backend.engine.contracts.exceptions import NegotiationLimitReached
from backend.infrastructure.repositories.contract_repository import (
    ContractRepository,
)
from backend.infrastructure.repositories.contract_version_repository import (
    ContractVersionRepository,
)
from backend.engine.contracts.services.activation_service import (
    ContractActivationService,
)


class ContractVersionService:
    """
    Engine-level contract version orchestration.

    Responsible for:
    - Version creation
    - Version transitions
    - Negotiation enforcement
    - Signing enforcement
    - Superseding previous signed versions
    - Triggering activation
    """

    def __init__(
        self,
        contract_repo: ContractRepository,
        version_repo: ContractVersionRepository,
        activation_service: ContractActivationService,
    ):
        self.contract_repo = contract_repo
        self.version_repo = version_repo
        self.activation_service = activation_service

        # ==========================================================
        # VERSION CREATION
        # ==========================================

    def create_revision(self, contract_id, content, user=None):
        contract = self.contract_repo.get(contract_id)

        current_count = self.version_repo.count(contract)

        next_number = calculate_next_version(
            current_count=current_count,
            max_versions=contract.max_versions,
        )

        latest = self.version_repo.get_latest(contract)  # ← THIS LINE

        return self.version_repo.create(
            contract=contract,
            version_number=next_number,
            content_snapshot=content,
            created_by=user,
            previous_version=latest,
            status="draft",
        )



    # ==========================================================
    # TRANSITIONS
    # ==========================================================

    def transition_version(self, version_id, new_status):
        """
        Enforces state machine transitions.
        """

        version = self.version_repo.get(version_id)

        validate_transition(version.status, new_status)

        version.status = new_status
        self.version_repo.save(version)

        return version

    # ==========================================================
    # SIGNING LOGIC (AMENDMENT SAFE)
    # ==========================================================

    def sign_version(
        self,
        version_id,
        obligor_id=None,
        obligee_id=None,
        amount=None,
        installments=None,
        interval_days=None,
        start_date=None,
    ):
        """
        Signs a version.

        Rules:
        - Only valid transition allowed
        - Only one signed version active at a time
        - Previous signed version becomes superseded
        - Old obligations remain intact
        - Activation triggers only for this version
        """

        version = self.version_repo.get(version_id)
        contract = version.contract

        # Validate transition
        validate_transition(version.status, "signed")

        # Supersede existing signed version (if any)
        existing_signed = self.version_repo.get_signed_version(contract)

        if existing_signed and existing_signed.id != version.id:
            existing_signed.superseded = True
            existing_signed.status = "archived"
            self.version_repo.save(existing_signed)

        # Sign new version
        version.status = "signed"
        self.version_repo.save(version)

        # Trigger activation only if obligation parameters provided
        if all([obligor_id, obligee_id, amount, installments, interval_days]):
            self.activation_service.activate_contract(
                contract_id=contract.id,
                obligor_id=obligor_id,
                obligee_id=obligee_id,
                amount=amount,
                installments=installments,
                interval_days=interval_days,
                start_date=start_date,
            )

        return version


