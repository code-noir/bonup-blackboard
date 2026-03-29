# backend/engine/contracts/services/reconstruction_service.py

from decimal import Decimal
from django.utils import timezone


class ContractReconstructionService:
    """
    Reconstructs an already-existing verbal contract
    by generating its obligation schedule and seeding
    factual historical data.

    Reconstruction NEVER sets lifecycle state directly.
    Lifecycle state is always derived from lifecycle engine.
    """

    def __init__(self, contract_service):
        self.contract_service = contract_service

    # ------------------------------------------------------------
    # PUBLIC ENTRY
    # ------------------------------------------------------------

    def reconstruct(self, payload: dict):

        self._validate_payload(payload)

        contract = self.contract_service.create_contract(
            name=payload["contract_name"],
            start_date=payload["start_date"],
            recurrence=payload["recurrence"],
            cycles=payload["cycles"],
            payment_amount=payload["payment"]["amount_per_cycle"],
            payment_grace=payload["payment"].get("grace_days", 0),
            service_grace=payload["service"].get("grace_days", 0),
        )

        self._seed_obligation_history(contract, payload)

        as_of = payload.get("as_of_date", timezone.now())
        contract.refresh(now=as_of)

        # Prevent importing already-breached contract
        if contract.state == "breached":
            raise ValueError(
                "Cannot reconstruct contract that results in breached state."
            )

        return contract

    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------

    def _validate_payload(self, payload):

        required_fields = [
            "contract_name",
            "start_date",
            "recurrence",
            "cycles",
            "payment",
            "service",
        ]

        for field in required_fields:
            if field not in payload:
                raise ValueError(f"Missing required field: {field}")

        if payload["cycles"] <= 0:
            raise ValueError("Contract must have at least one cycle.")

        payment_data = payload["payment"]

        if Decimal(str(payment_data["amount_per_cycle"])) <= 0:
            raise ValueError("Payment amount must be greater than zero.")

    # ------------------------------------------------------------
    # SEED HISTORY
    # ------------------------------------------------------------

    def _seed_obligation_history(self, contract, payload):

        payment_fulfilled = payload["payment"].get("fulfilled_count", 0)
        partial_payments = payload["payment"].get("partial_payments", {})
        service_fulfilled = payload["service"].get("fulfilled_count", 0)

        payment_obligations = [
            o for o in contract.obligations
            if o.__class__.__name__ == "PaymentObligation"
        ]

        service_obligations = [
            o for o in contract.obligations
            if o.__class__.__name__ == "ServiceObligation"
        ]

        # Guard against overflow seeding
        if payment_fulfilled > len(payment_obligations):
            raise ValueError("Fulfilled payment count exceeds obligation count.")

        if service_fulfilled > len(service_obligations):
            raise ValueError("Fulfilled service count exceeds obligation count.")

        # FULL payments
        for obligation in payment_obligations[:payment_fulfilled]:
            obligation.apply_payment(obligation.amount_due)

        # PARTIAL payments
        for index, amount in partial_payments.items():

            if index <= 0:
                raise ValueError("Installment index must start at 1.")

            if index > len(payment_obligations):
                raise ValueError("Partial payment index out of range.")

            obligation = payment_obligations[index - 1]

            obligation.apply_payment(Decimal(str(amount)))

        # COMPLETED services
        for obligation in service_obligations[:service_fulfilled]:
            obligation.mark_completed()



