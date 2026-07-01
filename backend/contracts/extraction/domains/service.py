import re


def object_from_text(text):
    lowered = (text or "").lower()
    object_patterns = [
        ("homepage mockup", "homepage mockup"),
        ("full website", "full website"),
        ("five-page business website", "five-page business website"),
        ("reasonable bugs", "reasonable bugs"),
        ("each delivery", "each delivery"),
        ("loan funds", "loan funds"),
        ("working keys and access", "working keys and access"),
        ("essential utilities", "essential utilities"),
        ("personal belongings", "personal belongings"),
    ]
    for key, value in object_patterns:
        if key in lowered:
            return value
    deliver = re.search(r"\bdeliver\s+(?:the\s+)?(?P<object>.+?)(?:\s+by\s+|\s+within\s+|\.|$)", text or "", re.IGNORECASE)
    if deliver:
        return deliver.group("object").strip()
    pay_for = re.search(r"\bfor\s+(?:the\s+)?(?P<object>.+?)(?:\s+when\s+|\.|$)", text or "", re.IGNORECASE)
    if pay_for:
        return pay_for.group("object").strip()
    return ""


def service_title(sentence):
    lowered = sentence.lower()
    obj = object_from_text(sentence)
    if re.search(r"\bdeliver\b", lowered) and obj:
        return f"Deliver {obj}"
    if "fix" in lowered and "bug" in lowered:
        return "Fix reasonable bugs after delivery"
    if "review" in lowered and "delivery" in lowered:
        return "Review each delivery"
    if "provide" in lowered and obj:
        return f"Provide {obj}"
    if "design" in lowered and obj:
        return f"Design {obj}"
    return ""


def service_candidate_type(sentence, candidate_model):
    lowered = sentence.lower()
    if "client" in lowered and "review" in lowered:
        return candidate_model.TYPE_RESPONSIBILITY
    if "contractor" in lowered and any(word in lowered for word in ["deliver", "fix", "provide", "perform", "must"]):
        return candidate_model.TYPE_SERVICE_WORK
    if any(word in lowered for word in ["deliver", "fix", "provide", "perform"]):
        return candidate_model.TYPE_SERVICE_WORK
    return ""
