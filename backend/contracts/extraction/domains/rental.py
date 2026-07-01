def rental_title(sentence, candidate_type, candidate_model):
    lowered = sentence.lower()
    if "rental term begins" in lowered or "term begins" in lowered:
        return "Rental term begins"
    if "rental term ends" in lowered or "term ends" in lowered:
        return "Rental term ends"
    if candidate_type == candidate_model.TYPE_DEPOSIT:
        return "Pay security deposit"
    if candidate_type == candidate_model.TYPE_PAYMENT and ("per month" in lowered or "each month" in lowered or ("rent" in lowered and "monthly" in lowered)):
        return "Pay monthly rent"
    if "provide" in lowered and "keys" in lowered and "access" in lowered:
        return "Provide keys and bedroom access"
    if "keep" in lowered and "bedroom clean" in lowered and "report damage" in lowered:
        return "Keep bedroom clean and report damage"
    if "repair" in lowered and "essential utilities" in lowered:
        return "Repair essential utilities after written notice"
    if "return" in lowered and "keys" in lowered and "belongings" in lowered:
        return "Return keys and remove belongings"
    return ""


def rental_candidate_type(sentence, candidate_model):
    lowered = sentence.lower()
    if "security deposit" in lowered:
        return candidate_model.TYPE_DEPOSIT
    if "tenant" in lowered and any(word in lowered for word in ["keep", "report", "return", "remove", "must"]):
        return candidate_model.TYPE_RESPONSIBILITY
    if "landlord" in lowered and any(word in lowered for word in ["provide", "repair", "must"]):
        return candidate_model.TYPE_SERVICE_WORK
    return ""


def is_rental_term(sentence):
    lowered = sentence.lower()
    return "rental term" in lowered and "begins" in lowered and "ends" in lowered
