"""Django-to-trusted-runtime projection for Product Direction M2."""
from tools.agent_control.founder_review_runtime import TrustedFounderReviewRuntime
from tools.agent_control.prod_application import ProductDirectionApplicationClient
from tools.agent_control.prod_runtime import (
    ProductDirectionRuntimeRequest,
    ProductRuntimeFailure,
    ProductRuntimeUnavailable,
    agent_control_task_id_for,
    submit_product_direction_task as _submit_product_direction_task,
)


_configured_application_runtime = None


def runtime_request_for(task):
    return ProductDirectionRuntimeRequest(
        application_task_id=str(task.id),
        agent_control_task_id=task.agent_control_task_id,
        agent_id=task.agent_id,
        objective=task.objective,
    )


def submit_product_direction_task(request):
    """Send only the bounded projection to the trusted runtime composition."""
    if _configured_application_runtime is None:
        return _submit_product_direction_task(request)
    return _configured_application_runtime.submit(request)


def configure_product_direction_runtime(client):
    """Compose the Django hooks from one trusted Agent Control client."""
    if type(client) is not ProductDirectionApplicationClient:
        raise ValueError("Trusted Product Direction application client required.")
    from . import proposal as proposal_module
    from . import review as review_module
    proposal_module.configure_proposal_reader(client)
    review_module.configure_founder_review_runtime(
        TrustedFounderReviewRuntime(client.founder_boundary())
    )
    global _configured_application_runtime
    _configured_application_runtime = client


def get_configured_product_direction_runtime():
    return _configured_application_runtime


__all__ = [
    "ProductRuntimeFailure",
    "ProductRuntimeUnavailable",
    "agent_control_task_id_for",
    "runtime_request_for",
    "submit_product_direction_task",
    "configure_product_direction_runtime",
    "get_configured_product_direction_runtime",
]
