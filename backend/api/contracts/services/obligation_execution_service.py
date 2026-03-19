#backend/api/contracts/services/obligation_execution_service.py

from django.utils import timezone

from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
)
from backend.infrastructure.repositories.obligation_execution_repository import (
    ObligationExecutionRepository,
)
from backend.engine.lifecycle_core.execution.primitives import ExecutionItem
from backend.engine.lifecycle_core.execution.evaluator import ExecutionEvaluator


class ObligationExecutionService:
    """
    Contract-side application service for execution sessions and events.

    Responsibilities:
    - open execution sessions
    - record execution events
    - evaluate execution items through the engine
    """

    def __init__(self):
        self.repo = ObligationExecutionRepository()
        self.evaluator = ExecutionEvaluator()

    def open_session(
        self,
        *,
        obligation_type,
        obligation_id,
        started_at=None,
    ):
        if started_at is None:
            started_at = timezone.now()

        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)
            return self.repo.create_session(
                payment_obligation=obligation,
                started_at=started_at,
            )

        if obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            return self.repo.create_session(
                service_obligation=obligation,
                started_at=started_at,
            )

        raise Exception("Invalid obligation type")

    def record_execution_item(
        self,
        *,
        session,
        task,
        observation,
        summary,
        estimated_duration_minutes,
        estimated_cost_amount,
        estimated_cost_currency,
        planned_execution_time=None,
        metadata=None,
    ):
        item = ExecutionItem(
            task=task,
            observation=observation,
            summary=summary,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_cost_amount=estimated_cost_amount,
            estimated_cost_currency=estimated_cost_currency,
            planned_execution_time=planned_execution_time,
        )

        decision = self.evaluator.evaluate(item)

        event = self.repo.create_event(
            session=session,
            event_type="execution_item_recorded",
            task=item.task,
            observation=item.observation,
            summary=item.summary,
            estimated_duration_minutes=item.estimated_duration_minutes,
            estimated_cost_amount=item.estimated_cost_amount,
            estimated_cost_currency=item.estimated_cost_currency,
            planned_execution_time=item.planned_execution_time,
            metadata={
                "decision_status": decision.decision_status,
                "authorization_mode": decision.authorization_mode,
                "billing_mode": decision.billing_mode,
                "promotion_suggestion": decision.promotion_suggestion,
                "required_next_step": decision.required_next_step,
                "rationale": decision.rationale,
                "proof_tags": decision.proof_tags,
                **(metadata or {}),
            },
        )

        return {
            "event": event,
            "decision": decision,
        }

    def close_session(self, *, session, ended_at=None):
        if ended_at is None:
            ended_at = timezone.now()

        return self.repo.close_session(session, ended_at=ended_at)

