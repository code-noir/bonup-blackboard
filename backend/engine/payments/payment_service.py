# backend/engine/payments/payment_service.py

from decimal import Decimal


class PaymentService:

    def __init__(self, gateway):
        self.gateway = gateway

    def process_payment(self, contract, obligation, amount):

        try:
            amount = Decimal(str(amount))

            if amount <= 0:
                return {
                    "success": False,
                    "error": "Invalid payment amount."
                }

            # simulate gateway success
            payment_result = self.gateway.charge(amount)

            if not payment_result["success"]:
                return payment_result

            # Apply payment through domain
            contract.apply_payment(obligation, amount)

            return {
                "success": True,
                "new_state": obligation.state,
                "remaining_balance": obligation.remaining_balance()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }




