# backend/engine/lifecycle_core/events/lifecycle_event.py


from django.utils import timezone


class LifecycleEvent:
    """
    Represents something that happened in the lifecycle
    of an obligation instance.
    """

    EVENT_SERVICE_COMPLETED = "service_completed"
    EVENT_SERVICE_ISSUE = "service_issue"

    EVENT_PAYMENT_RECEIVED = "payment_received"
    EVENT_PAYMENT_ADJUSTED = "payment_adjusted"

    EVENT_NOTE_ADDED = "note_added"

    def __init__(
        self,
        obligation_instance,
        event_type,
        actor_id,
        description=None,
        metadata=None,
    ):

        self.obligation_instance = obligation_instance

        self.event_type = event_type
        self.actor_id = actor_id

        self.description = description
        self.metadata = metadata or {}

        self.created_at = timezone.now()




