from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase

from backend.engine.contracts.obligations.primitives import PaymentObligation
from backend.engine.contracts.domain.contract import Contract
from backend.engine.payments.payment_service import PaymentService
from backend.engine.payments.mock_gateway import MockPaymentGateway


def create_obligation(amount="200.00", days_offset=5):
    return PaymentObligation(
        obligor_id=1,
        obligee_id=2,
        amount_due=amount,
        due_date=datetime.utcnow() + timedelta(days=days_offset),
    )


class PaymentServiceTests(TestCase):

    def setUp(self):
        self.gateway = MockPaymentGateway()
        self.service = PaymentService(self.gateway)

    def test_partial_payment(self):
        ob = create_obligation()
        contract = Contract(contract_id=1, obligations=[ob])

        result = self.service.process_payment(contract, ob, 50)

        self.assertTrue(result["success"])
        self.assertEqual(ob.amount_paid, Decimal("50.00"))
        self.assertEqual(ob.remaining_balance(), Decimal("150.00"))

    def test_full_payment_resolves(self):
        ob = create_obligation()
        contract = Contract(contract_id=1, obligations=[ob])

        result = self.service.process_payment(contract, ob, 200)

        self.assertTrue(result["success"])
        self.assertEqual(ob.state, "resolved")

    def test_overpayment_caps(self):
        ob = create_obligation()
        contract = Contract(contract_id=1, obligations=[ob])

        self.service.process_payment(contract, ob, 250)

        self.assertEqual(ob.amount_paid, Decimal("200.00"))
        self.assertEqual(ob.remaining_balance(), Decimal("0.00"))

    def test_negative_payment_fails(self):
        ob = create_obligation()
        contract = Contract(contract_id=1, obligations=[ob])

        result = self.service.process_payment(contract, ob, -10)

        self.assertFalse(result["success"])

    def test_overdue_state_after_payment(self):
        ob = create_obligation(days_offset=-5)
        contract = Contract(contract_id=1, obligations=[ob])

        result = self.service.process_payment(contract, ob, 50)

        self.assertEqual(result["new_state"], "overdue")




