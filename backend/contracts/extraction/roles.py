import re


def parse_roles(source_text, contract):
    roles = {}
    pattern = r"^\s*(?P<label>general contractor|subcontractor|client|contractor|customer|provider|owner|landlord|tenant)\s*:\s*(?P<name>[^\n]+?)\s*$"
    for match in re.finditer(pattern, source_text or "", re.IGNORECASE | re.MULTILINE):
        label = match.group("label").strip().title()
        name = match.group("name").strip().rstrip(".")
        roles[label.lower()] = {"label": label, "name": name, "display": f"{label} / {name}"}

    if "client" not in roles and contract.initiator:
        roles["client"] = {"label": "Client", "name": str(contract.initiator), "display": f"Client / {contract.initiator}"}
    if "contractor" not in roles and (contract.counterparty_name or contract.counterparty_email):
        name = contract.counterparty_name or contract.counterparty_email
        roles["contractor"] = {"label": "Contractor", "name": name, "display": f"Contractor / {name}"}
    return roles


def role_display(roles, role, fallback=""):
    value = roles.get(role)
    if value:
        return value["display"]
    return fallback


def parties_for_sentence(sentence, candidate_type, roles, contract, candidate_model):
    lowered = sentence.lower()
    client = role_display(roles, "client", str(contract.initiator) if contract.initiator else "")
    contractor = role_display(roles, "contractor", contract.counterparty_name or contract.counterparty_email or "")
    landlord = role_display(roles, "landlord", "")
    tenant = role_display(roles, "tenant", "")
    general_contractor = role_display(roles, "general contractor", "")
    subcontractor = role_display(roles, "subcontractor", "")

    if "general contractor" in lowered and candidate_type in {candidate_model.TYPE_PAYMENT, candidate_model.TYPE_OTHER, candidate_model.TYPE_RESPONSIBILITY}:
        return general_contractor or client, subcontractor or contractor
    if "subcontractor" in lowered and candidate_type in {candidate_model.TYPE_SERVICE_WORK, candidate_model.TYPE_RESPONSIBILITY}:
        return subcontractor or contractor, general_contractor or client
    if "change order" in lowered and "both parties" in lowered:
        return "both parties", "both parties"
    if "tenant" in lowered and candidate_type in {candidate_model.TYPE_PAYMENT, candidate_model.TYPE_DEPOSIT, candidate_model.TYPE_RESPONSIBILITY}:
        return tenant or client, landlord or contractor
    if "landlord" in lowered and candidate_type in {candidate_model.TYPE_SERVICE_WORK, candidate_model.TYPE_RESPONSIBILITY}:
        return landlord or contractor, tenant or client
    if candidate_type == candidate_model.TYPE_PAYMENT:
        return client or "payer/client", contractor
    if candidate_type == candidate_model.TYPE_DEPOSIT:
        return client or "payer/client", contractor
    if candidate_type == candidate_model.TYPE_RESPONSIBILITY:
        if "client" in lowered:
            return client, contractor
        return "", ""
    if candidate_type == candidate_model.TYPE_SERVICE_WORK:
        if "contractor" in lowered:
            return contractor, client
        return contractor or "service provider", client
    return "", ""
