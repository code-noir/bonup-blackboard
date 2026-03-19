from backend.engine.lifecycle_core.execution.primitives import (
    ExecutionItem,
    ExecutionDecision,
)


class ExecutionEvaluator:
    """
    First-pass evaluator for execution items.

    This is the starting point for the new execution layer.
    It evaluates one execution item and returns a structured decision.

    Current MVP rules:
    - low effort + low cost -> keep as event
    - high effort or high cost -> suggest side obligation
    - billing defaults to approval_required for now
    - no contract-specific or vertical-specific rule matrix yet
    """

    SIDE_OBLIGATION_DURATION_THRESHOLD_MINUTES = 120
    SIDE_OBLIGATION_COST_THRESHOLD = 150

    def evaluate(self, item: ExecutionItem) -> ExecutionDecision:
        promotion_suggestion = self._get_promotion_suggestion(item)

        return ExecutionDecision(
            decision_status="approval_required",
            authorization_mode="approval_required",
            billing_mode="separate_charge",
            promotion_suggestion=promotion_suggestion,
            required_next_step="request_customer_approval",
            rationale=self._build_rationale(item, promotion_suggestion),
            proof_tags=self._build_proof_tags(item, promotion_suggestion),
        )

    def _get_promotion_suggestion(self, item: ExecutionItem) -> str:
        if (
            item.estimated_duration_minutes >= self.SIDE_OBLIGATION_DURATION_THRESHOLD_MINUTES
            or item.estimated_cost_amount >= self.SIDE_OBLIGATION_COST_THRESHOLD
        ):
            return "suggest_side_obligation"

        return "keep_as_event"

    def _build_rationale(self, item: ExecutionItem, promotion_suggestion: str) -> str:
        if promotion_suggestion == "suggest_side_obligation":
            return (
                f"Execution item '{item.task}' exceeds the lightweight threshold "
                f"and may be better tracked as a side obligation."
            )

        return (
            f"Execution item '{item.task}' is small enough to remain an event "
            f"under the current obligation."
        )

    def _build_proof_tags(self, item: ExecutionItem, promotion_suggestion: str):
        tags = ["execution_item_detected", item.observation]

        if promotion_suggestion == "suggest_side_obligation":
            tags.append("promotion_suggested")
        else:
            tags.append("kept_as_event")

        return tags