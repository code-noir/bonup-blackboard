# backend/engine/contracts/domain/contract.py

from typing import List


class Contract:
    """
    Contract domain entity.

    Responsible for:
    - Holding obligations
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

    def refresh_state(self):
        """
        Public trigger if external services mutate obligations.
        """
        self._refresh_contract_state()

    # ---------------------------------------------------------------------
    # INTERNAL STATE AGGREGATION
    # ---------------------------------------------------------------------

    def _refresh_contract_state(self):
        """
        Aggregates contract state from obligation states.

        Rules:
        - If no obligations → active
        - If ANY obligation is defaulted → breached
        - If ALL obligations are resolved → fulfilled
        - Otherwise → active
        """

        if not self.obligations:
            self.state = "active"
            return

        states = {o.state for o in self.obligations}

        # Optional safety guard — remove if you don't want strict mode
        allowed_states = {"pending", "active", "resolved", "defaulted"}
        unknown = states - allowed_states
        if unknown:
            raise ValueError(f"Unknown obligation states detected: {unknown}")

        # Rule 1 — Breach dominates everything
        if "defaulted" in states:
            self.state = "breached"
            return

        # Rule 2 — Fulfilled only if ALL resolved
        if states == {"resolved"}:
            self.state = "fulfilled"
            return

        # Rule 3 — Otherwise still active
        self.state = "active"












