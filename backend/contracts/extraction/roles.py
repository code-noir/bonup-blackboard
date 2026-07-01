import re


ROLE_ALIASES = {
    "general contractor": "general_contractor",
    "subcontractor": "subcontractor",
    "client": "client",
    "contractor": "contractor",
    "landlord": "landlord",
    "tenant": "tenant",
    "owner": "owner",
    "renter": "renter",
    "borrower": "borrower",
    "lender": "lender",
    "buyer": "buyer",
    "seller": "seller",
    "employer": "employer",
    "employee": "employee",
    "worker": "worker",
    "vendor": "vendor",
    "customer": "customer",
    "provider": "provider",
    "recipient": "recipient",
}

ROLE_LABELS_BY_KEY = {key: label.title() for label, key in ROLE_ALIASES.items()}
ROLE_PATTERN = "|".join(re.escape(label) for label in sorted(ROLE_ALIASES, key=len, reverse=True))

ROLE_COUNTERPARTS = {
    "client": "contractor",
    "contractor": "client",
    "landlord": "tenant",
    "tenant": "landlord",
    "general_contractor": "subcontractor",
    "subcontractor": "general_contractor",
    "owner": "renter",
    "renter": "owner",
    "borrower": "lender",
    "lender": "borrower",
    "buyer": "seller",
    "seller": "buyer",
    "employer": "employee",
    "employee": "employer",
    "worker": "employer",
    "vendor": "customer",
    "customer": "vendor",
    "provider": "recipient",
    "recipient": "provider",
}


def format_party(label, name):
    label = (label or "").strip()
    name = (name or "").strip()
    if label and name:
        return f"{label} / {name}"
    return label or name


def _contract_fallback_party(contract, role_key):
    if role_key == "client" and contract.initiator:
        return format_party("Client", str(contract.initiator))
    if role_key == "contractor" and (contract.counterparty_name or contract.counterparty_email):
        return format_party("Contractor", contract.counterparty_name or contract.counterparty_email)
    return ""


def parse_roles(source_text, contract):
    roles = {}
    pattern = rf"^\s*(?P<label>{ROLE_PATTERN})\s*:\s*(?P<name>[^\n]+?)\s*$"
    for match in re.finditer(pattern, source_text or "", re.IGNORECASE | re.MULTILINE):
        raw_label = match.group("label").strip().lower()
        key = ROLE_ALIASES[raw_label]
        label = ROLE_LABELS_BY_KEY[key]
        name = match.group("name").strip().rstrip(".")
        roles[key] = {"key": key, "label": label, "name": name, "display": format_party(label, name)}
    return roles


def role_display(roles, role, fallback=""):
    return party_for_role(roles, role, fallback)


def party_for_role(roles, role_key, fallback=""):
    key = ROLE_ALIASES.get((role_key or "").replace("_", " ").lower(), role_key)
    value = roles.get(key)
    if value:
        return value["display"]
    return fallback


def has_explicit_roles(roles):
    return bool(roles)


def _mentioned_role_keys(sentence):
    mentioned = []
    for match in re.finditer(rf"\b(?P<label>{ROLE_PATTERN})\b", sentence or "", re.IGNORECASE):
        key = ROLE_ALIASES[match.group("label").strip().lower()]
        if key not in mentioned:
            mentioned.append(key)
    return mentioned


def _party_for_role_or_contract(roles, role_key, contract):
    return party_for_role(roles, role_key, _contract_fallback_party(contract, role_key))


def _explicit_pair_for_role(roles, role_key):
    responsible = party_for_role(roles, role_key)
    beneficiary = party_for_role(roles, ROLE_COUNTERPARTS.get(role_key))
    if responsible and beneficiary:
        return responsible, beneficiary
    return "", ""


def payment_parties_for_sentence(sentence, roles, contract):
    pay_pattern = rf"\b(?P<payer>{ROLE_PATTERN})\b\s+(?:agrees\s+to\s+|must\s+|shall\s+)?pays?\s+\b(?P<payee>{ROLE_PATTERN})\b"
    match = re.search(pay_pattern, sentence or "", re.IGNORECASE)
    if match:
        payer_key = ROLE_ALIASES[match.group("payer").strip().lower()]
        payee_key = ROLE_ALIASES[match.group("payee").strip().lower()]
        if has_explicit_roles(roles):
            return party_for_role(roles, payer_key), party_for_role(roles, payee_key)
        payer = _party_for_role_or_contract(roles, payer_key, contract)
        payee = _party_for_role_or_contract(roles, payee_key, contract)
        if payer or payee:
            return payer, payee
    return "", ""


def parties_for_sentence(sentence, candidate_type, roles, contract, candidate_model):
    lowered = sentence.lower()
    if "change order" in lowered and "both parties" in lowered:
        return "both parties", "both parties"

    payment_parties = payment_parties_for_sentence(sentence, roles, contract)
    if payment_parties != ("", ""):
        return payment_parties

    mentioned = _mentioned_role_keys(sentence)
    if has_explicit_roles(roles):
        for role_key in mentioned:
            parties = _explicit_pair_for_role(roles, role_key)
            if parties != ("", ""):
                return parties

    client = _party_for_role_or_contract(roles, "client", contract)
    contractor = _party_for_role_or_contract(roles, "contractor", contract)

    if candidate_type in {candidate_model.TYPE_PAYMENT, candidate_model.TYPE_DEPOSIT}:
        if not has_explicit_roles(roles) or ("client" in roles and "contractor" in roles):
            return client or "payer/client", contractor
        return "", ""
    if candidate_type == candidate_model.TYPE_RESPONSIBILITY:
        if "client" in lowered:
            return client, contractor
        if not has_explicit_roles(roles):
            return "", ""
        if "client" in roles and "contractor" in roles:
            return client, contractor
        return "", ""
    if candidate_type == candidate_model.TYPE_SERVICE_WORK:
        if "contractor" in lowered or ("client" in roles and "contractor" in roles):
            return contractor, client
        if has_explicit_roles(roles):
            return "", ""
        return contractor or "service provider", client
    return "", ""
