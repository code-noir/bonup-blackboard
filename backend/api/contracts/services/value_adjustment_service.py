#backend/api/contracts/services/value_adjustment_service.py


from backend.engine.lifecycle_core.execution.adjustments import ExecutionAdjustmentBuilder
from backend.engine.lifecycle_core.obligations.primitives import ServiceObligation
from backend.infrastructure.repositories.contract_value_adjustment_repository import (
    ContractValueAdjustmentRepository,
)


class ValueAdjustmentService:
    """
    Stores contract-side value adjustments from engine or execution outcomes.
    """

    def __init__(self):
        self.repo = ContractValueAdjustmentRepository()
        self.adjustment_builder = ExecutionAdjustmentBuilder()

    def store_lateness_adjustment(
        self,
        *,
        service_obligation,
        base_amount,
        currency="USD",
        adjustment_enabled,
        adjustment_mode=None,
        adjustment_value=None,
    ):
        engine_obligation = ServiceObligation(
            obligor_id=service_obligation.obligor_id,
            obligee_id=service_obligation.obligee_id,
            description=service_obligation.description,
            due_date=service_obligation.due_date,
            state=service_obligation.state,
        )
        engine_obligation.completed_at = service_obligation.completed_at

        adjustment = self.adjustment_builder.build_lateness_adjustment(
            obligation=engine_obligation,
            base_amount=base_amount,
            currency=currency,
            adjustment_enabled=adjustment_enabled,
            adjustment_mode=adjustment_mode,
            adjustment_value=adjustment_value,
        )

        if adjustment is None:
            return None

        return self.repo.create(
            contract=service_obligation.contract,
            service_obligation=service_obligation,
            adjustment_type=adjustment.adjustment_type,
            mode=adjustment.mode,
            amount=adjustment.amount,
            currency=adjustment.currency,
            summary=adjustment.summary,
        )

    def store_additional_charge(
        self,
        *,
        contract,
        execution_event,
        amount,
        currency,
        summary,
        service_obligation=None,
        payment_obligation=None,
    ):
        return self.repo.create(
            contract=contract,
            service_obligation=service_obligation,
            payment_obligation=payment_obligation,
            execution_event=execution_event,
            adjustment_type="additional_charge",
            mode="fixed_amount",
            amount=amount,
            currency=currency,
            summary=summary,
        )