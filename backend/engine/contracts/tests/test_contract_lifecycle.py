# backend/engine/contracts/tests/test_contract_lifecycle.py
from django.test import TestCase
from datetime import timedelta
from django.utils import timezone

from backend.engine.contracts.services.contract_coordinator import ContractCoordinator
from backend.engine.contracts.services.lifecycle_runner_services import LifecycleRunnerService
from backend.engine.lifecycle_core.obligations.primitives import PaymentObligation


class FakeObligationRepo:
    def __init__(self, obligations):
        self._obligations = obligations

    def get_by_contract(self, contract_id):
        return self._obligations

    def save(self, obligation):
        pass

class FakeContract:
    def __init__(self, contract_id=None):
        self.contract_id = contract_id
        self.obligations = []
        self.state = "active"

    def refresh(self, now=None):
        if all(o.state == "resolved" for o in self.obligations):
            self.state = "fulfilled"



class FakeContractRepo:
    def __init__(self, contract):
        self.contract = contract

    def get(self, contract_id):
        return self.contract

    def save(self, contract):
        pass


class ContractLifecycleTest(TestCase):

    def test_contract_becomes_fulfilled_when_all_obligations_resolved(self):

        due = timezone.now() - timedelta(days=1)

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

        fake_contract = FakeContract()

        coordinator = ContractCoordinator(
            obligation_repo=FakeObligationRepo(obligations),
            contract_repo=FakeContractRepo(fake_contract)
        )

        coordinator.refresh_contract_obligations(contract_id=1)

        self.assertEqual(fake_contract.state, "fulfilled")


class FakeTickObligationRepo:
    """Minimal fake satisfying the LifecycleRunnerService.tick() interface."""

    def __init__(self, obligations):
        self._obligations = obligations
        self.update_state_calls = []

    def list_candidates(self, contract_id=None, limit=None):
        return list(self._obligations)

    def update_state(self, obligation, new_state, current_time):
        obligation.state = new_state
        self.update_state_calls.append((obligation, new_state))


class LifecycleRunnerServiceTickTest(TestCase):

    def test_tick_detects_state_change_and_calls_update_state(self):
        now = timezone.now()

        # Obligation 1: past due by 1 day, unpaid → should transition to "overdue"
        overdue_ob = PaymentObligation(
            obligor_id=1,
            obligee_id=2,
            amount_due=100,
            due_date=now - timedelta(days=1),
            state="active",
        )

        # Obligation 2: due in future, unpaid → state stays "active"
        active_ob = PaymentObligation(
            obligor_id=1,
            obligee_id=2,
            amount_due=50,
            due_date=now + timedelta(days=10),
            state="active",
        )

        fake_repo = FakeTickObligationRepo([overdue_ob, active_ob])
        service = LifecycleRunnerService(obligation_repo=fake_repo)

        result = service.tick(current_time=now)

        self.assertEqual(result.scanned, 2)
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.unchanged, 1)
        # update_state was called exactly once — for the overdue obligation
        self.assertEqual(len(fake_repo.update_state_calls), 1)
        changed_ob, new_state = fake_repo.update_state_calls[0]
        self.assertIs(changed_ob, overdue_ob)
        self.assertEqual(new_state, "overdue")

    def test_tick_returns_zero_updated_when_no_state_changes(self):
        now = timezone.now()

        # Obligation due in the future → stays "active"
        ob = PaymentObligation(
            obligor_id=1,
            obligee_id=2,
            amount_due=100,
            due_date=now + timedelta(days=5),
            state="active",
        )

        fake_repo = FakeTickObligationRepo([ob])
        service = LifecycleRunnerService(obligation_repo=fake_repo)

        result = service.tick(current_time=now)

        self.assertEqual(result.scanned, 1)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.unchanged, 1)
        self.assertEqual(fake_repo.update_state_calls, [])
