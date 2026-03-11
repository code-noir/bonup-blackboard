# backend/engine/lifecycle_core/events/event_recorder.py

from backend.engine.lifecycle_core.events.lifecycle_event import LifecycleEvent


class EventRecorder:

    """
    Records lifecycle events for obligations.
    """

    @staticmethod
    def record_service_completed(instance, actor_id, note=None):

        event = LifecycleEvent(
            obligation_instance=instance,
            event_type=LifecycleEvent.EVENT_SERVICE_COMPLETED,
            actor_id=actor_id,
            description=note,
        )

        instance.mark_completed()

        return event


    @staticmethod
    def record_service_issue(instance, actor_id, description):

        event = LifecycleEvent(
            obligation_instance=instance,
            event_type=LifecycleEvent.EVENT_SERVICE_ISSUE,
            actor_id=actor_id,
            description=description,
        )

        return event


    @staticmethod
    def record_payment(instance, actor_id, amount):

        instance.apply_payment(amount)

        event = LifecycleEvent(
            obligation_instance=instance,
            event_type=LifecycleEvent.EVENT_PAYMENT_RECEIVED,
            actor_id=actor_id,
            description=f"Payment received: {amount}",
        )

        return event


    @staticmethod
    def record_note(instance, actor_id, note):

        event = LifecycleEvent(
            obligation_instance=instance,
            event_type=LifecycleEvent.EVENT_NOTE_ADDED,
            actor_id=actor_id,
            description=note,
        )

        return event



