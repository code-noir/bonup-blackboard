# backend/engine/contracts/tests/test_full_contract_cycle.py
#
# INERT — 0 TESTS RUN FROM THIS FILE.
#
# test_full_contract_cycle is defined at 4-space indent inside setUp
# (which is at 3-space indent). It is a nested function, not a test
# class method. Django's test runner never discovers it.
#
# ADDITIONAL BREAKAGE (would apply if indentation were fixed):
#   - sign_version() calls version_repo.get(), which does not exist
#     in ContractVersionRepository — AttributeError at runtime.
#   - create_revision() is called with kwarg content_snapshot=,
#     but the parameter name is content=.
#
# This file tests the engine-level ContractVersionService path, which
# is not wired to the live API. See contract_version_service.py for
# the full breakage description.
#
# Do not repair this file without first fixing the engine service and
# wiring it to the API layer.

from django.test import TestCase
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from backend.infrastructure.repositories.contract_repository import ContractRepository
from backend.infrastructure.repositories.contract_version_repository import ContractVersionRepository
from backend.infrastructure.repositories.contract_obligation_repository import ContractObligationRepository

from backend.engine.contracts.services.contract_version_service import ContractVersionService
from backend.engine.contracts.services.activation_service import ContractActivationService
from backend.engine.contracts.services.lifecycle_runner_services import LifecycleRunnerService
from backend.engine.contracts.services.contract_projection_service import ContractProjectionService


class TestFullContractLifecycleIntegration(TestCase):

   def setUp(self):
    self.contract_repo = ContractRepository()
    self.version_repo = ContractVersionRepository()
    self.obligation_repo = ContractObligationRepository()

    # Create activation service FIRST
    self.activation_service = ContractActivationService(
        contract_repo=self.contract_repo,
        version_repo=self.version_repo,
        obligation_repo=self.obligation_repo,
    )

    # Inject activation service into version service
    self.version_service = ContractVersionService(
        contract_repo=self.contract_repo,
        version_repo=self.version_repo,
        activation_service=self.activation_service,
    )

    self.lifecycle_runner = LifecycleRunnerService(
        obligation_repo=self.obligation_repo
    )

    self.projection_service = ContractProjectionService(
        contract_repo=self.contract_repo,
        version_repo=self.version_repo,
        obligation_repo=self.obligation_repo,
    )



    def test_full_contract_cycle(self):

        # 1️⃣ Create base contract
        contract = self.contract_repo.create(name="Integration Test Contract")

        # 2️⃣ Create revision
        revision = self.version_service.create_revision(
            contract_id=contract.id,
            content_snapshot="Initial Draft",
            created_by="system"
        )

        # 3️⃣ Sign revision
        signed_revision = self.version_service.sign_version(
            version_id=revision.id
        )

        self.assertEqual(signed_revision.status, "signed")

        # 4️⃣ Activate contract
        obligations = self.activation_service.activate_contract(
            contract_id=contract.id,
            obligor_id=1,
            obligee_id=2,
            amount=Decimal("1000.00"),
            installments=1,
            interval_days=30,
            start_date=timezone.now() - timedelta(days=10)
        )

        self.assertTrue(len(obligations) > 0)

        # 5️⃣ Run lifecycle automation
        self.lifecycle_runner.run()

        # 6️⃣ Reload obligations
        persisted_obligations = self.obligation_repo.get_by_contract(contract.id)

        self.assertTrue(len(persisted_obligations) > 0)

        # 7️⃣ Projection validation
        projection = self.projection_service.project(contract.id)

        self.assertIn("contract_status", projection)
        self.assertIn("obligations", projection)

        # Ensure contract status matches projection
        refreshed_contract = self.contract_repo.get(contract.id)

        self.assertEqual(
            projection["contract_status"],
            refreshed_contract.state
        )

