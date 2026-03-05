# backend/engine/contracts/services/contract_projection_service.py

from dataclasses import dataclass
from typing import Optional, Dict

from backend.infrastructure.repositories.contract_repository import (
    ContractRepository,
)
from backend.infrastructure.repositories.contract_version_repository import (
    ContractVersionRepository,
)
from backend.infrastructure.repositories.contract_obligation_repository import (
    ContractObligationRepository,
)


# ==========================================================
# WORKSPACE PROJECTION
# ==========================================================

@dataclass
class ObligationSummary:
    total: int
    active: int
    overdue: int
    resolved: int


@dataclass
class ContractProjection:
    contract_id: int
    contract_status: str
    version_count: int
    active_version_id: Optional[int]
    signed_version_id: Optional[int]
    negotiation_open: bool
    can_edit: bool
    can_sign: bool
    can_request_change: bool
    obligation_summary: ObligationSummary


# ==========================================================
# WORKSPACE SERVICE
# ==========================================================

class ContractProjectionService:
    """
    Read-only projection layer for contract projection.
    Assembles contract, versions, and obligations into a formal read model.
    """

    def __init__(
        self,
        contract_repo: ContractRepository,
        version_repo: ContractVersionRepository,
        obligation_repo: ContractObligationRepository,
    ):
        self.contract_repo = contract_repo
        self.version_repo = version_repo
        self.obligation_repo = obligation_repo

    def get_contract_projection(self, contract_id: int) -> ContractProjection:
        contract = self.contract_repo.get(contract_id)

        versions = self.version_repo.get_all(contract)
        signed_version = self.version_repo.get_signed_version(contract)
        latest_version = self.version_repo.get_latest(contract)

        obligations = self.obligation_repo.get_by_contract(contract)

        # ------------------------------------------
        # Obligation Summary
        # ------------------------------------------

        total = len(obligations)
        active = len([o for o in obligations if o.state == "active"])
        overdue = len([o for o in obligations if o.state == "overdue"])
        resolved = len([o for o in obligations if o.state == "resolved"])

        summary = ObligationSummary(
            total=total,
            active=active,
            overdue=overdue,
            resolved=resolved,
        )

        # ------------------------------------------
        # Negotiation Logic
        # ------------------------------------------

        negotiation_open = any(v.status in ["draft", "negotiating"] for v in versions)

        can_edit = latest_version and latest_version.status == "draft"

        can_sign = latest_version and latest_version.status in ["negotiating", "sent"]

        can_request_change = signed_version is not None

        # ------------------------------------------
        # Projection
        # ------------------------------------------

        return ContractProjection(
            contract_id=contract.id,
            contract_status=contract.status,
            version_count=len(versions),
            active_version_id=latest_version.id if latest_version else None,
            signed_version_id=signed_version.id if signed_version else None,
            negotiation_open=negotiation_open,
            can_edit=bool(can_edit),
            can_sign=bool(can_sign),
            can_request_change=bool(can_request_change),
            obligation_summary=summary,
        )


