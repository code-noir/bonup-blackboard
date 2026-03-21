







# backend/api/contracts/services/proof_of_work_service.py

from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
)
from backend.engine.lifecycle_core.execution.adjustments import (
    ExecutionAdjustmentBuilder,
)
from backend.engine.lifecycle_core.obligations.primitives import ServiceObligation
from backend.api.contracts.services.contract_mode_service import ContractModeService
from backend.infrastructure.repositories.contract_value_adjustment_repository import (
    ContractValueAdjustmentRepository,
)
from backend.infrastructure.repositories.contract_approval_repository import (
    ContractApprovalRepository,
)
from backend.infrastructure.repositories.contract_obligation_promotion_repository import (
    ContractObligationPromotionRepository,
)


class ProofOfWorkService:
    """
    Builds a structured proof-of-work payload from obligation execution data.
    """

    def __init__(self):
        self.adjustment_builder = ExecutionAdjustmentBuilder()
        self.contract_mode_service = ContractModeService()
        self.adjustment_repo = ContractValueAdjustmentRepository()
        self.approval_repo = ContractApprovalRepository()
        self.promotion_repo = ContractObligationPromotionRepository()

    def build_for_obligation(
        self,
        *,
        obligation_type,
        obligation_id,
        lateness_base_amount=None,
        lateness_currency="USD",
        lateness_adjustment_enabled=False,
        lateness_adjustment_mode=None,
        lateness_adjustment_value=None,
    ):
        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all().order_by("started_at")

            session_payloads = [self._serialize_session(session) for session in sessions]
            all_events = self._flatten_events(session_payloads)
            contract_mode = self.contract_mode_service.derive_mode(
                contract_id=obligation.contract_id
            )

            value_adjustments = self._get_stored_payment_adjustments(obligation)
            approval_requests = self._get_payment_approvals(obligation)

            return {
                "proof_type": "proof_of_work",
                "contract_mode": contract_mode,
                "obligation_summary": {
                    "obligation_id": str(obligation.id),
                    "obligation_type": "payment",
                    "contract_id": str(obligation.contract_id),
                    "obligor_id": obligation.obligor_id,
                    "obligee_id": obligation.obligee_id,
                    "state": obligation.state,
                    "due_date": obligation.due_date,
                    "base_amount_due": str(obligation.amount_due),
                    "base_amount_paid": str(obligation.amount_paid),
                },
                "execution_summary": {
                    "session_count": len(session_payloads),
                    "event_count": len(all_events),
                },
                "observations": self._extract_observations(all_events),
                "decisions": self._extract_decisions(all_events),
                "approval_requests": approval_requests,
                "value_adjustments": value_adjustments,
                "promotions": [],
                "promoted_side_obligations": [],
                "timeline": all_events,
                "sessions": session_payloads,
            }

        if obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all().order_by("started_at")

            session_payloads = [self._serialize_session(session) for session in sessions]
            all_events = self._flatten_events(session_payloads)
            contract_mode = self.contract_mode_service.derive_mode(
                contract_id=obligation.contract_id
            )

            self._ensure_service_lateness_adjustment_if_requested(
                obligation=obligation,
                lateness_base_amount=lateness_base_amount,
                lateness_currency=lateness_currency,
                lateness_adjustment_enabled=lateness_adjustment_enabled,
                lateness_adjustment_mode=lateness_adjustment_mode,
                lateness_adjustment_value=lateness_adjustment_value,
            )

            value_adjustments = self._get_stored_service_adjustments(obligation)
            approval_requests = self._get_service_approvals(obligation)
            promotions = self._get_service_promotions(obligation)
            promoted_side_obligations = self._get_promoted_side_obligations(promotions)

            return {
                "proof_type": "proof_of_work",
                "contract_mode": contract_mode,
                "obligation_summary": {
                    "obligation_id": str(obligation.id),
                    "obligation_type": "service",
                    "contract_id": str(obligation.contract_id),
                    "obligor_id": obligation.obligor_id,
                    "obligee_id": obligation.obligee_id,
                    "state": obligation.state,
                    "due_date": obligation.due_date,
                    "description": obligation.description,
                },
                "execution_summary": {
                    "session_count": len(session_payloads),
                    "event_count": len(all_events),
                },
                "observations": self._extract_observations(all_events),
                "decisions": self._extract_decisions(all_events),
                "approval_requests": approval_requests,
                "value_adjustments": value_adjustments,
                "promotions": promotions,
                "promoted_side_obligations": promoted_side_obligations,
                "timeline": all_events,
                "sessions": session_payloads,
            }

        raise Exception("Invalid obligation type")

    def _serialize_session(self, session):
        events = [
            self._serialize_event(event)
            for event in session.events.all().order_by("created_at")
        ]

        return {
            "session_id": str(session.id),
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "events": events,
        }

    def _serialize_event(self, event):
        return {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "task": event.task,
            "observation": event.observation,
            "summary": event.summary,
            "estimated_duration_minutes": event.estimated_duration_minutes,
            "estimated_cost_amount": (
                str(event.estimated_cost_amount)
                if event.estimated_cost_amount is not None
                else None
            ),
            "estimated_cost_currency": event.estimated_cost_currency,
            "planned_execution_time": event.planned_execution_time,
            "metadata": event.metadata,
            "created_at": event.created_at,
        }

    def _flatten_events(self, session_payloads):
        all_events = []

        for session in session_payloads:
            for event in session["events"]:
                event_copy = dict(event)
                event_copy["session_id"] = session["session_id"]
                all_events.append(event_copy)

        all_events.sort(key=lambda e: e["created_at"])
        return all_events

    def _extract_observations(self, events):
        observations = []

        for event in events:
            if event.get("observation"):
                observations.append({
                    "event_id": event["event_id"],
                    "session_id": event["session_id"],
                    "task": event.get("task"),
                    "observation": event.get("observation"),
                    "summary": event.get("summary"),
                    "created_at": event.get("created_at"),
                })

        return observations

    def _extract_decisions(self, events):
        decisions = []

        for event in events:
            metadata = event.get("metadata") or {}

            if "decision_status" in metadata:
                decisions.append({
                    "event_id": event["event_id"],
                    "session_id": event["session_id"],
                    "decision_status": metadata.get("decision_status"),
                    "authorization_mode": metadata.get("authorization_mode"),
                    "billing_mode": metadata.get("billing_mode"),
                    "promotion_suggestion": metadata.get("promotion_suggestion"),
                    "required_next_step": metadata.get("required_next_step"),
                    "rationale": metadata.get("rationale"),
                    "proof_tags": metadata.get("proof_tags", []),
                    "created_at": event.get("created_at"),
                })

        return decisions

    def _get_stored_service_adjustments(self, obligation):
        queryset = self.adjustment_repo.list_for_service_obligation(obligation.id)
        return [self._serialize_adjustment(adj) for adj in queryset]

    def _get_stored_payment_adjustments(self, obligation):
        queryset = self.adjustment_repo.list_for_payment_obligation(obligation.id)
        return [self._serialize_adjustment(adj) for adj in queryset]

    def _serialize_adjustment(self, adjustment):
        return {
            "adjustment_id": str(adjustment.id),
            "event_id": str(adjustment.execution_event_id) if adjustment.execution_event_id else None,
            "session_id": (
                str(adjustment.execution_event.session_id)
                if adjustment.execution_event_id and adjustment.execution_event.session_id
                else None
            ),
            "adjustment_type": adjustment.adjustment_type,
            "mode": adjustment.mode,
            "amount": str(adjustment.amount),
            "currency": adjustment.currency,
            "summary": adjustment.summary,
            "created_at": adjustment.created_at,
        }

    def _get_service_approvals(self, obligation):
        approvals = self.approval_repo.list_for_service_obligation(obligation.id)
        return [self._serialize_approval(a) for a in approvals]

    def _get_payment_approvals(self, obligation):
        approvals = self.approval_repo.list_for_payment_obligation(obligation.id)
        return [self._serialize_approval(a) for a in approvals]

    def _serialize_approval(self, approval):
        return {
            "approval_id": str(approval.id),
            "approval_type": approval.approval_type,
            "status": approval.status,
            "summary": approval.summary,
            "metadata": approval.metadata,
            "requested_at": approval.requested_at,
            "decided_at": approval.decided_at,
            "execution_event_id": (
                str(approval.execution_event_id) if approval.execution_event_id else None
            ),
            "payment_obligation_id": (
                str(approval.payment_obligation_id) if approval.payment_obligation_id else None
            ),
            "service_obligation_id": (
                str(approval.service_obligation_id) if approval.service_obligation_id else None
            ),
        }

    def _get_service_promotions(self, obligation):
        promotions = self.promotion_repo.list_for_parent_service_obligation(obligation.id)
        return [self._serialize_promotion(p) for p in promotions]

    def _serialize_promotion(self, promotion):
        return {
            "promotion_id": str(promotion.id),
            "promotion_type": promotion.promotion_type,
            "summary": promotion.summary,
            "source_execution_event_id": str(promotion.source_execution_event_id),
            "parent_service_obligation_id": (
                str(promotion.parent_service_obligation_id)
                if promotion.parent_service_obligation_id
                else None
            ),
            "promoted_service_obligation_id": (
                str(promotion.promoted_service_obligation_id)
                if promotion.promoted_service_obligation_id
                else None
            ),
            "created_at": promotion.created_at,
        }

    def _get_promoted_side_obligations(self, promotions):
        results = []

        for promotion in promotions:
            promoted_id = promotion.get("promoted_service_obligation_id")
            if not promoted_id:
                continue

            obligation = ContractServiceObligation.objects.get(id=promoted_id)
            results.append({
                "obligation_id": str(obligation.id),
                "contract_id": str(obligation.contract_id),
                "description": obligation.description,
                "due_date": obligation.due_date,
                "state": obligation.state,
                "obligor_id": obligation.obligor_id,
                "obligee_id": obligation.obligee_id,
            })

        return results

    def _ensure_service_lateness_adjustment_if_requested(
        self,
        *,
        obligation,
        lateness_base_amount,
        lateness_currency,
        lateness_adjustment_enabled,
        lateness_adjustment_mode,
        lateness_adjustment_value,
    ):
        if not lateness_adjustment_enabled:
            return None

        if lateness_base_amount is None:
            return None

        existing = self.adjustment_repo.list_for_service_obligation(obligation.id).filter(
            adjustment_type="lateness_adjustment"
        ).first()

        if existing:
            return existing

        engine_obligation = ServiceObligation(
            obligor_id=obligation.obligor_id,
            obligee_id=obligation.obligee_id,
            description=obligation.description,
            due_date=obligation.due_date,
            state=obligation.state,
        )
        engine_obligation.completed_at = obligation.completed_at

        adjustment = self.adjustment_builder.build_lateness_adjustment(
            obligation=engine_obligation,
            base_amount=lateness_base_amount,
            currency=lateness_currency,
            adjustment_enabled=lateness_adjustment_enabled,
            adjustment_mode=lateness_adjustment_mode,
            adjustment_value=lateness_adjustment_value,
        )

        if adjustment is None:
            return None

        return self.adjustment_repo.create(
            contract=obligation.contract,
            service_obligation=obligation,
            adjustment_type=adjustment.adjustment_type,
            mode=adjustment.mode,
            amount=adjustment.amount,
            currency=adjustment.currency,
            summary=adjustment.summary,
        )











