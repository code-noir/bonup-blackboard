# backend/engine/lifecycle_core/lifecycle_manager.py

from django.utils import timezone


class LifecycleManager:

    """
    Core lifecycle processor.

    Evaluates obligation instances and updates
    their lifecycle state.
    """

    STATE_PENDING = "pending"
    STATE_ACTIVE = "active"
    STATE_DUE = "due"
    STATE_OVERDUE = "overdue"
    STATE_RESOLVED = "resolved"

    @staticmethod
    def evaluate_instance(instance, current_time=None):

        if current_time is None:
            current_time = timezone.now()

        # -------------------------
        # Already resolved
        # -------------------------

        if instance.state == LifecycleManager.STATE_RESOLVED:
            return instance.state

        # -------------------------
        # Check if completed
        # -------------------------

        if hasattr(instance, "amount_due") and instance.amount_due:

            if instance.amount_paid >= instance.amount_due:
                instance.state = LifecycleManager.STATE_RESOLVED
                return instance.state

        # -------------------------
        # Check overdue
        # -------------------------

        if instance.due_date and current_time > instance.due_date:

            if instance.state != LifecycleManager.STATE_RESOLVED:
                instance.state = LifecycleManager.STATE_OVERDUE
                return instance.state

        # -------------------------
        # Check active
        # -------------------------

        if instance.state == LifecycleManager.STATE_PENDING:
            instance.state = LifecycleManager.STATE_ACTIVE

        return instance.state


    @staticmethod
    def evaluate_contract_instances(instances):

        """
        Evaluate all obligations belonging to a contract.
        """

        now = timezone.now()

        for instance in instances:
            LifecycleManager.evaluate_instance(instance, now)

        return instances


