

# backend/engine/contracts/services/reconstruction_service.py

from datetime import datetime
from decimal import Decimal


class ContractReconstructionService:
    """
    Reconstructs an already-existing verbal contract
    by generating its obligation schedule and seeding
    factual historical data.

    Lifecycle state is always derived by lifecycle_core.
    Reconstruction never sets state directly.
    """

    def __init__(self, contract_service):
        self.contract_service = contract_service

    def reconstruct(self, payload: dict):
        """
        payload structure example:

        {
            "contract_name": "Lawn Care",
            "start_date": datetime(...),
            "recurrence": "monthly",
            "cycles": 6,
            "payment": {
                "amount_per_cycle": "200.00",
                "grace_days": 3,
                "fulfilled_count": 3,
                "partial_payments": {
                    4: "100.00"  # optional partial example
                }
            },
            "service": {
                "grace_days": 0,
                "fulfilled_count": 3
            },
            "as_of_date": datetime(...)
        }
        """

        # 1️⃣ Create contract normally through engine
        contract = self.contract_service.create_contract(
            name=payload["contract_name"],
            start_date=payload["start_date"],
            recurrence=payload["recurrence"],
            cycles=payload["cycles"],
            payment_amount=payload["payment"]["amount_per_cycle"],
            payment_grace=payload["payment"].get("grace_days", 0),
            service_grace=payload["service"].get("grace_days", 0),
        )

        # 2️⃣ Seed historical factual data (NOT state)
        self._seed_obligation_history(contract, payload)

        # 3️⃣ Derive lifecycle state using controlled time
        as_of = payload.get("as_of_date", datetime.utcnow())
        contract.refresh(now=as_of)

        return contract

    # ------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------

    def _seed_obligation_history(self, contract, payload):

        payment_fulfilled = payload["payment"].get("fulfilled_count", 0)
        partial_payments = payload["payment"].get("partial_payments", {})
        service_fulfilled = payload["service"].get("fulfilled_count", 0)

        # Separate obligations by type
        payment_obligations = [
            o for o in contract.obligations
            if o.__class__.__name__ == "PaymentObligation"
        ]

        service_obligations = [
            o for o in contract.obligations
            if o.__class__.__name__ == "ServiceObligation"
        ]

        # ------------------------------
        # Apply FULL payments
        # ------------------------------
        for obligation in payment_obligations[:payment_fulfilled]:
            obligation.apply_payment(obligation.amount_due)

        # ------------------------------
        # Apply PARTIAL payments (optional)
        # ------------------------------
        for index, amount in partial_payments.items():
            if index - 1 < len(payment_obligations):
                obligation = payment_obligations[index - 1]
                obligation.apply_payment(Decimal(str(amount)))

        # ------------------------------
        # Apply completed services
        # ------------------------------
        for obligation in service_obligations[:service_fulfilled]:
            obligation.mark_completed()
