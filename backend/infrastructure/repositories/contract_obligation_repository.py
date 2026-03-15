# backend/infrastructure/repositories/contract_obligation_repository.py

from datetime import datetime
from typing import Optional

from backend.contracts.models import ContractObligation


class ContractObligationRepository:
    """
    Persistence layer for ContractObligation.
    """

    # ------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------

    def create(self, **kwargs):
        return ContractObligation.objects.create(**kwargs)

    def bulk_create(self, obligations):
        return ContractObligation.objects.bulk_create(obligations)

    # ------------------------------------------------------------
    # READ
    # ------------------------------------------------------------

    def filter_by_contract(self, contract):
        return ContractObligation.objects.filter(contract=contract)

    def list_candidates(self, contract_id: Optional[str] = None, limit: Optional[int] = None):
        """
        Returns obligations eligible for lifecycle evaluation.

        By default:
        - Only active contracts
        - Excludes terminal states (resolved, breached)
        """

        queryset = ContractObligation.objects.filter(
            contract__is_active=True
        ).exclude(
            state__in=["resolved", "breached"]
        )

        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)

        if limit:
            queryset = queryset[:limit]

        return queryset

    # ------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------

    def update_state(self, obligation, new_state: str, current_time: datetime):
        """
        Persist lifecycle state change.
        """

        obligation.state = new_state

        # Optional: mark defaulted flag
        if new_state in ["defaulted", "breached"]:
            obligation.is_defaulted = True
        else:
            obligation.is_defaulted = False

        obligation.updated_at = current_time
        obligation.save(update_fields=["state", "is_defaulted", "updated_at"])

        return obligation


