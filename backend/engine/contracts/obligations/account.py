from .lifecycle import process_obligation_lifecycle


def evaluate_account_state(instances):
    """
    Determines overall account-level state based on obligation instances.
    """

    if not instances:
        return "active"

    total = len(instances)
    resolved_count = 0
    overdue_found = False
    default_found = False

    for instance in instances:
        state = process_obligation_lifecycle(instance)

        if state == "resolved":
            resolved_count += 1

        if state == "overdue":
            overdue_found = True

        if state == "defaulted":
            default_found = True

    # Full resolution
    if resolved_count == total:
        return "resolved"

    # Any default = account default
    if default_found:
        return "defaulted"

    # Any overdue = account overdue
    if overdue_found:
        return "overdue"

    return "active"





    