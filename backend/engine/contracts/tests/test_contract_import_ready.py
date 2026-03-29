# backend/engine/contracts/tests/test_contract_import_ready.py
from django.test import TestCase
from datetime import timedelta
from django.utils import timezone

from backend.engine.contracts.domain.contract import Contract
from backend.engine.lifecycle_core.obligations.primitives import PaymentObligation


class ContractImportReadyTest(TestCase):

    def test_import_mixed_state_contract(self):

        past_due = timezone.now() - timedelta(days=10)
        future_due = timezone.now() + timedelta(days=10)

        # Resolved obligation
        o1 = PaymentObligation(1, 2, 100, past_due)
        o1.amount_paid = 100
        o1.state = "resolved"

        # Overdue obligation
        o2 = PaymentObligation(1, 2, 200, past_due)

        # Active obligation
        o3 = PaymentObligation(1, 2, 300, future_due)

        contract = Contract(
            contract_id=1,
            obligations=[o1, o2, o3]
        )

        contract.refresh()

        self.assertEqual(contract.state, "active")

