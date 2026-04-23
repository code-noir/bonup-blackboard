# backend/engine/payments/payment_service.py
#
# ENGINE-LEVEL ONLY — NOT WIRED TO THE LIVE API.
#
# PaymentService is a working pure-engine payment implementation.
# Its tests (engine/payments/tests/test_payment_service.py) run and pass (5/5).
# It operates on domain Contract and PaymentObligation objects via a gateway
# interface (MockPaymentGateway in tests).
#
# It is NOT imported by any live API view. The live payment path is:
#   backend/api/payments/views.py — direct ORM on the Payment model,
#   with process_obligation_lifecycle() called inline on confirm/refund/reverse.
#
# This service represents a gateway-aware engine approach that could be
# wired to the API layer in the future, but is not currently connected.

from decimal import Decimal
from django.utils import timezone

from backend.engine.contracts.obligations.lifecycle import process_obligation_lifecycle


class PaymentService:
    """
    Service responsible for applying payments to obligations.
    """

    def __init__(self, gateway, obligation_repo=None):
        self.gateway = gateway
        self.obligation_repo = obligation_repo

    def process_payment(self, contract, obligation, amount, now=None):
        if now is None:
            now = timezone.now()

        amount = Decimal(str(amount))

        if amount <= 0:
            return {"success": False, "error": "Invalid payment amount."}

        # Charge gateway
        result = self.gateway.charge(amount)
        if not result.success:
            return {"success": False, "error": result.error}

        # Apply payment to obligation via contract

        contract.apply_payment(obligation, amount)

        # recompute contract state
        contract.refresh_state()


        # Re-run lifecycle AFTER payment so state reflects deadline/balance
        process_obligation_lifecycle(
            obligation,
            obligation_repo=self.obligation_repo,  # safe if None
            current_time=now,
        )

        # Persist obligation if repo exists
        if self.obligation_repo is not None:
            self.obligation_repo.save(obligation)

        return {
            "success": True,
            "new_state": obligation.state,
            "remaining_balance": obligation.remaining_balance(),
        }















