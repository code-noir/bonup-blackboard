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
