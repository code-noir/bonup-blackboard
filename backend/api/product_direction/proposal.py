"""Read-only application bridge for immutable validated PROD-01 artifacts."""
from tools.agent_control.prod_artifact import (
    ProposalArtifactError,
    ProposalArtifactStore,
    safe_proposal_projection,
    validate_safe_proposal_projection,
)
from tools.agent_control.prod_application import ApplicationRemoteError

from backend.bonup.models import ProductDirectionTask


READABLE_STATUSES = frozenset({
    ProductDirectionTask.STATUS_WORKING_PROPOSAL,
    ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW,
    ProductDirectionTask.STATUS_APPROVED_INTERNAL,
    ProductDirectionTask.STATUS_REJECTED,
    ProductDirectionTask.STATUS_CHANGES_REQUESTED,
})


class ProposalReadFailure(ValueError):
    """Bounded proposal-read failure; its reason is safe for the API."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


_configured_proposal_reader = None


def configure_proposal_reader(reader):
    """Install the trusted Agent Control proposal projection reader."""
    if not callable(getattr(reader, "read_proposal", None)):
        raise ValueError("Trusted proposal projection reader required.")
    global _configured_proposal_reader
    _configured_proposal_reader = reader


def get_proposal_artifact_store():
    """Use the fixed trusted artifact location; callers cannot select a path."""
    return ProposalArtifactStore()


def _fail(reason):
    raise ProposalReadFailure(reason)


def read_product_direction_proposal(task, *, artifact_store=None):
    if type(task) is not ProductDirectionTask:
        _fail("TASK_BINDING_MISMATCH")
    if task.status not in READABLE_STATUSES:
        _fail("PROPOSAL_NOT_AVAILABLE")
    if (task.agent_id != ProductDirectionTask.AGENT_ID
            or not task.agent_control_task_id
            or not task.proposal_artifact_id
            or task.proposal_id is None
            or not task.proposal_digest):
        _fail("PROPOSAL_BINDING_MISMATCH")
    if task.proposal_artifact_id != "PROD-01-" + str(task.proposal_id):
        _fail("ARTIFACT_BINDING_MISMATCH")

    if artifact_store is None and _configured_proposal_reader is not None:
        try:
            value = _configured_proposal_reader.read_proposal(
                application_task_id=str(task.id),
                agent_control_task_id=task.agent_control_task_id,
                proposal_artifact_id=task.proposal_artifact_id,
                proposal_id=str(task.proposal_id),
                proposal_digest=task.proposal_digest,
            )
            value = validate_safe_proposal_projection(value)
        except ProposalArtifactError:
            _fail("ARTIFACT_INVALID")
        except ApplicationRemoteError as error:
            _fail(error.reason)
        except Exception:
            _fail("ARTIFACT_INVALID")
        if (value["artifact_id"] != task.proposal_artifact_id
                or value["task_id"] != task.agent_control_task_id
                or value["agent_id"] != ProductDirectionTask.AGENT_ID
                or value["proposal_id"] != str(task.proposal_id)
                or value["proposal_digest"] != task.proposal_digest
                or value["knowledge_state"] != "WORKING"):
            _fail("PROPOSAL_BINDING_MISMATCH")
        return dict(value, application_task_id=str(task.id),
                    agent_control_task_id=value["task_id"])

    store = get_proposal_artifact_store() if artifact_store is None else artifact_store
    if type(store) is not ProposalArtifactStore:
        _fail("ARTIFACT_INVALID")
    try:
        artifact = store.load(str(task.proposal_id))
    except ProposalArtifactError as error:
        raise ProposalReadFailure(getattr(error, "reason", "ARTIFACT_INVALID")) from None

    value = artifact.value
    if value["artifact_id"] != task.proposal_artifact_id:
        _fail("ARTIFACT_BINDING_MISMATCH")
    if value["task_id"] != task.agent_control_task_id:
        _fail("TASK_BINDING_MISMATCH")
    if value["agent_id"] != ProductDirectionTask.AGENT_ID:
        _fail("AGENT_BINDING_MISMATCH")
    if value["proposal_id"] != str(task.proposal_id):
        _fail("PROPOSAL_BINDING_MISMATCH")
    if value["proposal_digest"] != task.proposal_digest:
        _fail("PROPOSAL_DIGEST_MISMATCH")
    if value["knowledge_state"] != "WORKING":
        _fail("KNOWLEDGE_STATE_INVALID")

    return dict(safe_proposal_projection(artifact), application_task_id=str(task.id),
                agent_control_task_id=task.agent_control_task_id)
