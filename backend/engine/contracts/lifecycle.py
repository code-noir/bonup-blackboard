## backend/engine/contracts/lifecycle.py
from .versioning import calculate_next_version
from .exceptions import (
    NegotiationLimitReached,
    ImmutableVersionError,
)

from .state_machine import validate_transition
from .exceptions import InvalidStateTransition


def perform_transition(current_status, new_status):
    validate_transition(current_status, new_status)
    return new_status



def prepare_version_creation(contract, existing_versions):
    """
    Pure engine logic.
    No Django imports.
    """

    current_count = len(existing_versions)

    # Calculate next version number (enforces negotiation limit)
    next_version_number = calculate_next_version(
        current_count=current_count,
        max_versions=contract.max_versions,
    )

    previous_version = None

    if existing_versions:
        # versions are expected ordered descending
        previous_version = existing_versions[0]

    return next_version_number, previous_version

