# backend/engine/contracts/services/payment_service.py
#
# NOT ON THE LIVE API PATH — DO NOT BUILD ON THIS WITHOUT REPAIR.
#
# ContractPaymentService is not imported by any live view or factory.
# No tests exercise this class.
#
# KNOWN BREAKAGE:
#   apply_payment() calls self.obligation_repo.get(obligation_id) and
#   self.obligation_repo.save(obligation) — neither method exists on
#   ContractObligationRepository → AttributeError at runtime if called.
#
# The live payment path is:
#   backend/api/payments/views.py — direct ORM on the Payment model.
#   PaymentConfirmAPIView / PaymentRefundAPIView / PaymentReverseAPIView
#   call process_obligation_lifecycle() inline to sync obligation state.
#
# Before activating this path, ContractObligationRepository must be
# extended with get() and save() methods.

from django.utils import timezone

from backend.infrastructure.repositories.contract_obligation_repository import (
    ContractObligationRepository,
)

from backend.engine.contracts.obligations.lifecycle import (
    process_obligation_lifecycle,
)


class ContractPaymentService:
    """
    Handles payment application to a persisted obligation.

    Lifecycle state is ALWAYS determined by the lifecycle engine.
    No service is allowed to assign state directly.
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
        current_time=None,
    ):
        """
        Applies payment facts only.
        Lifecycle engine determines resulting state.
        """

        if current_time is None:
            current_time = timezone.now()

        # 1️⃣ Load persisted obligation
        obligation = self.obligation_repo.get(obligation_id)

        # 2️⃣ Apply payment fact (engine primitive logic)
        obligation.apply_payment(amount)

        # 3️⃣ Run lifecycle engine (single source of truth)
        new_state = process_obligation_lifecycle(
            obligation,
            current_time=current_time,
        )

        # 4️⃣ Persist state ONLY if changed
        if obligation.state != new_state:
            self.obligation_repo.update_state(
                obligation=obligation,
                new_state=new_state,
                current_time=current_time,
            )
        else:
            # Still persist payment mutation (amount_paid change)
            self.obligation_repo.save(obligation)

        return obligation


