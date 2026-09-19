"""Django-to-trusted-runtime projection for Product Direction M2."""
from tools.agent_control.prod_runtime import (
    ProductDirectionRuntimeRequest,
    ProductRuntimeFailure,
    ProductRuntimeUnavailable,
    agent_control_task_id_for,
    submit_product_direction_task as _submit_product_direction_task,
)


def runtime_request_for(task):
    return ProductDirectionRuntimeRequest(
        application_task_id=str(task.id),
        agent_control_task_id=task.agent_control_task_id,
        agent_id=task.agent_id,
        objective=task.objective,
    )


def submit_product_direction_task(request):
    """Send only the bounded projection to the trusted runtime composition."""
    return _submit_product_direction_task(request)


__all__ = [
    "ProductRuntimeFailure",
    "ProductRuntimeUnavailable",
    "agent_control_task_id_for",
    "runtime_request_for",
    "submit_product_direction_task",
]
