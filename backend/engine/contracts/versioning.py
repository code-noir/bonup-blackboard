# backend/engine/contracts/versioning.py
from .exceptions import NegotiationLimitReached


def calculate_next_version(current_count, max_versions):
    if current_count >= max_versions:
        raise NegotiationLimitReached("Negotiation limit reached.")

    return current_count + 1

