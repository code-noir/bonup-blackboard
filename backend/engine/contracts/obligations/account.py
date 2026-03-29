from django.utils import timezone

from .lifecycle import process_obligation_lifecycle


def aggregate_account_state(instances):
    """
    Aggregates overall account state based on obligation instances.

    Rules:
    - If no instances → active
    - If all resolved → resolved
    - If any defaulted → defaulted
    - If any overdue → overdue
    - Otherwise → active
    """

    if not instances:
        return "active"

    total = len(instances)
    resolved_count = 0
    overdue_found = False
    default_found = False

    # Account owns the concept of "now"
    current_time = timezone.now()

    for instance in instances:
        state = process_obligation_lifecycle(
            instance,
            current_time=current_time,
        )

        if state == "resolved":
            resolved_count += 1

        if state == "overdue":
            overdue_found = True

        if state == "defaulted":
            default_found = True

    # Full resolution
    if resolved_count == total:
        return "resolved"

    # Any default → account default
    if default_found:
        return "defaulted"

    # Any overdue → account overdue
    if overdue_found:
        return "overdue"

    return "active"







    