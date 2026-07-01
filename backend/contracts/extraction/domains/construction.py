import re


def construction_candidate_type(sentence, candidate_model):
    lowered = sentence.lower()
    if "retainage" in lowered and "withhold" in lowered:
        return candidate_model.TYPE_OTHER
    if "change order" in lowered and "approved in writing" in lowered:
        return candidate_model.TYPE_RESPONSIBILITY
    if "proof of insurance" in lowered:
        return candidate_model.TYPE_RESPONSIBILITY
    if "pay" in lowered or "$" in lowered:
        return ""
    if "subcontractor" in lowered and any(word in lowered for word in ["complete", "correct", "provide", "must"]):
        return candidate_model.TYPE_SERVICE_WORK
    return ""


def construction_title(sentence, candidate_type, amount_info, candidate_model):
    lowered = sentence.lower()
    amount = amount_info.get("raw") if amount_info else ""
    if "primer coat" in lowered and "must complete" in lowered:
        return "Complete primer coat work"
    if "final paint coat" in lowered and "must complete" in lowered:
        return "Complete final paint coat work"
    if candidate_type == candidate_model.TYPE_PAYMENT and "primer coat" in lowered and "inspection" in lowered:
        return f"Pay {amount} after primer coat inspection"
    if candidate_type == candidate_model.TYPE_PAYMENT and "final paint coat" in lowered and "approved" in lowered:
        return f"Pay {amount} after final paint completion and approval"
    if "retainage" in lowered and "punch-list" in lowered:
        return "Withhold 10% retainage until punch-list completion"
    if "correct punch-list" in lowered:
        return "Correct punch-list items after written notice"
    if "proof of insurance" in lowered:
        return "Provide proof of insurance before starting work"
    if "change order" in lowered and "approved in writing" in lowered:
        return "Approve change orders in writing before extra work"
    return ""


def construction_payment_trigger(sentence):
    lowered = sentence.lower()
    if "after" not in lowered:
        return ""
    match = re.search(r"\bafter\s+(?P<trigger>[^.]+?)(?:\.|$)", sentence or "", re.IGNORECASE)
    if not match:
        return ""
    trigger = match.group("trigger").strip()
    if "final paint coat work is completed and approved" in lowered:
        trigger = "final paint coat work completed and approved"
    return f"after {trigger}"


def construction_before_trigger(sentence):
    lowered = sentence.lower()
    if "proof of insurance" in lowered and "before starting work" in lowered:
        return "before starting work"
    if "change order" in lowered and "before extra work begins" in lowered:
        return "before extra work begins"
    return ""


def retainage_metadata(sentence):
    match = re.search(r"(?P<percent>\d+(?:\.\d+)?)\s*%\s+retainage", sentence or "", re.IGNORECASE)
    if not match:
        return {}
    percent = float(match.group("percent"))
    if percent.is_integer():
        percent = int(percent)
    metadata = {"retainage_percent": percent, "payment_kind": "retainage"}
    condition = re.search(r"\buntil\s+(?P<condition>[^.]+?)(?:\.|$)", sentence or "", re.IGNORECASE)
    if condition:
        metadata["condition"] = f"until {condition.group('condition').strip()}"
    return metadata


def change_order_metadata(sentence):
    lowered = sentence.lower()
    if "change order" not in lowered:
        return {}
    metadata = {"rule_type": "change_order_approval"}
    if "approved" in lowered:
        metadata["approval_required"] = True
    if "in writing" in lowered:
        metadata["approval_format"] = "writing"
    trigger = construction_before_trigger(sentence)
    if trigger:
        metadata["due_trigger"] = trigger
    return metadata
