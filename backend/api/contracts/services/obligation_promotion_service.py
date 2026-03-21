
# backend/api/contracts/services/obligation_promotion_service.py

from backend.contracts.models import (
    ContractServiceObligation,
    ObligationExecutionEvent,
)
from backend.infrastructure.repositories.contract_obligation_promotion_repository import (
    ContractObligationPromotionRepository,
)


class ObligationPromotionService:
    """
    Promotes an execution event into a side service obligation.
    """

    def __init__(self):
        self.repo = ContractObligationPromotionRepository()

    def promote_execution_event_to_service_obligation(
        self,
        *,
        execution_event_id,
        summary=None,
        due_date=None,
    ):
        existing = self.repo.find_for_execution_event(execution_event_id)
        if existing is not None:
            return existing

        execution_event = ObligationExecutionEvent.objects.select_related(
            "session__service_obligation__contract",
            "session__service_obligation__version",
            "session__service_obligation__obligor",
            "session__service_obligation__obligee",
        ).get(id=execution_event_id)

        parent_service_obligation = execution_event.session.service_obligation
        if parent_service_obligation is None:
            raise Exception("Execution event is not linked to a service obligation")

        description = summary or execution_event.summary or execution_event.task or "Promoted side obligation"
        new_due_date = due_date or parent_service_obligation.due_date

        promoted_service_obligation = ContractServiceObligation.objects.create(
            contract=parent_service_obligation.contract,
            version=parent_service_obligation.version,
            obligor=parent_service_obligation.obligor,
            obligee=parent_service_obligation.obligee,
            description=description,
            due_date=new_due_date,
            state="active",
        )

        promotion = self.repo.create(
            contract=parent_service_obligation.contract,
            source_execution_event=execution_event,
            parent_service_obligation=parent_service_obligation,
            promoted_service_obligation=promoted_service_obligation,
            summary=f"Execution event promoted to side obligation: {description}",
        )

        return promotion

