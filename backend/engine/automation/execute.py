# backend/engine/automation/execute.py

from typing import Optional
from datetime import datetime

from backend.engine.automation.factory import (
    build_lifecycle_automation_runner,
)


def execute_lifecycle_automation(
    contract_id: Optional[int] = None,
    limit: Optional[int] = None,
    current_time: Optional[datetime] = None,
):
    """
    High-level execution entrypoint.

    This function:
    - Builds automation runner
    - Executes lifecycle tick
    - Returns structured result

    This is the safe call boundary for:
    - Celery
    - CLI
    - Cron
    - Admin triggers
    """

    runner = build_lifecycle_automation_runner()

    result = runner.run(
        contract_id=contract_id,
        limit=limit,
        current_time=current_time,
    )

    return result

