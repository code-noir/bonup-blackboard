# backend/engine/automation/tasks.py

from celery import shared_task

from backend.engine.automation.execute import (
    execute_lifecycle_automation,
)


@shared_task
def run_lifecycle_automation_task(
    contract_id=None,
    limit=None,
):
    """
    Celery task wrapper for lifecycle automation.

    This task:
    - Delegates to engine automation
    - Contains no business logic
    - Is safe for scheduled execution
    """

    result = execute_lifecycle_automation(
        contract_id=contract_id,
        limit=limit,
    )

    return {
        "scanned": result.scanned,
        "updated": result.updated,
        "unchanged": result.unchanged,
        "timestamp": result.timestamp.isoformat(),
    }

