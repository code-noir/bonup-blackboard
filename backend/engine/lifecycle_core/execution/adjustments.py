#backend/engine/lifecycle_core/execution/adjustments.py

from decimal import Decimal

from backend.engine.lifecycle_core.execution.primitives import ValueAdjustment
from backend.engine.lifecycle_core.obligations.primitives import ServiceObligation


class ExecutionAdjustmentBuilder:
    """
    Builds execution-layer value adjustments from obligation outcomes.
    """

    def build_lateness_adjustment(
        self,
        *,
        obligation: ServiceObligation,
        base_amount,
        currency,
        adjustment_enabled,
        adjustment_mode=None,
        adjustment_value=None,
    ):
        """
        Build a one-time lateness ValueAdjustment for a completed service obligation.

        Returns:
        - ValueAdjustment if a lateness adjustment applies
        - None if no adjustment applies
        """

        adjustment_amount = obligation.calculate_lateness_adjustment(
            base_amount=base_amount,
            adjustment_enabled=adjustment_enabled,
            adjustment_mode=adjustment_mode,
            adjustment_value=adjustment_value,
        )

        if adjustment_amount <= Decimal("0.00"):
            return None

        if adjustment_mode == "fixed_amount":
            summary = (
                f"Late service adjustment applied as a fixed reduction of "
                f"{adjustment_amount} {currency}."
            )
        else:
            summary = (
                f"Late service adjustment applied as a percentage-based reduction of "
                f"{adjustment_amount} {currency}."
            )

        return ValueAdjustment(
            adjustment_type="lateness_adjustment",
            mode=adjustment_mode,
            amount=adjustment_amount,
            currency=currency,
            summary=summary,
        )







