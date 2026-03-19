#backend/infrastructure/repositories/obligation_execution_repository.py

from backend.contracts.models import (
    ObligationExecutionSession,
    ObligationExecutionEvent,
)


class ObligationExecutionRepository:
    """
    Persistence layer for obligation execution sessions and events.
    """

    def create_session(
        self,
        *,
        payment_obligation=None,
        service_obligation=None,
        started_at,
        status="active",
    ):
        return ObligationExecutionSession.objects.create(
            payment_obligation=payment_obligation,
            service_obligation=service_obligation,
            started_at=started_at,
            status=status,
        )

    def close_session(self, session, ended_at):
        session.ended_at = ended_at
        session.status = "closed"
        session.save(update_fields=["ended_at", "status"])
        return session

    def create_event(
        self,
        *,
        session,
        event_type,
        summary,
        task=None,
        observation=None,
        estimated_duration_minutes=None,
        estimated_cost_amount=None,
        estimated_cost_currency=None,
        planned_execution_time=None,
        metadata=None,
    ):
        return ObligationExecutionEvent.objects.create(
            session=session,
            event_type=event_type,
            task=task,
            observation=observation,
            summary=summary,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_cost_amount=estimated_cost_amount,
            estimated_cost_currency=estimated_cost_currency,
            planned_execution_time=planned_execution_time,
            metadata=metadata or {},
        )
