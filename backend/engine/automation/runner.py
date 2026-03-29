# backend/engine/automation/runner.py

from datetime import datetime
from dataclasses import dataclass
from django.utils import timezone
from typing import Optional

from backend.engine.contracts.services.lifecycle_runner_services import (
    LifecycleRunnerService,
)


@dataclass
class AutomationRunResult:
    scanned: int
    updated: int
    unchanged: int
    timestamp: datetime


class LifecycleAutomationRunner:
    """
    Engine-level automation runner.

    Responsible for:
    - Triggering lifecycle scan
    - Delegating mutation logic to LifecycleRunnerService
    - Returning structured result

    Contains NO lifecycle logic.
    """

    def __init__(self, lifecycle_runner: LifecycleRunnerService):
        self.lifecycle_runner = lifecycle_runner

    def run(
        self,
        contract_id: Optional[int] = None,
        limit: Optional[int] = None,
        current_time: Optional[datetime] = None,
    ) -> AutomationRunResult:
        """
        Execute lifecycle tick.
        """

        if current_time is None:
            current_time = timezone.now()

        result = self.lifecycle_runner.run(
            contract_id=contract_id,
            limit=limit,
            current_time=current_time,
        )

        return AutomationRunResult(
            scanned=result.scanned,
            updated=result.updated,
            unchanged=result.unchanged,
            timestamp=current_time,
        )


