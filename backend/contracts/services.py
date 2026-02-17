from django.db import transaction
from backend.engine.contracts.lifecycle import prepare_version_creation
from backend.engine.contracts.state_machine import validate_transition
from backend.engine.contracts.exceptions import (
    NegotiationLimitReached,
    ImmutableVersionError,
    InvalidStateTransition,
)
from .models import ContractVersion


@transaction.atomic
def create_new_version(contract, content, user=None):
    """
    Orchestrates creation of a new contract version.
    Enforces negotiation limits and immutability.
    """

    existing_versions = contract.versions.count()

    next_version_number = prepare_version_creation(
        max_versions=contract.max_versions,
        existing_versions=existing_versions,
    )

    previous_version = (
        contract.versions.order_by("-version_number").first()
    )

    if previous_version:
        previous_version.status = "superseded"
        previous_version.superseded = True
        previous_version.save(update_fields=["status", "superseded"])

    version = ContractVersion.objects.create(
        contract=contract,
        version_number=next_version_number,
        previous_version=previous_version,
        created_by=user,
        content_snapshot=content,
        status="draft",
    )

    return version


@transaction.atomic
def transition_version(version, new_status):
    """
    Handles state transitions via engine validation.
    """

    validate_transition(version.status, new_status)

    version.status = new_status
    version.save(update_fields=["status"])

    return version





