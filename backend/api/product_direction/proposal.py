"""Read-only application bridge for immutable validated PROD-01 artifacts."""
from tools.agent_control.prod_artifact import ProposalArtifactError, ProposalArtifactStore

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

    proposal = value["proposal"]
    return {
        "application_task_id": str(task.id),
        "agent_control_task_id": task.agent_control_task_id,
        "agent_id": value["agent_id"],
        "proposal_id": value["proposal_id"],
        "proposal_digest": value["proposal_digest"],
        "knowledge_state": value["knowledge_state"],
        "title": proposal["title"],
        "problem_user_need": proposal["problem_user_need"],
        "objective": proposal["objective"],
        "proposed_requirement": proposal["proposed_requirement"],
        "acceptance_intent": proposal["acceptance_intent"],
        "dependencies": proposal["dependencies"],
        "assumptions": proposal["assumptions"],
        "risks_open_questions": proposal["risks_open_questions"],
        "priority_recommendation": proposal["priority_recommendation"],
        "evidence_references": proposal["evidence_references"],
    }
