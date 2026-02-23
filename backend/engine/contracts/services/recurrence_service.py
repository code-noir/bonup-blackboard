# backend/engine/contracts/services/recurrence_service.py

from datetime import timedelta


class RecurrenceService:
    """
    Handles rolling projection of obligations for indefinite contracts.

    This service ensures that:
    - Current obligation exists
    - One buffer obligation exists ahead
    - No over-projection occurs
    """

    def __init__(self, obligation_repo):
        self.obligation_repo = obligation_repo

    def maintain_projection(
        self,
        contract,
        obligations,
        interval_days,
        buffer_cycles=1,
    ):
        """
        Ensures rolling projection of obligations.

        Rules:
        - Maintain latest due_date + buffer_cycles
        - Do NOT generate if contract is closed
        - Do NOT generate if contract is defaulted
        """

        if contract.state in ["closed", "defaulted"]:
            return

        if not obligations:
            return

        # Sort obligations by due_date
        obligations = sorted(obligations, key=lambda o: o.due_date)

        last_due_date = obligations[-1].due_date

        # Determine how many future cycles exist
        # Count obligations that are not resolved
        active_obligations = [
            o for o in obligations
            if o.state in ["active", "overdue"]
        ]

        if len(active_obligations) > buffer_cycles:
            return  # projection already sufficient

        # Create one additional obligation
        next_due_date = last_due_date + timedelta(days=interval_days)

        template = obligations[-1]

        self.obligation_repo.create(
            contract=contract,
            version=None,  # Adjust if version tracking required
            obligor_id=template.obligor_id,
            obligee_id=template.obligee_id,
            installment_number=None,
            amount_due=template.amount_due,
            due_date=next_due_date,
            state="active",
        )

