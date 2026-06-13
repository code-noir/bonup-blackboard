from backend.agreement_exchange.models import AgreementExchange


COUNTERPARTY_VISIBLE_EXCHANGE_STATUSES = {
    AgreementExchange.STATUS_SENT,
    AgreementExchange.STATUS_VIEWED,
    AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
    AgreementExchange.STATUS_CHANGES_REQUESTED,
    AgreementExchange.STATUS_INITIATOR_REVIEW,
    AgreementExchange.STATUS_UPDATED_VERSION_SENT,
    AgreementExchange.STATUS_READY_TO_SIGN,
    AgreementExchange.STATUS_SIGNED,
    AgreementExchange.STATUS_REJECTED,
}


def normalize_email(value):
    return (value or "").strip().lower()


def is_exchange_visible_to_counterparty(exchange):
    return exchange.status in COUNTERPARTY_VISIBLE_EXCHANGE_STATUSES


def can_user_see_exchange(exchange, user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if exchange.initiator_id == user.id:
        return True
    user_email = normalize_email(getattr(user, "email", ""))
    counterparty_email = normalize_email(exchange.counterparty_email)
    is_counterparty = exchange.counterparty_user_id == user.id or (
        user_email and user_email == counterparty_email
    )
    return bool(is_counterparty and is_exchange_visible_to_counterparty(exchange))


def can_user_see_contract_on_dashboard(contract, user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if contract.initiator_id == user.id:
        return True

    user_email = normalize_email(getattr(user, "email", ""))
    contract_counterparty_email = normalize_email(contract.counterparty_email)
    if not user_email or user_email != contract_counterparty_email:
        return False

    prefetched_exchanges = getattr(contract, "_prefetched_objects_cache", {}).get("agreement_exchanges")
    if prefetched_exchanges is not None:
        return any(is_exchange_visible_to_counterparty(exchange) for exchange in prefetched_exchanges)

    return contract.agreement_exchanges.filter(
        status__in=COUNTERPARTY_VISIBLE_EXCHANGE_STATUSES,
    ).exists()


ACTIVE_EXCHANGE_STATUSES = {
    AgreementExchange.STATUS_SENT,
    AgreementExchange.STATUS_VIEWED,
    AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
    AgreementExchange.STATUS_CHANGES_REQUESTED,
    AgreementExchange.STATUS_INITIATOR_REVIEW,
    AgreementExchange.STATUS_UPDATED_VERSION_SENT,
    AgreementExchange.STATUS_READY_TO_SIGN,
}


def _contract_exchanges(contract):
    prefetched_exchanges = getattr(contract, "_prefetched_objects_cache", {}).get("agreement_exchanges")
    if prefetched_exchanges is not None:
        return sorted(prefetched_exchanges, key=lambda exchange: exchange.updated_at, reverse=True)
    return list(contract.agreement_exchanges.order_by("-updated_at", "-created_at"))


def _latest_current_version(contract):
    prefetched_versions = getattr(contract, "_prefetched_objects_cache", {}).get("versions")
    if prefetched_versions is not None:
        versions = sorted(prefetched_versions, key=lambda version: version.version_number, reverse=True)
        return next((version for version in versions if not version.superseded), versions[0] if versions else None)
    return contract.versions.filter(superseded=False).order_by("-version_number", "-created_at").first()


def resolve_contract_dashboard_status(contract):
    """
    Resolve the user-facing contract state used by dashboard/list surfaces.

    Uses Agreement Exchange first because that is the live negotiation path.
    Falls back to the latest current ContractVersion for older direct signing.
    """
    exchanges = _contract_exchanges(contract)
    latest_exchange = exchanges[0] if exchanges else None
    active_exchange = next((exchange for exchange in exchanges if exchange.status in ACTIVE_EXCHANGE_STATUSES), None)
    signed_exchange = next((exchange for exchange in exchanges if exchange.status == AgreementExchange.STATUS_SIGNED), None)
    rejected_exchange = next((exchange for exchange in exchanges if exchange.status == AgreementExchange.STATUS_REJECTED), None)
    latest_version = _latest_current_version(contract)
    signed_version_id = None

    if signed_exchange is not None:
        signed_version_id = signed_exchange.current_contract_version_id
    elif latest_version is not None and latest_version.status == "signed":
        signed_version_id = latest_version.id

    if signed_version_id:
        display_status = "signed"
        display_status_label = "Signed"
        lifecycle_ready = True
        primary_action = "open_lifecycle"
        primary_action_url = f"/lifecycle?contract={contract.id}"
        active_exchange_id = None
    elif active_exchange is not None:
        display_status = "under_negotiation"
        display_status_label = "Under Negotiation"
        lifecycle_ready = False
        primary_action = "open_negotiation"
        primary_action_url = f"/negotiation/{contract.id}"
        active_exchange_id = active_exchange.id
    elif rejected_exchange is not None and latest_exchange == rejected_exchange:
        display_status = "rejected"
        display_status_label = "Rejected"
        lifecycle_ready = False
        primary_action = "open_rejected_exchange"
        primary_action_url = f"/agreement-exchange/{rejected_exchange.id}"
        active_exchange_id = None
    else:
        display_status = "prepared"
        display_status_label = "Prepared"
        lifecycle_ready = False
        primary_action = "open_negotiation"
        primary_action_url = f"/negotiation/{contract.id}"
        active_exchange_id = None

    return {
        "display_status": display_status,
        "display_status_label": display_status_label,
        "active_exchange_id": str(active_exchange_id) if active_exchange_id else None,
        "latest_exchange_status": latest_exchange.status if latest_exchange else None,
        "signed_version_id": str(signed_version_id) if signed_version_id else None,
        "lifecycle_ready": lifecycle_ready,
        "primary_action": primary_action,
        "primary_action_url": primary_action_url,
    }
