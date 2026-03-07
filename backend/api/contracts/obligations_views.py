from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from backend.contracts.models import Contract
from backend.engine.lifecycle_core.obligations.primitives import PaymentObligation
from django.utils import timezone
from backend.infrastructure.repositories.contract_obligation_repository import ContractObligationRepository


class CreateObligationAPIView(APIView):
    """
    POST /contracts/{id}/obligations
    """

    def post(self, request, contract_id):

        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return Response(
                {"error": "Contract not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        obligor_id = request.data.get("obligor_id")
        obligee_id = request.data.get("obligee_id")
        amount_due = request.data.get("amount_due")
        due_date = request.data.get("due_date")

        if not all([obligor_id, obligee_id, amount_due, due_date]):
            return Response(
                {"error": "Missing required fields"},
                status=status.HTTP_400_BAD_REQUEST
            )

        obligation = PaymentObligation(
            obligor_id=obligor_id,
            obligee_id=obligee_id,
            amount_due=amount_due,
            due_date=due_date
        )

        # attach obligation to contract engine
        contract.engine_contract.add_obligation(obligation)

        return Response(
            {"message": "Obligation created"},
            status=status.HTTP_201_CREATED
        )

class ContractObligationsListAPIView(APIView):
    """
    GET /api/contracts/{contract_id}/obligations/

    Returns all obligations for a contract.
    """

    def get(self, request, contract_id):

        obligation_repo = ContractObligationRepository()

        obligations = obligation_repo.filter_by_contract(contract_id)

        data = [
            {
                "id": o.id,
                "obligor_id": o.obligor_id,
                "obligee_id": o.obligee_id,
                "amount_due": o.amount_due,
                "paid_amount": o.paid_amount,
                "due_date": o.due_date,
                "state": o.state
            }
            for o in obligations
        ]

        return Response(data, status=status.HTTP_200_OK)

