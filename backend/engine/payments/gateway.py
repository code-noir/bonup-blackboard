from abc import ABC, abstractmethod


class PaymentResult:
    """
    Standardized payment response.
    """

    def __init__(self, success: bool, transaction_id: str = None, error: str = None):
        self.success = success
        self.transaction_id = transaction_id
        self.error = error


class PaymentGateway(ABC):
    """
    Abstract interface for any payment processor.
    """

    @abstractmethod
    def charge(self, amount, currency="USD", metadata=None) -> PaymentResult:
        pass