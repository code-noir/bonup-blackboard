#backend/contracts/contract_mode.py
from enum import Enum


class ContractMode(str, Enum):
    """
    High-level contract relationship mode derived from obligation composition.
    """

    UNDETERMINED = "undetermined"
    PAYMENT_TO_PAYMENT = "payment_to_payment"
    SERVICE_TO_SERVICE = "service_to_service"
    SERVICE_TO_PAYMENT = "service_to_payment"
