import re
from decimal import Decimal, InvalidOperation


def to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def extract_amounts(text):
    amounts = []
    pattern = r"(?P<currency>\$|USD\s*)\s*(?P<amount>[0-9][0-9,]*(?:\.[0-9]{2})?)"
    for match in re.finditer(pattern, text or "", re.IGNORECASE):
        amounts.append({
            "raw": match.group(0).strip(),
            "amount": match.group("amount").replace(",", ""),
            "currency": "USD" if match.group("currency").strip().upper().startswith("USD") or match.group("currency") == "$" else match.group("currency").strip(),
        })
    return amounts


def money_title_amount(amount_info):
    raw = amount_info.get("raw") or ""
    if raw.startswith("$"):
        return raw
    amount = amount_info.get("amount") or ""
    if not amount:
        return raw
    whole, dot, cents = amount.partition(".")
    try:
        whole = f"{int(whole):,}"
    except ValueError:
        pass
    return f"${whole}{dot}{cents}"
