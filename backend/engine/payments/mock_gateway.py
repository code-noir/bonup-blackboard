
# backend/engine/payments/mock_gateway.py

class MockPaymentGateway:

    def charge(self, amount):
        return {
            "success": True,
            "transaction_id": "mock_tx_123"
        }