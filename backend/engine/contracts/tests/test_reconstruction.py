# backend/engine/contracts/tests/test_reconstruction.py

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from backend.engine.contracts.services.reconstruction_service import (
    ContractReconstructionService,
)

from backend.engine.contracts.services.contract_service import (
    ContractService,
)


class ReconstructionTests(TestCase):

    def setUp(self):
        # Your engine does not use repositories.
        # ContractService is self-contained.
        self.contract_service = ContractService()

        self.reconstruction_service = ContractReconstructionService(
            contract_service=self.contract_service
        )

    # ------------------------------------------------------------
    # VALID RECONSTRUCTION
    # ------------------------------------------------------------

    def test_valid_reconstruction(self):

        now = timezone.now()

        payload = {
            "contract_name": "Lawn Care",
            "start_date": now - timedelta(days=60),
            "recurrence": "monthly",
            "cycles": 6,
            "payment": {
                "amount_per_cycle": "200.00",
                "grace_days": 3,
                "fulfilled_count": 3,
                "partial_payments": {
                    4: "100.00",
                },
            },
            "service": {
                "grace_days": 0,
                "fulfilled_count": 3,
            },
            "as_of_date": now,
        }

        contract = self.reconstruction_service.reconstruct(payload)

        # Contract should exist
        self.assertIsNotNone(contract)

        # Obligations should be generated
        self.assertTrue(len(contract.obligations) > 0)

        # State should be derived via refresh()
        self.assertIn(contract.state, ["active", "fulfilled", "breached"])

    # ------------------------------------------------------------
    # OVER-SEED SHOULD FAIL
    # ------------------------------------------------------------

    def test_over_seed_payment_fails(self):

        now = timezone.now()

        payload = {
            "contract_name": "Invalid Contract",
            "start_date": now,
            "recurrence": "monthly",
            "cycles": 2,
            "payment": {
                "amount_per_cycle": "100.00",
                "fulfilled_count": 10,  # Invalid (too many)
            },
            "service": {
                "fulfilled_count": 0,
            },
            "as_of_date": now,
        }

        with self.assertRaises(ValueError):
            self.reconstruction_service.reconstruct(payload)

    # ------------------------------------------------------------
    # BREACHED CONTRACT SHOULD NOT IMPORT
    # ------------------------------------------------------------

    def test_breached_contract_rejected(self):

        now = timezone.now()

        payload = {
            "contract_name": "Breached Case",
            "start_date": now - timedelta(days=365),
            "recurrence": "monthly",
            "cycles": 1,
            "payment": {
                "amount_per_cycle": "200.00",
                "fulfilled_count": 0,
            },
            "service": {
                "fulfilled_count": 0,
            },
            "as_of_date": now,
        }

        with self.assertRaises(ValueError):
            self.reconstruction_service.reconstruct(payload)



