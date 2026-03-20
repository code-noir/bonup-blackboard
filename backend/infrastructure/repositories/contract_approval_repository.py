#backend/infrastructure/repositories/contract_approval_repository.py

from django.utils import timezone

from backend.contracts.models import ContractApprovalRequest


class ContractApprovalRepository:
    """
    Persistence layer for contract approval requests.
    """

    def create(self, **kwargs):
        return ContractApprovalRequest.objects.create(**kwargs)

    def get(self, approval_id):
        return ContractApprovalRequest.objects.get(id=approval_id)

    def list_for_contract(self, contract_id):
        return ContractApprovalRequest.objects.filter(contract_id=contract_id)

    def list_for_service_obligation(self, service_obligation_id):
        return ContractApprovalRequest.objects.filter(
            service_obligation_id=service_obligation_id
        )

    def list_for_payment_obligation(self, payment_obligation_id):
        return ContractApprovalRequest.objects.filter(
            payment_obligation_id=payment_obligation_id
        )

    def list_for_execution_event(self, execution_event_id):
        return ContractApprovalRequest.objects.filter(
            execution_event_id=execution_event_id
        )

    def approve(self, approval_request):
        approval_request.status = "approved"
        approval_request.decided_at = timezone.now()
        approval_request.save(update_fields=["status", "decided_at"])
        return approval_request

    def reject(self, approval_request):
        approval_request.status = "rejected"
        approval_request.decided_at = timezone.now()
        approval_request.save(update_fields=["status", "decided_at"])
        return approval_request


