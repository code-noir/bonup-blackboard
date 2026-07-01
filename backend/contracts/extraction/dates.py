import re
from datetime import datetime, time, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date

MONTH_NAME_RE = re.compile(
    r"\b(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+"
    r"(?P<day>\d{1,2}),\s*(?P<year>20\d{2})\b",
    re.IGNORECASE,
)

MONTH_NUMBERS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _date_from_month_match(match):
    month_key = match.group("month").lower().rstrip(".")
    month = MONTH_NUMBERS.get(month_key)
    if not month:
        return None
    try:
        return datetime(int(match.group("year")), month, int(match.group("day"))).date()
    except ValueError:
        return None


def fixed_due_dates(text):
    dates = []
    for iso in re.finditer(r"\b(20[0-9]{2}-[01][0-9]-[0-3][0-9])\b", text or ""):
        parsed = parse_date(iso.group(1))
        if parsed:
            dates.append(parsed)
    for match in MONTH_NAME_RE.finditer(text or ""):
        parsed = _date_from_month_match(match)
        if parsed:
            dates.append(parsed)
    return dates


def fixed_due_date(text):
    dates = fixed_due_dates(text)
    return dates[0] if dates else None


def as_aware_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    return timezone.make_aware(datetime.combine(value, time.min))


def due_datetime(raw_due, contract):
    if raw_due:
        parsed = parse_date(str(raw_due))
        if parsed:
            return as_aware_datetime(parsed)
        relative = re.search(r"within\s+([0-9]+)\s+(day|days|week|weeks|month|months)", str(raw_due), re.IGNORECASE)
        if relative:
            quantity = int(relative.group(1))
            unit = relative.group(2).lower()
            if unit.startswith("week"):
                quantity *= 7
            elif unit.startswith("month"):
                quantity *= 30
            return timezone.now() + timedelta(days=quantity)
    if contract.end_date:
        return as_aware_datetime(contract.end_date)
    return None
