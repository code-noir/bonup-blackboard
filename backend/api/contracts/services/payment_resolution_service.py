#backend/api/contracts/services/payment_resolution_service.py

from django.utils import timezone
from backend.contracts.models import ContractObligation


class PaymentResolutionService:
    def resolve(self, obligation_id):
        obligation = ContractObligation.objects.get(id=obligation_id)

        # Basic guard
        if obligation.amount_paid < obligation.amount_due:
            raise Exception("Cannot resolve: payment not complete.")

        obligation.state = "resolved"

        # Optional: set resolved timestamp if you have field
        if hasattr(obligation, "resolved_at"):
            obligation.resolved_at = timezone.now()

        obligation.save(update_fields=["state"])

        return obligation

