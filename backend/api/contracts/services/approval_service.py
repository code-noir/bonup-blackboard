# backend/api/contracts/services/approval_service.py

from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)
from backend.infrastructure.repositories.contract_value_adjustment_repository import (
    ContractValueAdjustmentRepository,
)
from backend.api.contracts.services.value_adjustment_service import (
    ValueAdjustmentService,
)
from backend.api.contracts.services.obligation_promotion_service import (
    ObligationPromotionService,
)


class ApprovalService:
    """
    Contract-side application service for approval requests.
    """

    def __init__(self):
        self.repo = ContractApprovalRepository()
        self.adjustment_repo = ContractValueAdjustmentRepository()
        self.value_adjustment_service = ValueAdjustmentService()
        self.promotion_service = ObligationPromotionService()

    def request_execution_item_approval(
        self,
        *,
        obligation_type,
        obligation_id,
        execution_event,
        requested_by=None,
        requested_from=None,
        summary,
        metadata=None,
    ):
        if obligation_type == "payment":
            payment_obligation = ContractObligation.objects.get(id=obligation_id)
            return self.repo.create(
                contract=payment_obligation.contract,
                payment_obligation=payment_obligation,
                execution_event=execution_event,
                requested_by=requested_by,
                requested_from=requested_from,
                approval_type="execution_item",
                summary=summary,
                metadata=metadata or {},
            )

        if obligation_type == "service":
            service_obligation = ContractServiceObligation.objects.get(id=obligation_id)
            return self.repo.create(
                contract=service_obligation.contract,
                service_obligation=service_obligation,
                execution_event=execution_event,
                requested_by=requested_by,
                requested_from=requested_from,
                approval_type="execution_item",
                summary=summary,
                metadata=metadata or {},
            )

        raise Exception("Invalid obligation type")

    def approve(self, *, approval_id):
        approval_request = self.repo.get(approval_id)
        approval_request = self.repo.approve(approval_request)

        self._create_adjustment_if_needed(approval_request)
        self._promote_if_needed(approval_request)

        return approval_request

    def reject(self, *, approval_id):
        approval_request = self.repo.get(approval_id)
        return self.repo.reject(approval_request)

    def _create_adjustment_if_needed(self, approval_request):
        execution_event = approval_request.execution_event
        if execution_event is None:
            return None

        metadata = approval_request.metadata or {}
        billing_mode = metadata.get("billing_mode")

        if billing_mode != "separate_charge":
            return None

        if execution_event.estimated_cost_amount is None:
            return None

        existing = self.adjustment_repo.find_additional_charge_for_execution_event(
            execution_event.id
        )
        if existing is not None:
            return existing

        if approval_request.service_obligation_id:
            return self.value_adjustment_service.store_additional_charge(
                contract=approval_request.contract,
                service_obligation=approval_request.service_obligation,
                execution_event=execution_event,
                amount=execution_event.estimated_cost_amount,
                currency=execution_event.estimated_cost_currency or "USD",
                summary=execution_event.summary,
            )

        if approval_request.payment_obligation_id:
            return self.value_adjustment_service.store_additional_charge(
                contract=approval_request.contract,
                payment_obligation=approval_request.payment_obligation,
                execution_event=execution_event,
                amount=execution_event.estimated_cost_amount,
                currency=execution_event.estimated_cost_currency or "USD",
                summary=execution_event.summary,
            )

        return None

    def _promote_if_needed(self, approval_request):
        execution_event = approval_request.execution_event
        if execution_event is None:
            return None

        metadata = approval_request.metadata or {}
        promotion_suggestion = metadata.get("promotion_suggestion")

        if promotion_suggestion != "suggest_side_obligation":
            return None

        return self.promotion_service.promote_execution_event_to_service_obligation(
            execution_event_id=execution_event.id
        )




















