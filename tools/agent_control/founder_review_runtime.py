"""Trusted application boundary for externally authorized product reviews.

The application side of this boundary is intentionally not a Founder
transport.  A provisioned Agent Control composition owns FounderIntake,
FounderSessions, FounderTransport, ProductionProductReviewAdapter, and the
Registry.  It exposes only initiation and observation to the application.
"""
from uuid import UUID, uuid5

from .founder_review_auth import ProductProposalReviewBinding
from .records import ProductReviewCompletedEvent
from .schema import valid_format
from .types import AuthorityError, ValidationError


PRODUCT_REVIEW_OPERATION_NAMESPACE = UUID("2dcd4d2c-75a2-4d5f-8f0c-3fd3d6f5e6a1")


def product_review_operation_id(binding):
    """Derive the stable Agent Control operation for one signed subject."""
    if type(binding) is not ProductProposalReviewBinding:
        raise ValidationError("Product review binding required.")
    return str(uuid5(PRODUCT_REVIEW_OPERATION_NAMESPACE, binding.binding_digest))


class FounderReviewBoundary:
    """Explicit contract implemented by the provisioned Agent Control side.

    The callbacks run in the trusted Agent Control composition.  They must
    route through the existing FounderIntake/FounderSessions chain and return
    only a bounded initiation result or a Registry-loaded trusted event.
    """

    trusted_agent_control_boundary = True

    def __init__(self, *, request_review, observe_review):
        if not callable(request_review) or not callable(observe_review):
            raise ValidationError("Agent Control Founder review boundary required.")
        self._request_review = request_review
        self._observe_review = observe_review

    def request_product_review(self, binding, *, operation_id):
        if type(binding) is not dict:
            raise ValidationError("Canonical Founder review binding required.")
        return self._request_review(binding, operation_id=operation_id)

    def observe_product_review(self, task_id):
        return self._observe_review(task_id)


class TrustedFounderReviewRuntime:
    """Django-facing wrapper around a trusted Agent Control composition."""

    available = True

    def __init__(self, boundary):
        if (getattr(boundary, "trusted_agent_control_boundary", False) is not True
                or not callable(getattr(boundary, "request_product_review", None))
                or not callable(getattr(boundary, "observe_product_review", None))):
            raise ValidationError("Trusted Agent Control Founder boundary required.")
        self._boundary = boundary

    def request_review(self, binding):
        if type(binding) is not ProductProposalReviewBinding:
            raise AuthorityError("Verified Founder review binding required.")
        result = self._boundary.request_product_review(
            binding.to_dict(),
            operation_id=product_review_operation_id(binding),
        )
        if type(result) is not dict or set(result) != {"status"}:
            raise ValidationError("Bounded Founder review initiation result required.")
        if result["status"] not in {"REQUESTED", "PENDING", "ALREADY_REQUESTED"}:
            raise AuthorityError("Founder review initiation was not accepted.")
        return result

    def observe_review(self, *, task_id):
        if type(task_id) is not str or not valid_format("task-id", task_id):
            raise ValidationError("Agent Control task binding required.")
        event = self._boundary.observe_product_review(task_id)
        if event is None:
            return None
        if (type(event) is not ProductReviewCompletedEvent
                or not getattr(event, "_trusted", False)
                or event["task_id"] != task_id):
            raise AuthorityError("Trusted ProductReviewCompletedEvent required.")
        return event


__all__ = [
    "FounderReviewBoundary",
    "PRODUCT_REVIEW_OPERATION_NAMESPACE",
    "TrustedFounderReviewRuntime",
    "product_review_operation_id",
]
