#backend/api/contracts/services/approval_service.py

from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)


class ApprovalService:
    """
    Contract-side application service for approval requests.
    """

    def __init__(self):
        self.repo = ContractApprovalRepository()

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
        return self.repo.approve(approval_request)

    def reject(self, *, approval_id):
        approval_request = self.repo.get(approval_id)
        return self.repo.reject(approval_request)

