#backend/api/contracts/services/proof_of_work_service.py


from backend.contracts.models import (
    ContractObligation,
    ContractServiceObligation,
)


class ProofOfWorkService:
    """
    Builds a structured proof-of-work payload from obligation execution data.

    This returns a cleaner proof document shape that is easier to:
    - expose through API
    - transform into PBVD
    - render in UI
    - export later
    """

    def build_for_obligation(self, *, obligation_type, obligation_id):
        if obligation_type == "payment":
            obligation = ContractObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all().order_by("started_at")

            session_payloads = [self._serialize_session(session) for session in sessions]
            all_events = self._flatten_events(session_payloads)

            return {
                "proof_type": "proof_of_work",
                "obligation_summary": {
                    "obligation_id": str(obligation.id),
                    "obligation_type": "payment",
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
                "value_adjustments": self._extract_value_adjustments(all_events),
                "timeline": all_events,
                "sessions": session_payloads,
            }

        if obligation_type == "service":
            obligation = ContractServiceObligation.objects.get(id=obligation_id)
            sessions = obligation.execution_sessions.all().order_by("started_at")

            session_payloads = [self._serialize_session(session) for session in sessions]
            all_events = self._flatten_events(session_payloads)

            return {
                "proof_type": "proof_of_work",
                "obligation_summary": {
                    "obligation_id": str(obligation.id),
                    "obligation_type": "service",
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
                "value_adjustments": self._extract_value_adjustments(all_events),
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

    def _extract_value_adjustments(self, events):
        adjustments = []

        for event in events:
            metadata = event.get("metadata") or {}

            billing_mode = metadata.get("billing_mode")
            estimated_cost_amount = event.get("estimated_cost_amount")
            estimated_cost_currency = event.get("estimated_cost_currency")

            if billing_mode == "separate_charge" and estimated_cost_amount:
                adjustments.append({
                    "event_id": event["event_id"],
                    "session_id": event["session_id"],
                    "adjustment_type": "additional_charge",
                    "amount": estimated_cost_amount,
                    "currency": estimated_cost_currency,
                    "summary": event.get("summary"),
                    "created_at": event.get("created_at"),
                })

        return adjustments


