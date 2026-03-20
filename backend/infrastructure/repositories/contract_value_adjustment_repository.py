#backend/infrastructure/repositories/contract_value_adjustment_repository.py

from backend.contracts.models import ContractValueAdjustment


class ContractValueAdjustmentRepository:
    """
    Persistence layer for stored contract value adjustments.
    """

    def create(self, **kwargs):
        return ContractValueAdjustment.objects.create(**kwargs)

    def list_for_contract(self, contract_id):
        return ContractValueAdjustment.objects.filter(contract_id=contract_id)

    def list_for_service_obligation(self, service_obligation_id):
        return ContractValueAdjustment.objects.filter(
            service_obligation_id=service_obligation_id
        )

    def list_for_payment_obligation(self, payment_obligation_id):
        return ContractValueAdjustment.objects.filter(
            payment_obligation_id=payment_obligation_id
        )

    def list_for_execution_event(self, execution_event_id):
        return ContractValueAdjustment.objects.filter(
            execution_event_id=execution_event_id
        )