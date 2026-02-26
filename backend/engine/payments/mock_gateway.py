# backend/engine/payments/mock_gateway.py

class MockPaymentGateway:
    """
    Simulates a successful external payment provider.
    """

    def charge(self, amount):
        return {
            "success": True,
            "transaction_id": "mock_txn_123"
        }

