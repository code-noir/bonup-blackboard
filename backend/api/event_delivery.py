"""Trusted server-side fan-out boundary for Agent Control domain events."""

from tools.agent_control.records import ProductReviewCompletedEvent

from .blackboard.events import BLACKBOARD_PRODUCT_DIRECTION_CONSUMER, consume_product_review_completed as consume_blackboard
from .product_direction.events import PRODUCT_DIRECTION_CONSUMER, consume_product_review_completed as consume_product_direction


class TrustedDjangoProjectionBoundary:
    """The only application seam accepted by the durable delivery worker."""

    trusted_application_boundary = True
    available = True

    def __init__(self, *, artifact_store=None):
        self.artifact_store = artifact_store

    def deliver(self, event, consumer_name):
        if (type(event) is not ProductReviewCompletedEvent
                or not getattr(event, "_trusted", False)):
            raise ValueError("Trusted ProductReviewCompletedEvent required.")
        if consumer_name == PRODUCT_DIRECTION_CONSUMER:
            return consume_product_direction(event, artifact_store=self.artifact_store)
        if consumer_name == BLACKBOARD_PRODUCT_DIRECTION_CONSUMER:
            return consume_blackboard(event, artifact_store=self.artifact_store)
        raise ValueError("Unknown projection consumer.")


__all__ = ["TrustedDjangoProjectionBoundary"]
