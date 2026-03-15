# test_contract_lifecycle.py

from datetime import datetime, timedelta
from django.test import TestCase
from backend.engine.contracts.services.contract_coordinator import ContractCoordinator

from backend.engine.lifecycle_core.obligations.primitives import PaymentObligation


# ------------------------------------------------------------
# 1️⃣ Fake Obligation Repo
# ------------------------------------------------------------

class FakeObligationRepo:

    def __init__(self, obligations):
        self._obligations = obligations

    def get_by_contract(self, contract_id):
        return self._obligations

    def save(self, obligation):
        pass


# ------------------------------------------------------------
# 2️⃣ Fake Contract
# ------------------------------------------------------------

class FakeContract:

    def __init__(self, contract_id=None):
        self.contract_id = contract_id
        self.obligations = []
        self.state = "active"

    def refresh(self, now=None):
        if all(o.state == "resolved" for o in self.obligations):
            self.state = "fulfilled"
        else:
            self.state = "active"


# ------------------------------------------------------------
# 3️⃣ Fake Contract Repo
# ------------------------------------------------------------

class FakeContractRepo:

    def __init__(self, contract):
        self._contract = contract

    def get(self, contract_id):
        return self._contract

    def save(self, contract):
        self._contract = contract


# ------------------------------------------------------------
# 4️⃣ Coordinator Wiring Test
# ------------------------------------------------------------

class ContractLifecycleTest(TestCase):

    def test_contract_becomes_fulfilled_when_all_obligations_resolved(self):

        due = datetime.utcnow() - timedelta(days=1)

        o1 = PaymentObligation(
            obligor_id=1,
            obligee_id=2,
            amount_due=100,
            due_date=due
        )
        o1.state = "resolved"

        o2 = PaymentObligation(
            obligor_id=1,
            obligee_id=2,
            amount_due=200,
            due_date=due
        )
        o2.state = "resolved"

        obligations = [o1, o2]

        fake_contract = FakeContract(contract_id=1)

        obligation_repo = FakeObligationRepo(obligations)
        contract_repo = FakeContractRepo(fake_contract)

        coordinator = ContractCoordinator(
            obligation_repo=obligation_repo,
            contract_repo=contract_repo
        )

        coordinator.refresh_contract_obligations(contract_id=1)

        self.assertEqual(fake_contract.state, "fulfilled")




