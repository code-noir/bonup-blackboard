"""Fail-closed application bridge for authenticated PROD-01 review."""
from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from tools.agent_control.founder_review_auth import (
    ProductProposalReviewBinding,
    REVIEW_DECISIONS,
)
from tools.agent_control.prod_artifact import ProposalArtifactError
from tools.agent_control.records import ProductReviewRecord
from tools.agent_control.schema import valid_format
from tools.agent_control.types import AuthorityError, ValidationError

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
REVIEW_STATUS_BY_DECISION = {
    "ACCEPT": ProductDirectionTask.STATUS_APPROVED_INTERNAL,
    "REJECT": ProductDirectionTask.STATUS_REJECTED,
    "REQUEST_CHANGES": ProductDirectionTask.STATUS_CHANGES_REQUESTED,
}
SAFE_REVIEW_REASONS = frozenset({
    "TASK_BINDING_MISMATCH", "PROPOSAL_NOT_AVAILABLE", "PROPOSAL_BINDING_MISMATCH",
    "ARTIFACT_BINDING_MISMATCH", "ARTIFACT_MISSING", "ARTIFACT_INVALID",
    "AGENT_BINDING_MISMATCH", "PROPOSAL_DIGEST_MISMATCH", "KNOWLEDGE_STATE_INVALID",
    "REVIEW_ALREADY_RECORDED", "REVIEW_NOT_AVAILABLE", "REVIEW_BINDING_INVALID",
    "REVIEW_RECORD_INVALID", "REVIEW_DECISION_INVALID", "REVIEW_STATE_INVALID",
    "REVIEW_AUTHENTICATION_INVALID", "FOUNDER_REVIEW_DENIED",
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

    def request_challenge(self, binding):
        raise FounderRuntimeUnavailable()

    def submit_signature(self, *, task_id, signature):
        raise FounderRuntimeUnavailable()


def get_founder_review_runtime():
    """Return the trusted external bridge; no Founder session is created here."""
    return UnavailableFounderReviewRuntime()


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


def _safe_record(record, target):
    """Accept only a controller-created ProductReviewRecord for this target."""
    if type(record) is not ProductReviewRecord:
        _review_failure("REVIEW_RECORD_INVALID")
    try:
        value = record.to_dict()
        expected = {
            "artifact_id": target.artifact.value["artifact_id"],
            "artifact_digest": target.artifact.value["artifact_digest"],
            "task_id": target.task.agent_control_task_id,
            "agent_id": ProductDirectionTask.AGENT_ID,
            "proposal_id": str(target.task.proposal_id),
            "proposal_digest": target.task.proposal_digest,
            "prior_knowledge_state": "WORKING",
        }
        if any(value.get(key) != expected_value for key, expected_value in expected.items()):
            _review_failure("REVIEW_BINDING_MISMATCH")
        decision = value.get("decision")
        if decision not in REVIEW_DECISIONS:
            _review_failure("REVIEW_DECISION_INVALID")
        expected_state = "APPROVED_INTERNAL" if decision == "ACCEPT" else "WORKING"
        if value.get("resulting_knowledge_state") != expected_state:
            _review_failure("REVIEW_STATE_INVALID")
        if value.get("review_id") is None or not valid_format("uuid", value["review_id"]):
            _review_failure("REVIEW_RECORD_INVALID")
        if value.get("review_digest") is None or not valid_format("sha256", value["review_digest"]):
            _review_failure("REVIEW_RECORD_INVALID")
        authentication = value.get("authentication", {})
        if authentication.get("purpose") != "PROD_PROPOSAL_REVIEW":
            _review_failure("REVIEW_AUTHENTICATION_INVALID")
        if authentication.get("binding_digest") != target.binding.binding_digest:
            _review_failure("REVIEW_BINDING_MISMATCH")
        if "PUBLICATION_ELIGIBLE" in record.canonical_json():
            _review_failure("REVIEW_STATE_INVALID")
    except (KeyError, TypeError, ValueError):
        _review_failure("REVIEW_RECORD_INVALID")
    return value


def safe_review_result(value):
    return {
        "review_id": value["review_id"],
        "review_digest": value["review_digest"],
        "decision": value["decision"],
        "prior_knowledge_state": value["prior_knowledge_state"],
        "resulting_knowledge_state": value["resulting_knowledge_state"],
        "proposal_id": value["proposal_id"],
        "proposal_digest": value["proposal_digest"],
    }


def request_review_challenge(task, *, decision, reason):
    if task.status != ProductDirectionTask.STATUS_WORKING_PROPOSAL:
        _review_failure("REVIEW_NOT_AVAILABLE")
    target = load_review_target(task, decision=decision, reason=reason)
    runtime = get_founder_review_runtime()
    if not getattr(runtime, "available", False):
        raise FounderRuntimeUnavailable()
    try:
        runtime.request_challenge(target.binding)
    except FounderRuntimeUnavailable:
        raise
    except FounderReviewRuntimeError:
        raise
    except Exception:
        raise FounderReviewRuntimeError("FOUNDER_REVIEW_DENIED") from None

    ProductDirectionTask.objects.filter(
        pk=task.pk,
        status__in=REVIEWABLE_STATUSES,
        review_id__isnull=True,
    ).update(status=ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW)
    return {
        "status": "CHALLENGE_REQUESTED",
        "decision": decision,
        "proposal_id": str(target.task.proposal_id),
        "proposal_digest": target.task.proposal_digest,
    }


def submit_review_signature(task, *, signature):
    if task.status in FINAL_REVIEW_STATUSES or task.review_id is not None:
        _review_failure("REVIEW_ALREADY_RECORDED")
    if task.status != ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW:
        _review_failure("REVIEW_NOT_AVAILABLE")
    runtime = get_founder_review_runtime()
    if not getattr(runtime, "available", False):
        raise FounderRuntimeUnavailable()
    try:
        record = runtime.submit_signature(task_id=str(task.id), signature=signature)
    except FounderRuntimeUnavailable:
        raise
    except FounderReviewRuntimeError:
        raise
    except Exception:
        raise FounderReviewRuntimeError("FOUNDER_REVIEW_DENIED") from None

    # The runtime owns the challenge, signature verification, Founder session,
    # adapter, and durable Registry write. Re-load the exact artifact before
    # accepting the returned record or changing application state.
    if type(record) is not ProductReviewRecord:
        _review_failure("REVIEW_RECORD_INVALID")
    try:
        record_value = record.to_dict()
        record_decision = record_value["decision"]
        record_reason = record_value["reason"]
    except (KeyError, TypeError, ValueError):
        _review_failure("REVIEW_RECORD_INVALID")
    target = load_review_target(
        ProductDirectionTask.objects.get(pk=task.pk),
        decision=record_decision,
        reason=record_reason,
    )
    value = _safe_record(record, target)
    with transaction.atomic():
        current = ProductDirectionTask.objects.select_for_update().get(pk=task.pk)
        if current.status in FINAL_REVIEW_STATUSES or current.review_id is not None:
            _review_failure("REVIEW_ALREADY_RECORDED")
        if current.status != ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW:
            _review_failure("REVIEW_NOT_AVAILABLE")
        current.status = REVIEW_STATUS_BY_DECISION[value["decision"]]
        current.review_id = UUID(value["review_id"])
        current.review_digest = value["review_digest"]
        current.save(update_fields=["status", "review_id", "review_digest", "updated_at"])
    return safe_review_result(value)
