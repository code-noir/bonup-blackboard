#backend/api/contracts/services/contract_management_service.py



from backend.contracts.models import (
    Contract,
    ContractObligation,
    ContractServiceObligation,
)
from backend.api.contracts.services.contract_mode_service import ContractModeService
from backend.infrastructure.repositories.contract_value_adjustment_repository import (
    ContractValueAdjustmentRepository,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)
from backend.infrastructure.repositories.contract_obligation_promotion_repository import (
    ContractObligationPromotionRepository,
)


class ContractManagementService:
    """
    Builds a contract-level management summary payload.
    """

    def __init__(self):
        self.contract_mode_service = ContractModeService()
        self.adjustment_repo = ContractValueAdjustmentRepository()
        self.approval_repo = ContractApprovalRepository()
        self.promotion_repo = ContractObligationPromotionRepository()

    def build_summary(self, *, contract_id):
        contract = Contract.objects.get(id=contract_id)

        payment_obligations = ContractObligation.objects.filter(
            contract_id=contract_id
        ).order_by("due_date")

        service_obligations = ContractServiceObligation.objects.filter(
            contract_id=contract_id
        ).order_by("due_date")

        adjustments = self.adjustment_repo.list_for_contract(contract_id)
        approvals = self.approval_repo.list_for_contract(contract_id)
        promotions = self.promotion_repo.list_for_contract(contract_id)

        return {
            "contract": {
                "id": str(contract.id),
                "initiator_id": contract.initiator_id,
                "counterparty_email": contract.counterparty_email,
                "structure_type": contract.structure_type,
                "state": contract.state,
                "is_active": contract.is_active,
                "created_at": contract.created_at,
            },
            "contract_mode": self.contract_mode_service.derive_mode(contract_id=contract_id),
            "counts": {
                "payment_obligation_count": payment_obligations.count(),
                "service_obligation_count": service_obligations.count(),
                "approval_count": approvals.count(),
                "adjustment_count": adjustments.count(),
                "promotion_count": promotions.count(),
            },
            "payment_obligations": [
                {
                    "id": str(ob.id),
                    "installment_number": ob.installment_number,
                    "obligor_id": ob.obligor_id,
                    "obligee_id": ob.obligee_id,
                    "amount_due": str(ob.amount_due),
                    "amount_paid": str(ob.amount_paid),
                    "due_date": ob.due_date,
                    "state": ob.state,
                    "is_defaulted": ob.is_defaulted,
                }
                for ob in payment_obligations
            ],
            "service_obligations": [
                {
                    "id": str(ob.id),
                    "obligor_id": ob.obligor_id,
                    "obligee_id": ob.obligee_id,
                    "description": ob.description,
                    "due_date": ob.due_date,
                    "state": ob.state,
                    "completed_at": ob.completed_at,
                }
                for ob in service_obligations
            ],
            "approval_requests": [
                {
                    "id": str(a.id),
                    "approval_type": a.approval_type,
                    "status": a.status,
                    "summary": a.summary,
                    "execution_event_id": str(a.execution_event_id) if a.execution_event_id else None,
                    "payment_obligation_id": str(a.payment_obligation_id) if a.payment_obligation_id else None,
                    "service_obligation_id": str(a.service_obligation_id) if a.service_obligation_id else None,
                    "requested_at": a.requested_at,
                    "decided_at": a.decided_at,
                }
                for a in approvals
            ],
            "value_adjustments": [
                {
                    "id": str(adj.id),
                    "adjustment_type": adj.adjustment_type,
                    "mode": adj.mode,
                    "amount": str(adj.amount),
                    "currency": adj.currency,
                    "summary": adj.summary,
                    "execution_event_id": str(adj.execution_event_id) if adj.execution_event_id else None,
                    "payment_obligation_id": str(adj.payment_obligation_id) if adj.payment_obligation_id else None,
                    "service_obligation_id": str(adj.service_obligation_id) if adj.service_obligation_id else None,
                    "created_at": adj.created_at,
                }
                for adj in adjustments
            ],
            "promotions": [
                {
                    "id": str(p.id),
                    "promotion_type": p.promotion_type,
                    "summary": p.summary,
                    "source_execution_event_id": str(p.source_execution_event_id),
                    "parent_service_obligation_id": (
                        str(p.parent_service_obligation_id)
                        if p.parent_service_obligation_id else None
                    ),
                    "promoted_service_obligation_id": (
                        str(p.promoted_service_obligation_id)
                        if p.promoted_service_obligation_id else None
                    ),
                    "created_at": p.created_at,
                }
                for p in promotions
            ],
        }
