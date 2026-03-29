# backend/engine/contracts/domain/contract.py
from typing import List
from backend.engine.contracts.obligations.lifecycle import process_obligation_lifecycle


class Contract:
    """
    Contract domain entity.

    Responsible for:
    - Holding obligations
    - Executing obligation lifecycle
    - Aggregating contract state from obligations
    """

    def __init__(self, contract_id: int, obligations: List = None):
        self.contract_id = contract_id
        self.obligations = obligations or []

        # DO NOT hard-set "active"
        # Always derive state from obligations
        self._state = None
        self._refresh_contract_state()

    # ---------------------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------------------

    def add_obligation(self, obligation):
        self.obligations.append(obligation)
        self._refresh_contract_state()

    def refresh(self, now=None, obligation_repo=None):
        """
        Full lifecycle refresh:
        - Ticks each obligation
        - Re-aggregates contract state
        """

        for obligation in self.obligations:
            process_obligation_lifecycle(
                obligation,
                obligation_repo=obligation_repo,
                current_time=now,
            )

        self._refresh_contract_state()

    def refresh_state(self):
        """
        Public wrapper for contract state aggregation.
        """
        self._refresh_contract_state()

    def apply_payment(self, obligation, amount):
        """
        Applies payment to a specific obligation.
        """

        obligation.apply_payment(amount)

        # Recompute contract state immediately
        self._refresh_contract_state()

    # ---------------------------------------------------------------------
    # INTERNAL STATE AGGREGATION
    # ---------------------------------------------------------------------

    def _refresh_contract_state(self):
        """
        Aggregates contract state from obligation states.
        """

        if not self.obligations:
            self._state = "active"
            return

        states = {o.state for o in self.obligations}

        if "breached" in states or "defaulted" in states:
            self._state = "breached"
        elif states == {"resolved"}:
            self._state = "fulfilled"
        else:
            self._state = "active"



    
    @property
    def state(self):
        self._refresh_contract_state()
        return self._state









