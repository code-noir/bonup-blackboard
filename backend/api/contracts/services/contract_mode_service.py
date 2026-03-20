#backend/api/contracts/services/contract_mode_service.py

from backend.contracts.models import ContractObligation, ContractServiceObligation
from backend.contracts.contract_mode import ContractMode


class ContractModeService:
    """
    Derives contract mode from the obligation mix currently attached to a contract.

    Rules:
    - payment only -> payment_to_payment
    - service only -> service_to_service
    - both service and payment -> service_to_payment
    - no obligations yet -> undetermined
    """

    def derive_mode(self, *, contract_id):
        payment_count = ContractObligation.objects.filter(contract_id=contract_id).count()
        service_count = ContractServiceObligation.objects.filter(contract_id=contract_id).count()

        if payment_count > 0 and service_count > 0:
            return ContractMode.SERVICE_TO_PAYMENT.value

        if payment_count > 0 and service_count == 0:
            return ContractMode.PAYMENT_TO_PAYMENT.value

        if service_count > 0 and payment_count == 0:
            return ContractMode.SERVICE_TO_SERVICE.value

        return ContractMode.UNDETERMINED.value




