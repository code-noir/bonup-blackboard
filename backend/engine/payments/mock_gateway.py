import uuid
from .gateway import PaymentGateway, PaymentResult


class MockPaymentGateway(PaymentGateway):
    """
    Fake processor for testing.
    """

    def charge(self, amount, currency="USD", metadata=None) -> PaymentResult:

        if amount <= 0:
            return PaymentResult(
                success=False,
                error="Invalid charge amount."
            )

        # simulate successful transaction
        return PaymentResult(
            success=True,
            transaction_id=str(uuid.uuid4())
        )
