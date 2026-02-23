from datetime import datetime
from backend.engine.contracts.obligations.state import evaluate_obligation_state


class Contract:
    """
    Domain aggregate root for contract lifecycle.
    Owns obligations and enforces invariants.
    """

    def __init__(self, contract_id, obligations=None):
        self.contract_id = contract_id
        self.obligations = obligations or []
        self.state = "active"

    # ------------------------------------------------------------
    # PAYMENT ENTRY POINT
    # ------------------------------------------------------------

    def apply_payment(self, obligation, amount):

        if obligation not in self.obligations:
            raise ValueError("Obligation does not belong to contract.")

        # Apply monetary change
        obligation.apply_payment(amount)

        # Recalculate obligation lifecycle
        new_state = evaluate_obligation_state(
            obligation,
            current_time=datetime.utcnow()
        )

        obligation.state = new_state

        # Recalculate overall contract state
        self._refresh_contract_state()

    # ------------------------------------------------------------
    # LIFECYCLE REFRESH
    # ------------------------------------------------------------

    def refresh(self, now=None):

        if now is None:
            now = datetime.utcnow()

        for obligation in self.obligations:
            new_state = evaluate_obligation_state(
                obligation,
                current_time=now
            )
            obligation.state = new_state

        self._refresh_contract_state()

    # ------------------------------------------------------------
    # CONTRACT STATE AGGREGATION
    # ------------------------------------------------------------

    def _refresh_contract_state(self):

        if not self.obligations:
            self.state = "active"
            return

        states = [o.state for o in self.obligations]

        if "defaulted" in states:
            self.state = "breached"
            return

        if all(state == "resolved" for state in states):
            self.state = "fulfilled"
            return

        self.state = "active"







