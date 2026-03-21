#backend/infrastructure/repositories/contract_obligation_promotion_repository.py

from backend.contracts.models import ContractObligationPromotion


class ContractObligationPromotionRepository:
    """
    Persistence layer for execution-event -> side-obligation promotions.
    """

    def create(self, **kwargs):
        return ContractObligationPromotion.objects.create(**kwargs)

    def list_for_contract(self, contract_id):
        return ContractObligationPromotion.objects.filter(contract_id=contract_id)

    def list_for_parent_service_obligation(self, service_obligation_id):
        return ContractObligationPromotion.objects.filter(
            parent_service_obligation_id=service_obligation_id
        )

    def list_for_execution_event(self, execution_event_id):
        return ContractObligationPromotion.objects.filter(
            source_execution_event_id=execution_event_id
        )

    def find_for_execution_event(self, execution_event_id):
        return ContractObligationPromotion.objects.filter(
            source_execution_event_id=execution_event_id
        ).first()

