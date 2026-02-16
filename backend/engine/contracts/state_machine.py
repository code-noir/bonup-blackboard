ALLOWED_TRANSITIONS = {
    "draft": ["sent", "archived"],
    "sent": ["negotiating", "signed", "rejected", "archived"],
    "negotiating": ["superseded", "archived"],
    "signed": ["archived"],
    "rejected": ["archived"],
    "superseded": [],
    "archived": [],
}


def validate_transition(current_status, new_status):
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, []):
        raise ValueError(
            f"Illegal transition from '{current_status}' to '{new_status}'"
        )


