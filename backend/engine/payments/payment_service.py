# backend/engine/payments/payment_service.py

from decimal import Decimal

from backend.engine.contracts.obligations.lifecycle import (
    process_obligation_lifecycle,
)

class PaymentService:

    def __init__(self, gateway):
        self.gateway = gateway

    def process_payment(self, contract, obligation, amount):
        amount = Decimal(str(amount))

        if amount <= 0:
            return {
                "success": False,
                "error": "Invalid payment amount."
            }

        payment_result = self.gateway.charge(amount)
        print("DEBUG gateway result:", payment_result)

        if not payment_result.get("success"):
            return payment_result

        # Apply domain payment
        contract.apply_payment(obligation, amount)

        # 🔥 Re-run lifecycle after payment
        process_obligation_lifecycle(
            obligation,
            obligation_repo=contract.obligation_repo,  # see note below
        )

        print("DEBUG amount_paid after apply:", obligation.amount_paid)

        return {
            "success": True,
            "new_state": obligation.state,
            "remaining_balance": obligation.remaining_balance(),
        }






