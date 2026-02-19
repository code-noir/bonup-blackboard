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

def create_new_version(*, contract, content, user):
    last_version = contract.versions.first()

    # mark old version as superseded
    ContractVersion.objects.filter(id=last_version.id).update(
        status="superseded",
        superseded=True,
    )

    new_version_number = last_version.version_number + 1

    return ContractVersion.objects.create(
        contract=contract,
        version_number=new_version_number,
        content_snapshot=content,
        status="draft",
        created_by=user,
    )


def transition_version(version, new_status):
    validate_transition(version.status, new_status)

    version.status = new_status
    version.save(update_fields=["status"])


