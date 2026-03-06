
# backend/engine/automation/factory.py

from backend.infrastructure.repositories.contract_obligation_repository import (
    ContractObligationRepository,
)

from backend.engine.contracts.services.lifecycle_runner_services import (
    LifecycleRunnerService,
)

from backend.engine.automation.runner import LifecycleAutomationRunner


def build_lifecycle_automation_runner() -> LifecycleAutomationRunner:
    """
    Factory builder for automation runner.

    Keeps wiring outside business logic.
    """

    obligation_repo = ContractObligationRepository()

    lifecycle_runner = LifecycleRunnerService(
        obligation_repo=obligation_repo,
    )

    return LifecycleAutomationRunner(
        lifecycle_runner=lifecycle_runner,
    )
