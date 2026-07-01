import re


def relative_due_rule(text):
    match = re.search(
        r"\bwithin\s+(?P<amount>\d+)\s+(?P<unit>day|days|week|weeks|month|months)"
        r"(?:\s+(?P<direction>after|before)\s+(?P<event>[^.]+?))?(?:\.|$)",
        text or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    event = (match.group("event") or "").strip()
    lowered = (text or "").lower()
    if event.lower() == "discovering it" and "damage" in lowered:
        event = "discovering damage"
    if not event and "delivery" in lowered:
        event = "delivery"
    return {
        "amount": int(match.group("amount")),
        "unit": match.group("unit").lower().rstrip("s") + "s",
        "direction": (match.group("direction") or "after").lower(),
        "event": event,
    }


def due_trigger(text):
    match = re.search(r"\bwhen\s+(?P<trigger>[^.]+?)(?:\.|$)", text or "", re.IGNORECASE)
    if not match:
        return ""
    return f"when {match.group('trigger').strip()}"


def before_trigger(text):
    match = re.search(r"\bbefore\s+(?P<trigger>[^.]+?)(?:\.|$)", text or "", re.IGNORECASE)
    if not match:
        return ""
    return f"before {match.group('trigger').strip()}"


def monthly_rent_recurrence(text, amount):
    lowered = (text or "").lower()
    if "per month" not in lowered and "each month" not in lowered and "monthly" not in lowered:
        return {}
    recurrence = {"frequency": "monthly", "amount": str(amount) if amount is not None else "", "unit": "month"}
    due_day = re.search(r"due on the (?P<day>\d{1,2})(?:st|nd|rd|th)? day of each month", text or "", re.IGNORECASE)
    if due_day:
        recurrence["due_day"] = int(due_day.group("day"))
    return recurrence


def due_rule(text):
    match = re.search(r"\bdue on the [^.]+", text or "", re.IGNORECASE)
    return match.group(0).strip() if match else ""


def after_trigger(text):
    match = re.search(r"\bafter\s+(?P<trigger>[^.]+?)(?:\.|$)", text or "", re.IGNORECASE)
    if not match:
        return ""
    return f"after {match.group('trigger').strip()}"
