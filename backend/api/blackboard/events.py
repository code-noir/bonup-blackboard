"""Independent Blackboard projection for PRODUCT_REVIEW_COMPLETED v1."""

from datetime import datetime

from django.db import transaction

from tools.agent_control.prod_artifact import ProposalArtifactError, ProposalArtifactStore
from tools.agent_control.records import ProductReviewCompletedEvent
from tools.agent_control.registry import Registry
from tools.agent_control.schema import valid_format
from tools.agent_control.types import ValidationError

from backend.bonup.models import AgentControlEventInbox, ApprovedProductDirection


BLACKBOARD_PRODUCT_DIRECTION_CONSUMER = "blackboard-product-direction"
APPROVED_INTERNAL = "APPROVED_INTERNAL"


class BlackboardProjectionError(ValueError):
    """Bounded projection failure; inbox acknowledgement must roll back."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _fail(reason):
    raise BlackboardProjectionError(reason)


def _occurred_at(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        _fail("EVENT_TIME_INVALID")


def _artifact_for_event(event, artifact_store):
    if type(artifact_store) is not ProposalArtifactStore:
        _fail("ARTIFACT_INVALID")
    try:
        artifact = artifact_store.load(event["proposal_id"])
    except ProposalArtifactError as error:
        _fail(getattr(error, "reason", "ARTIFACT_INVALID"))
    value = artifact.value
    proposal = value["proposal"]
    if (
        value["agent_id"] != event["agent_id"]
        or value["task_id"] != event["task_id"]
        or value["proposal_id"] != event["proposal_id"]
        or value["proposal_digest"] != event["proposal_digest"]
        or value["artifact_id"] != event["artifact_id"]
        or value["artifact_digest"] != event["artifact_digest"]
        or value["knowledge_state"] != "WORKING"
        or proposal["agent_id"] != event["agent_id"]
        or proposal["task_id"] != event["task_id"]
        or proposal["proposal_id"] != event["proposal_id"]
        or proposal["knowledge_state"] != "WORKING"
    ):
        _fail("EVENT_PROVENANCE_MISMATCH")
    return value


def _validate_event(event):
    if (type(event) is not ProductReviewCompletedEvent
            or not getattr(event, "_trusted", False)):
        _fail("EVENT_INVALID")
    value = event.to_dict()
    if (
        value["event_version"] != 1
        or value["event_type"] != "PRODUCT_REVIEW_COMPLETED"
        or value["agent_id"] != "PROD-01"
        or value["prior_knowledge_state"] != "WORKING"
        or value["resulting_knowledge_state"] not in {"WORKING", APPROVED_INTERNAL}
        or value["decision"] not in {"ACCEPT", "REJECT", "REQUEST_CHANGES"}
        or value["artifact_id"] != "PROD-01-" + value["proposal_id"]
        or not valid_format("task-id", value["task_id"])
        or not valid_format("uuid", value["review_id"])
        or not valid_format("sha256", value["review_digest"])
        or not valid_format("sha256", value["proposal_digest"])
        or not valid_format("sha256", value["artifact_digest"])
        or not valid_format("sha256", value["event_digest"])
        or value["correlation_id"] != value["operation_id"]
    ):
        _fail("EVENT_PROVENANCE_MISMATCH")
    expected_state = APPROVED_INTERNAL if value["decision"] == "ACCEPT" else "WORKING"
    if value["resulting_knowledge_state"] != expected_state:
        _fail("EVENT_PROVENANCE_MISMATCH")
    return value


def _projection_values(event, artifact):
    proposal = artifact["proposal"]
    return {
        "event_digest": event["event_digest"],
        "agent_control_task_id": event["task_id"],
        "agent_id": event["agent_id"],
        "proposal_id": event["proposal_id"],
        "proposal_digest": event["proposal_digest"],
        "artifact_id": event["artifact_id"],
        "artifact_digest": event["artifact_digest"],
        "review_id": event["review_id"],
        "review_digest": event["review_digest"],
        "resulting_knowledge_state": event["resulting_knowledge_state"],
        "event_occurred_at": _occurred_at(event["occurred_at"]),
        "title": proposal["title"],
        "objective": proposal["objective"],
        "proposed_requirement": proposal["proposed_requirement"],
        "acceptance_intent": proposal["acceptance_intent"],
    }


def consume_product_review_completed(event, *, artifact_store=None,
                                     consumer_name=BLACKBOARD_PRODUCT_DIRECTION_CONSUMER):
    """Project directly from one trusted Agent Control event.

    ProductDirectionTask is deliberately not read here. A missing projection
    can be rebuilt even when its inbox acknowledgement already exists.
    """
    value = _validate_event(event)
    store = ProposalArtifactStore() if artifact_store is None else artifact_store
    artifact = _artifact_for_event(event, store)
    approved = value["decision"] == "ACCEPT" and value["resulting_knowledge_state"] == APPROVED_INTERNAL
    projection = _projection_values(event, artifact) if approved else None

    with transaction.atomic():
        inbox, created = AgentControlEventInbox.objects.get_or_create(
            consumer_name=consumer_name,
            event_id=value["event_id"],
            defaults={
                "event_type": value["event_type"],
                "event_digest": value["event_digest"],
            },
        )
        if not created and (
            inbox.event_type != value["event_type"]
            or inbox.event_digest != value["event_digest"]
        ):
            _fail("EVENT_INBOX_MISMATCH")
        if not approved:
            return {"status": "NOT_APPROVED", "event_id": value["event_id"]}

        existing = ApprovedProductDirection.objects.filter(
            event_id=value["event_id"]
        ).first()
        if existing is not None:
            existing_values = {
                key: str(getattr(existing, key))
                if key in {"proposal_id", "review_id"}
                else getattr(existing, key)
                for key in projection
                if key not in {"event_occurred_at", "acceptance_intent"}
            }
            expected_values = {
                key: item for key, item in projection.items()
                if key not in {"event_occurred_at", "acceptance_intent"}
            }
            if existing_values != expected_values or (
                existing.event_occurred_at != projection["event_occurred_at"]
                or existing.acceptance_intent != projection["acceptance_intent"]
            ):
                _fail("PROJECTION_CONFLICT")
            return {"status": "DUPLICATE", "event_id": value["event_id"]}

        ApprovedProductDirection.objects.create(
            event_id=value["event_id"],
            **projection,
        )
        return {
            "status": "APPLIED" if created else "REBUILT",
            "event_id": value["event_id"],
        }


def consume_product_review_event(registry, event_id, *, artifact_store=None,
                                 consumer_name=BLACKBOARD_PRODUCT_DIRECTION_CONSUMER):
    if type(registry) is not Registry:
        raise ValidationError("Trusted Agent Control Registry required.")
    event = registry.load_domain_event(event_id)
    return consume_product_review_completed(
        event,
        artifact_store=artifact_store,
        consumer_name=consumer_name,
    )
