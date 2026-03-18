#backend/contracts/mappers/obligation_response_mapper.py

from backend.contracts.models import ContractObligation, ContractServiceObligation


class ObligationResponseMapper:
    @staticmethod
    def to_dict(obligation):
        if isinstance(obligation, ContractObligation):
            return {
                "id": str(obligation.id),
                "obligation_type": "payment",
                "obligor_id": obligation.obligor_id,
                "obligee_id": obligation.obligee_id,
                "amount_due": str(obligation.amount_due),
                "amount_paid": str(obligation.amount_paid),
                "description": None,
                "due_date": obligation.due_date,
                "state": obligation.state,
            }

        if isinstance(obligation, ContractServiceObligation):
            return {
                "id": str(obligation.id),
                "obligation_type": "service",
                "obligor_id": obligation.obligor_id,
                "obligee_id": obligation.obligee_id,
                "amount_due": None,
                "amount_paid": None,
                "description": obligation.description,
                "due_date": obligation.due_date,
                "state": obligation.state,
            }

        raise Exception(f"Unsupported obligation type: {type(obligation)}")

