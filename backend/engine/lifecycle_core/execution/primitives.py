#backend/engine/lifecycle_core/execution/primitives.py

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional


# ============================================================
# EXECUTION ITEM
# ============================================================

@dataclass
class ExecutionItem:
    """
    A structured item discovered during execution.

    This is universal across bonUP verticals.
    It is not limited to physical labor.
    """

    task: str
    observation: str
    summary: str
    estimated_duration_minutes: int
    estimated_cost_amount: Decimal
    estimated_cost_currency: str
    planned_execution_time: Optional[datetime] = None

    def __post_init__(self):
        self.estimated_cost_amount = Decimal(self.estimated_cost_amount)

        if self.estimated_duration_minutes < 0:
            raise ValueError("estimated_duration_minutes cannot be negative")

        if not self.task:
            raise ValueError("task is required")

        if not self.observation:
            raise ValueError("observation is required")

        if not self.summary:
            raise ValueError("summary is required")

        if not self.estimated_cost_currency:
            raise ValueError("estimated_cost_currency is required")


# ============================================================
# EXECUTION DECISION
# ============================================================

@dataclass
class ExecutionDecision:
    """
    Output returned by the engine after evaluating an execution item.
    """

    decision_status: str
    authorization_mode: str
    billing_mode: str
    promotion_suggestion: str
    required_next_step: str
    rationale: str
    proof_tags: List[str] = field(default_factory=list)


# ============================================================
# EXECUTION EVENT
# ============================================================

@dataclass
class ExecutionEvent:
    """
    Recorded event during execution of an obligation.
    """

    event_type: str
    summary: str
    created_at: datetime
    session_id: Optional[str] = None
    obligation_id: Optional[str] = None
    item_task: Optional[str] = None
    item_observation: Optional[str] = None
    metadata: dict = field(default_factory=dict)


# ============================================================
# EXECUTION SESSION
# ============================================================

@dataclass
class ExecutionSession:
    """
    A real execution period under one obligation.

    One obligation may have multiple execution sessions.
    """

    obligation_id: str
    started_at: datetime
    status: str = "active"
    ended_at: Optional[datetime] = None
    events: List[ExecutionEvent] = field(default_factory=list)

    def add_event(self, event: ExecutionEvent):
        self.events.append(event)

    def close(self, ended_at: Optional[datetime] = None):
        self.ended_at = ended_at or datetime.utcnow()
        self.status = "closed"


# ============================================================
# VALUE ADJUSTMENT
# ============================================================

@dataclass
class ValueAdjustment:
    """
    Financial adjustment connected to execution outcome.

    Examples:
    - extra billable work
    - lateness discount
    """

    adjustment_type: str
    mode: str
    amount: Decimal
    currency: str
    summary: str

    def __post_init__(self):
        self.amount = Decimal(self.amount)