
from datetime import datetime
from django.test import TestCase

from backend.engine.contracts.services.reconstruction_service import (
    ContractReconstructionService,
)
from backend.engine.contracts.services.contract_service import (
    ContractService,
)


class ReconstructionTests(TestCase):

    def setUp(self):
        self.contract_service = ContractService()
        self.reconstruction_service = ContractReconstructionService(
            self.contract_service
        )

    # ------------------------------------------------------------
    # TEST 1 — Fully Completed Contract
    # ------------------------------------------------------------
    def test_reconstruction_fully_completed(self):

        payload = {
            "contract_name": "Test Contract",
            "start_date": datetime(2023, 1, 1),
            "recurrence": "monthly",
            "cycles": 6,
            "payment": {
                "amount_per_cycle": 200,
                "fulfilled_count": 6,
            },
            "service": {
                "fulfilled_count": 6,
            },
            "as_of_date": datetime(2024, 1, 1),
        }

        contract = self.reconstruction_service.reconstruct(payload)

        self.assertTrue(all(o.state == "resolved" for o in contract.obligations))
        self.assertEqual(contract.state, "resolved")

    # ------------------------------------------------------------
    # TEST 2 — Partial + Overdue
    # ------------------------------------------------------------
    def test_reconstruction_partial_and_overdue(self):

        payload = {
            "contract_name": "Test Contract",
            "start_date": datetime(2023, 1, 1),
            "recurrence": "monthly",
            "cycles": 6,
            "payment": {
                "amount_per_cycle": 200,
                "fulfilled_count": 2,
                "partial_payments": {
                    3: 100
                },
            },
            "service": {
                "fulfilled_count": 2,
            },
            "as_of_date": datetime(2024, 1, 1),
        }

        contract = self.reconstruction_service.reconstruct(payload)

        resolved = [o for o in contract.obligations if o.state == "resolved"]
        overdue = [o for o in contract.obligations if o.state == "overdue"]

        self.assertTrue(len(resolved) >= 4)  # 2 payment + 2 service
        self.assertTrue(len(overdue) > 0)
        self.assertIn(contract.state, ["active", "overdue", "defaulted"])

    # ------------------------------------------------------------
    # TEST 3 — Future Active Contract
    # ------------------------------------------------------------
    def test_reconstruction_future_active(self):

        now = datetime.utcnow()

        payload = {
            "contract_name": "Future Contract",
            "start_date": now,
            "recurrence": "monthly",
            "cycles": 6,
            "payment": {
                "amount_per_cycle": 200,
            },
            "service": {},
            "as_of_date": now,
        }

        contract = self.reconstruction_service.reconstruct(payload)

        self.assertTrue(all(o.state == "active" for o in contract.obligations))
        self.assertEqual(contract.state, "active")



