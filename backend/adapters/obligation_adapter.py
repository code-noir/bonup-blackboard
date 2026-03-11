# backend/adapters/obligation_adapter.py

from backend.contracts.models import ContractObligation
from backend.engine.lifecycle_core.obligations.primitives import PaymentObligation


class ObligationAdapter:
    """
    Adapter that converts engine obligations
    into Django database objects.
    """

    @staticmethod
    def payment_to_model(payment_obligation, contract, version, installment_number):
        """
        Convert engine PaymentObligation → ContractObligation model
        """

        return ContractObligation.objects.create(
            contract=contract,
            version=version,
            obligor_id=payment_obligation.obligor_id,
            obligee_id=payment_obligation.obligee_id,
            installment_number=installment_number,
            amount_due=payment_obligation.amount_due,
            amount_paid=payment_obligation.amount_paid,
            due_date=payment_obligation.due_date,
            state=payment_obligation.state,
        )

    @staticmethod
    def model_to_payment(contract_obligation):
        """
        Convert ContractObligation model → PaymentObligation
        """

        return PaymentObligation(
            obligor_id=contract_obligation.obligor_id,
            obligee_id=contract_obligation.obligee_id,
            amount_due=contract_obligation.amount_due,
            amount_paid=contract_obligation.amount_paid,
            due_date=contract_obligation.due_date,
            state=contract_obligation.state,
        )