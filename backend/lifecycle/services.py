from django.db import transaction

from backend.agreement_exchange.models import AgreementExchange
from backend.contracts.models import ContractVersion, LifecycleAgreement, LifecycleEvent


class LifecycleNotReadyError(Exception):
    pass


def find_signed_contract_version(contract):
    return resolve_lifecycle_ready_contract(contract)["signed_version"]


def find_source_exchange(contract, signed_version):
    return (
        AgreementExchange.objects
        .filter(
            current_contract_version=signed_version,
            status=AgreementExchange.STATUS_SIGNED,
        )
        .order_by("-updated_at", "-created_at")
        .first()
    )


def _contract_exchanges(contract):
    prefetched_exchanges = getattr(contract, "_prefetched_objects_cache", {}).get("agreement_exchanges")
    if prefetched_exchanges is not None:
        return sorted(prefetched_exchanges, key=lambda exchange: exchange.updated_at, reverse=True)
    return list(
        AgreementExchange.objects
        .filter(contract=contract)
        .select_related("current_contract_version", "current_contract_version__contract")
        .order_by("-updated_at", "-created_at")
    )


def resolve_lifecycle_ready_contract(contract):
    signed_version = (
        ContractVersion.objects
        .filter(contract=contract, status="signed")
        .order_by("-version_number", "-created_at")
        .select_related("contract")
        .first()
    )
    if signed_version is None:
        return {"contract": contract, "signed_version": None, "source_exchange": None}

    return {
        "contract": contract,
        "signed_version": signed_version,
        "source_exchange": find_source_exchange(contract, signed_version),
    }


def backfill_signed_exchange_versions(*, apply=False):
    exchanges = (
        AgreementExchange.objects
        .filter(status=AgreementExchange.STATUS_SIGNED)
        .exclude(current_contract_version__status="signed")
        .select_related("contract", "current_contract_version")
        .order_by("contract_id", "-updated_at", "-created_at")
    )
    repaired = []
    for exchange in exchanges:
        version = exchange.current_contract_version
        contract = version.contract
        repaired.append({
            "exchange_id": str(exchange.id),
            "contract_id": str(contract.id),
            "version_id": str(version.id),
            "version_status": version.status,
            "contract_status": contract.status,
        })
        if not apply:
            continue
        version.status = "signed"
        version.save(update_fields=["status"])
        if contract.status != "signed":
            contract.status = "signed"
            contract.save(update_fields=["status"])
    return repaired


def contract_is_lifecycle_ready(contract):
    return resolve_lifecycle_ready_contract(contract)["signed_version"] is not None


@transaction.atomic
def get_or_create_lifecycle_for_signed_contract(contract, user):
    locked_contract = contract.__class__.objects.select_for_update().get(pk=contract.pk)
    lifecycle_target = resolve_lifecycle_ready_contract(locked_contract)
    signed_version = lifecycle_target["signed_version"]
    if signed_version is None:
        raise LifecycleNotReadyError("Lifecycle is available only after the contract has a signed version.")

    lifecycle_contract = locked_contract
    source_exchange = lifecycle_target["source_exchange"]
    agreement, created = LifecycleAgreement.objects.get_or_create(
        contract=lifecycle_contract,
        defaults={
            "signed_version": signed_version,
            "source_exchange": source_exchange,
            "owner": user if getattr(user, "is_authenticated", False) else locked_contract.initiator,
            "status": LifecycleAgreement.STATUS_SETUP,
            "metadata": {"source": "signed_contract"},
        },
    )

    if created:
        LifecycleEvent.objects.create(
            lifecycle_agreement=agreement,
            event_type="timeline_setup_started",
            title="Timeline setup started",
            description="Agreement Timeline setup was opened for the signed contract.",
            metadata={
                "contract_id": str(lifecycle_contract.id),
                "signed_version_id": str(signed_version.id),
                "source_exchange_id": str(source_exchange.id) if source_exchange else None,
            },
        )

    return agreement
