# backend/engine/payments/mock_gateway.py

from .gateway import PaymentGateway, PaymentResult


class MockPaymentGateway(PaymentGateway):
    """
    Simulates a successful external payment provider.
    """

    def charge(self, amount, currency="USD", metadata=None) -> PaymentResult:
        return PaymentResult(success=True, transaction_id="mock_txn_123")
