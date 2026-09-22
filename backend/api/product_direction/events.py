"""Trusted Agent Control domain-event projection for Product Direction."""

from django.db import transaction

from tools.agent_control.records import ProductReviewCompletedEvent
from tools.agent_control.prod_artifact import (
    ProposalArtifactError,
    safe_proposal_projection,
    validate_safe_proposal_projection,
)

from backend.bonup.models import AgentControlEventInbox, ProductDirectionTask

from . import proposal as proposal_module


PRODUCT_DIRECTION_CONSUMER = "product-direction"
REVIEW_STATUS_BY_DECISION = {
    "ACCEPT": ProductDirectionTask.STATUS_APPROVED_INTERNAL,
    "REJECT": ProductDirectionTask.STATUS_REJECTED,
    "REQUEST_CHANGES": ProductDirectionTask.STATUS_CHANGES_REQUESTED,
}


class ProductDirectionProjectionError(ValueError):
    """Bounded projection failure; the inbox acknowledgement must roll back."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _fail(reason):
    raise ProductDirectionProjectionError(reason)


def _projection_for_event(event, *, artifact_store, proposal_projection):
    if proposal_projection is not None:
        try:
            value = validate_safe_proposal_projection(proposal_projection)
        except ProposalArtifactError:
            _fail("ARTIFACT_INVALID")
    else:
        store = (proposal_module.get_proposal_artifact_store()
                 if artifact_store is None else artifact_store)
        try:
            value = safe_proposal_projection(store.load(event["proposal_id"]))
        except ProposalArtifactError as error:
            _fail(getattr(error, "reason", "ARTIFACT_INVALID"))
    if any(value[field] != event[event_field] for field, event_field in (
            ("task_id", "task_id"), ("agent_id", "agent_id"),
            ("artifact_id", "artifact_id"), ("artifact_digest", "artifact_digest"),
            ("proposal_id", "proposal_id"), ("proposal_digest", "proposal_digest"),
            ("knowledge_state", "prior_knowledge_state"))):
        _fail("EVENT_BINDING_MISMATCH")
    return value


def consume_product_review_completed(event, *, artifact_store=None,
                                     proposal_projection=None,
                                     consumer_name=PRODUCT_DIRECTION_CONSUMER):
    """Apply one verified event without invoking Founder or review authority."""
    if (type(event) is not ProductReviewCompletedEvent
            or not getattr(event, "_trusted", False)):
        _fail("EVENT_INVALID")
    expected_status = REVIEW_STATUS_BY_DECISION[event["decision"]]

    with transaction.atomic():
        inbox, created = AgentControlEventInbox.objects.get_or_create(
            consumer_name=consumer_name,
            event_id=event["event_id"],
            defaults={
                "event_type": event["event_type"],
                "event_digest": event["event_digest"],
            },
        )
        if not created:
            if (inbox.event_type != event["event_type"]
                    or inbox.event_digest != event["event_digest"]):
                _fail("EVENT_INBOX_MISMATCH")
            return {"status": "DUPLICATE", "event_id": event["event_id"]}

        try:
            task = ProductDirectionTask.objects.select_for_update().get(
                agent_control_task_id=event["task_id"])
        except ProductDirectionTask.DoesNotExist:
            _fail("TASK_BINDING_MISMATCH")

        if (task.agent_id != ProductDirectionTask.AGENT_ID
                or task.agent_control_task_id != event["task_id"]
                or task.proposal_artifact_id != event["artifact_id"]
                or task.proposal_id is None
                or str(task.proposal_id) != event["proposal_id"]
                or task.proposal_digest != event["proposal_digest"]):
            _fail("EVENT_BINDING_MISMATCH")
        artifact_store_value = _projection_for_event(
            event, artifact_store=artifact_store,
            proposal_projection=proposal_projection,
        )
        if (artifact_store_value["task_id"] != event["task_id"]
                or artifact_store_value["proposal_id"] != event["proposal_id"]
                or artifact_store_value["proposal_digest"] != event["proposal_digest"]
                or artifact_store_value["artifact_id"] != event["artifact_id"]
                or artifact_store_value["artifact_digest"] != event["artifact_digest"]):
            _fail("EVENT_BINDING_MISMATCH")

        if task.review_id is not None:
            if (str(task.review_id) != event["review_id"]
                    or task.review_digest != event["review_digest"]
                    or task.status != expected_status):
                _fail("REVIEW_PROJECTION_CONFLICT")
            return {"status": "ALREADY_PROJECTED", "event_id": event["event_id"]}
        if task.status not in {
            ProductDirectionTask.STATUS_WORKING_PROPOSAL,
            ProductDirectionTask.STATUS_AWAITING_FOUNDER_REVIEW,
        }:
            _fail("REVIEW_PROJECTION_CONFLICT")

        task.status = expected_status
        task.review_id = event["review_id"]
        task.review_digest = event["review_digest"]
        try:
            task.save(update_fields=["status", "review_id", "review_digest", "updated_at"])
        except ProductDirectionProjectionError:
            raise
        except Exception:
            _fail("PROJECTION_FAILED")
        return {"status": "APPLIED", "event_id": event["event_id"]}


def consume_product_review_event(registry, event_id, *, artifact_store=None,
                                 consumer_name=PRODUCT_DIRECTION_CONSUMER):
    """Load an event through Agent Control integrity checks, then project it."""
    event = registry.load_domain_event(event_id)
    return consume_product_review_completed(
        event, artifact_store=artifact_store, consumer_name=consumer_name,
    )
