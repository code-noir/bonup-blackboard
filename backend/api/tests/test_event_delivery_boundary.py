from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from tools.agent_control.records import ProductReviewCompletedEvent
from tools.agent_control.serialization import digest

from backend.api.event_delivery import TrustedDjangoProjectionBoundary


def trusted_event():
    operation_id = str(uuid4())
    value = {
        "event_version": 1,
        "event_id": str(uuid4()),
        "event_type": "PRODUCT_REVIEW_COMPLETED",
        "occurred_at": "2026-09-20T00:00:00Z",
        "review_id": str(uuid4()),
        "review_digest": "a" * 64,
        "task_id": "ATS-1234",
        "agent_id": "PROD-01",
        "artifact_id": "PROD-01-" + "00000000-0000-4000-8000-000000000701",
        "artifact_digest": "b" * 64,
        "proposal_id": "00000000-0000-4000-8000-000000000701",
        "proposal_digest": "c" * 64,
        "decision": "ACCEPT",
        "prior_knowledge_state": "WORKING",
        "resulting_knowledge_state": "APPROVED_INTERNAL",
        "operation_id": operation_id,
        "correlation_id": operation_id,
    }
    value["event_digest"] = digest(value)
    event = ProductReviewCompletedEvent(value)
    object.__setattr__(event, "_trusted", True)
    return event


class TrustedDjangoProjectionBoundaryTests(SimpleTestCase):
    def test_routes_each_consumer_independently(self):
        boundary = TrustedDjangoProjectionBoundary()
        event = trusted_event()
        with patch("backend.api.event_delivery.consume_product_direction") as product, \
                patch("backend.api.event_delivery.consume_blackboard") as blackboard:
            boundary.deliver(event, "product-direction")
            boundary.deliver(event, "blackboard-product-direction")
        product.assert_called_once_with(event, artifact_store=None)
        blackboard.assert_called_once_with(event, artifact_store=None)

    def test_rejects_untrusted_or_unknown_delivery(self):
        boundary = TrustedDjangoProjectionBoundary()
        with self.assertRaises(ValueError):
            boundary.deliver(trusted_event().to_dict(), "product-direction")
        with self.assertRaises(ValueError):
            boundary.deliver(trusted_event(), "unknown-consumer")
