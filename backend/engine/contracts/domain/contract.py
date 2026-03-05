# backend/engine/contracts/domain/contract.py

from typing import List
from backend.engine.contracts.obligations.lifecycle import (
    process_obligation_lifecycle,
)


class Contract:
    """
    Contract domain entity.

    Responsible for:
    - Holding obligations
    - Executing obligation lifecycle
    - Aggregating contract state from obligations
    """

    def __init__(self, contract_id: int, obligations: List):
        self.contract_id = contract_id
        self.obligations = obligations or []
        self.state = "active"

        # Initial aggregation
        self._refresh_contract_state()

    # ---------------------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------------------

    def add_obligation(self, obligation):
        self.obligations.append(obligation)
        self._refresh_contract_state()

    def refresh(self, now):
        """
        Full lifecycle refresh:
        - Ticks each obligation
        - Re-aggregates contract state
        """
        for obligation in self.obligations:
            process_obligation_lifecycle(
            obligation,
            obligation_repo=self.obligation_repo,
            current_time=now,
)


        self._refresh_contract_state()

    # ---------------------------------------------------------------------
    # INTERNAL STATE AGGREGATION
    # ---------------------------------------------------------------------

    def _refresh_contract_state(self):
        """
        Aggregates contract state from obligation states.

        Rules:
        - If no obligations → active
        - If ANY obligation is defaulted or breached → breached
        - If ALL obligations are resolved → fulfilled
        - Otherwise → active
        """

        if not self.obligations:
            self.state = "active"
            return

        states = {o.state for o in self.obligations}

        # Expanded allowed states to match lifecycle_core
        allowed_states = {
            "pending",
            "active",
            "overdue",
            "defaulted",
            "resolved",
            "breached",
        }

        unknown = states - allowed_states
        if unknown:
            raise ValueError(f"Unknown obligation states detected: {unknown}")

        # Breach dominates everything
        if "breached" in states or "defaulted" in states:
            self.state = "breached"
            return

        # Fulfilled only if ALL resolved
        if states == {"resolved"}:
            self.state = "fulfilled"
            return

        # Otherwise active
        self.state = "active"



    def apply_payment(self, obligation, amount):
        """
        Applies payment to a specific obligation.
        """

        obligation.apply_payment(amount)

        # If all obligations are resolved, update contract state
        if all(ob.state == "resolved" for ob in self.obligations):
            self.state = "fulfilled"











