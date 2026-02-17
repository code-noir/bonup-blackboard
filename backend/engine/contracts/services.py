from backend.contracts.models import ContractVersion
from backend.engine.contracts.lifecycle import prepare_version_creation
from backend.engine.contracts.state_machine import validate_transition
from backend.engine.contracts.exceptions import (
    NegotiationLimitReached,
    ImmutableVersionError,
    InvalidStateTransition,
)


def create_initial_version(contract, content, user=None):
    if ContractVersion.objects.filter(contract=contract).exists():
        raise Exception("Initial version already exists.")

    return ContractVersion.objects.create(
        contract=contract,
        content_snapshot=content,
        created_by=user,
        version_number=1,
        status="draft",
    )


def create_new_version(contract, content, user=None):
    last_version = (
        ContractVersion.objects
        .filter(contract=contract)
        .order_by("-version_number")
        .first()
    )

    if not last_version:
        raise Exception("No previous version exists.")

    if contract.versions.count() >= contract.max_versions:
        raise NegotiationLimitReached()

    new_version_number = last_version.version_number + 1

    # mark previous version superseded
    last_version.status = "superseded"
    last_version.superseded = True
    last_version.save(update_fields=["status", "superseded"])

    return ContractVersion.objects.create(
        contract=contract,
        content_snapshot=content,
        created_by=user,
        version_number=new_version_number,
        previous_version=last_version,
        status="draft",
    )


def transition_version(version, new_status):
    validate_transition(version.status, new_status)

    version.status = new_status
    version.save(update_fields=["status"])


