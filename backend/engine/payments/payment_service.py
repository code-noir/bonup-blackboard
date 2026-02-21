
from decimal import Decimal
from backend.engine.payments.gateway import PaymentGateway
from backend.engine.contracts.obligations.lifecycle import evaluate_obligation_state


class PaymentService:

    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway

    def process_payment(self, obligation_instance, amount):

        amount = Decimal(str(amount))

        # 1️⃣ Call external processor
        result = self.gateway.charge(amount)

        if not result.success:
            return {
                "success": False,
                "error": result.error
            }

        # 2️⃣ Apply payment to obligation
        obligation_instance.apply_payment(amount)

        # 3️⃣ Re-evaluate state
        new_state = evaluate_obligation_state(obligation_instance)

        return {
            "success": True,
            "transaction_id": result.transaction_id,
            "new_state": new_state,
            "remaining_balance": obligation_instance.remaining_balance()
        }


