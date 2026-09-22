"""Django startup composition for the bounded PROD-01 application boundary."""

from tools.agent_control.prod_application import ProductDirectionApplicationClient
from tools.agent_control.types import AuthorityError, ValidationError

from .runtime import configure_product_direction_runtime


def configure_from_installed_agent_control():
    """Select the trusted local client only from valid root-controlled config.

    Missing or invalid installed state deliberately leaves both runtime hooks
    unavailable.  Django never constructs a model transport or reads a secret.
    """
    try:
        client = ProductDirectionApplicationClient.from_installed_config()
        configure_product_direction_runtime(client)
    except (AuthorityError, OSError, ValidationError, KeyError):
        return False
    return True


__all__ = ["configure_from_installed_agent_control"]
