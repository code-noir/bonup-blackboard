"""Fail-closed application bridge for authenticated PROD-01 review."""
from dataclasses import dataclass
from django.db import transaction
from tools.agent_control.founder_review_auth import ProductProposalReviewBinding
from tools.agent_control.prod_artifact import ProposalArtifactError
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control.founder_review_runtime import TrustedFounderReviewRuntime

from backend.bonup.models import ProductDirectionTask

from . import proposal as proposal_module
from .proposal import ProposalReadFailure, read_product_direction_proposal


REVIEWABLE_STATUSES = frozenset({
    ProductDirectionTask.STATUS_WORKING_PROPOSAL,
    ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW,
})
FINAL_REVIEW_STATUSES = frozenset({
    ProductDirectionTask.STATUS_APPROVED_INTERNAL,
    ProductDirectionTask.STATUS_REJECTED,
    ProductDirectionTask.STATUS_CHANGES_REQUESTED,
})
SAFE_REVIEW_REASONS = frozenset({
    "TASK_BINDING_MISMATCH", "PROPOSAL_NOT_AVAILABLE", "PROPOSAL_BINDING_MISMATCH",
    "ARTIFACT_BINDING_MISMATCH", "ARTIFACT_MISSING", "ARTIFACT_INVALID",
    "AGENT_BINDING_MISMATCH", "PROPOSAL_DIGEST_MISMATCH", "KNOWLEDGE_STATE_INVALID",
    "REVIEW_ALREADY_RECORDED", "REVIEW_NOT_AVAILABLE", "REVIEW_BINDING_INVALID",
    "REVIEW_RECORD_INVALID", "REVIEW_DECISION_INVALID", "REVIEW_STATE_INVALID",
    "REVIEW_AUTHENTICATION_INVALID", "REVIEW_EVENT_UNAVAILABLE",
    "REVIEW_PROJECTION_RETRY", "FOUNDER_REVIEW_DENIED", "FOUNDER_REVIEW_PENDING",
    "FOUNDER_EXTERNAL_ONLY",
})


class FounderRuntimeUnavailable(Exception):
    """The installed trusted Founder service is not available."""


class FounderReviewRuntimeError(Exception):
    """Bounded failure returned by the trusted Founder service bridge."""

    def __init__(self, reason="FOUNDER_REVIEW_DENIED"):
        bounded = reason if reason in SAFE_REVIEW_REASONS else "FOUNDER_REVIEW_DENIED"
        super().__init__(bounded)
        self.reason = bounded


class UnavailableFounderReviewRuntime:
    """Production default until Founder/Agent Control is provisioned."""

    available = False

    def request_review(self, binding):
        raise FounderRuntimeUnavailable()

    def observe_review(self, *, task_id):
        raise FounderRuntimeUnavailable()


_configured_founder_review_runtime = None


def configure_founder_review_runtime(runtime):
    """Install only a trusted Agent Control composition at application startup."""
    if type(runtime) is not TrustedFounderReviewRuntime:
        raise ValidationError("Trusted Founder review runtime required.")
    global _configured_founder_review_runtime
    _configured_founder_review_runtime = runtime


def get_founder_review_runtime():
    """Return the trusted external bridge; never construct Founder authority."""
    return (_configured_founder_review_runtime
            if _configured_founder_review_runtime is not None
            else UnavailableFounderReviewRuntime())


@dataclass(frozen=True)
class ReviewTarget:
    task: ProductDirectionTask
    artifact: object
    binding: ProductProposalReviewBinding


def _review_failure(reason):
    raise FounderReviewRuntimeError(reason)


def load_review_target(task, *, decision, reason):
    """Resolve one exact application task to one verified immutable artifact."""
    if type(task) is not ProductDirectionTask:
        _review_failure("TASK_BINDING_MISMATCH")
    if task.status in FINAL_REVIEW_STATUSES or task.review_id is not None:
        _review_failure("REVIEW_ALREADY_RECORDED")
    if task.status not in REVIEWABLE_STATUSES:
        _review_failure("REVIEW_NOT_AVAILABLE")

    store = proposal_module.get_proposal_artifact_store()
    try:
        # This verifies the application binding, artifact identity, task ID,
        # proposal digest, and WORKING knowledge state before signing.
        read_product_direction_proposal(task, artifact_store=store)
        artifact = store.load(str(task.proposal_id))
        binding = ProductProposalReviewBinding.from_artifact(
            artifact, decision=decision, reason=reason)
    except ProposalReadFailure as error:
        _review_failure(error.reason)
    except ProposalArtifactError as error:
        _review_failure(getattr(error, "reason", "ARTIFACT_INVALID"))
    except (AuthorityError, ValidationError):
        _review_failure("REVIEW_BINDING_INVALID")
    return ReviewTarget(task=task, artifact=artifact, binding=binding)


def request_review(task, *, decision, reason):
    """Initiate Founder review with only the server-derived binding."""
    with transaction.atomic():
        task = ProductDirectionTask.objects.select_for_update().get(pk=task.pk)
        if task.status == ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW:
            return {
                "status": "ALREADY_REQUESTED",
                "proposal_id": str(task.proposal_id),
                "proposal_digest": task.proposal_digest,
            }
        if task.status != ProductDirectionTask.STATUS_WORKING_PROPOSAL:
            _review_failure("REVIEW_NOT_AVAILABLE")
        target = load_review_target(task, decision=decision, reason=reason)
        runtime = get_founder_review_runtime()
        if not getattr(runtime, "available", False):
            raise FounderRuntimeUnavailable()
        try:
            runtime.request_review(target.binding)
        except FounderRuntimeUnavailable:
            raise
        except FounderReviewRuntimeError:
            raise
        except Exception:
            raise FounderReviewRuntimeError("FOUNDER_REVIEW_DENIED") from None
        task.status = ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW
        task.save(update_fields=["status", "updated_at"])
    return {
        "status": "REQUESTED",
        "decision": decision,
        "proposal_id": str(target.task.proposal_id),
        "proposal_digest": target.task.proposal_digest,
    }


def observe_review(task):
    """Receive one committed event and let the EVENT-01 consumer project it."""
    if task.status in FINAL_REVIEW_STATUSES or task.review_id is not None:
        return {
            "status": "ALREADY_PROJECTED",
            "review_id": str(task.review_id),
            "review_digest": task.review_digest,
        }
    if task.status != ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW:
        _review_failure("REVIEW_NOT_AVAILABLE")
    runtime = get_founder_review_runtime()
    if not getattr(runtime, "available", False):
        raise FounderRuntimeUnavailable()
    try:
        event = runtime.observe_review(task_id=task.agent_control_task_id)
    except FounderRuntimeUnavailable:
        raise
    except FounderReviewRuntimeError:
        raise
    except Exception:
        raise FounderReviewRuntimeError("REVIEW_EVENT_UNAVAILABLE") from None
    if event is None:
        return {"status": "PENDING"}
    from .events import ProductDirectionProjectionError, consume_product_review_completed
    try:
        projection = consume_product_review_completed(event)
    except ProductDirectionProjectionError:
        _review_failure("REVIEW_PROJECTION_RETRY")
    return {
        "status": projection["status"],
        "event_id": event["event_id"],
        "review_id": event["review_id"],
        "review_digest": event["review_digest"],
        "decision": event["decision"],
        "resulting_knowledge_state": event["resulting_knowledge_state"],
    }
