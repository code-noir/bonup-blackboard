
from decimal import Decimal
from backend.engine.payments.gateway import PaymentGateway


class PaymentService:

    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway

    def process_payment(self, contract, obligation, amount):

        amount = Decimal(str(amount))

        # 1️⃣ Charge gateway
        result = self.gateway.charge(amount)

        if not result.success:
            return {
                "success": False,
                "error": result.error
            }

        try:
            # 2️⃣ Route through aggregate
            contract.apply_payment(obligation, amount)

            return {
                "success": True,
                "transaction_id": result.transaction_id,
                "new_state": obligation.state,
                "remaining_balance": obligation.remaining_balance()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }



