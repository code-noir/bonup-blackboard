# backend/engine/contracts/services/payment_service.py

from datetime import datetime

from backend.infrastructure.repositories.contract_obligation_repository import (
    ContractObligationRepository,
)

from backend.engine.contracts.obligations.state import (
    evaluate_obligation_state,
    evaluate_default_escalation,
)


class ContractPaymentService:
    """
    Handles payment application to a persisted obligation.
    """

    def __init__(
        self,
        obligation_repo: ContractObligationRepository,
    ):
        self.obligation_repo = obligation_repo

    def apply_payment(
        self,
        obligation_id,
        amount,
        grace_period_days: int = 3,
        max_default_days: int = 60,
    ):
        """
        Applies a payment to an obligation and updates its lifecycle state.
        """

        # 1️⃣ Load persisted obligation
        obligation = self.obligation_repo.get(obligation_id)

        # 2️⃣ Apply payment using engine primitive logic
        obligation.amount_paid += amount

        if obligation.amount_paid >= obligation.amount_due:
            obligation.amount_paid = obligation.amount_due
            obligation.state = "resolved"
        else:
            # 3️⃣ Evaluate state
            new_state = evaluate_obligation_state(
                obligation,
                grace_period_days=grace_period_days,
                current_time=datetime.utcnow(),
            )

            # 4️⃣ Evaluate default escalation
            final_state = evaluate_default_escalation(
                obligation,
                max_default_days=max_default_days,
                current_time=datetime.utcnow(),
            )

            obligation.state = final_state

        # 5️⃣ Persist update
        self.obligation_repo.save(obligation)

        return obligation