from datetime import datetime

from backend.engine.contracts.obligations.state import evaluate_obligation_state


class Contract:
    """
    Aggregate root for contract lifecycle.
    Owns obligations and contract-level state.
    """

    def __init__(self, contract_id, obligations):
        self.contract_id = contract_id
        self.obligations = obligations
        self.state = self._evaluate_state()

    # ------------------------------------------------------------
    # PAYMENT ENTRY POINT
    # ------------------------------------------------------------

    def apply_payment(self, obligation, amount):
        """
        Apply payment through contract boundary.
        """
        obligation.apply_payment(amount)
        self.refresh()

    # ------------------------------------------------------------
    # LIFECYCLE REFRESH
    # ------------------------------------------------------------

    def refresh(self, now=None):

        if not now:
            now = datetime.utcnow()

        for obligation in self.obligations:
            obligation.state = evaluate_obligation_state(
                obligation,
                current_time=now
            )

        self.state = self._evaluate_state()

    # ------------------------------------------------------------
    # CONTRACT STATE LOGIC
    # ------------------------------------------------------------

    def _evaluate_state(self):

        if not self.obligations:
            return "active"

        states = [o.state for o in self.obligations]

        if "defaulted" in states:
            return "breached"

        if all(state == "resolved" for state in states):
            return "fulfilled"

        return "active"




