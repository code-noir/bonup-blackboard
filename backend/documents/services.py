"""Explicit reference mutation boundaries; no storage/provider work under locks."""
from django.core.exceptions import PermissionDenied
from django.db import models, transaction

from backend.api.contracts.permissions import is_party
from backend.contracts.models import Contract
from backend.documents.models import ContractDocument
from backend.uploads.models import Upload
from backend.uploads.retention import lock_eligible_upload, lock_uploads, reconcile_removed_accesses


def _require_party(user, contract, *, initiator_only=False):
    if not is_party(user, contract) or (initiator_only and contract.initiator_id != user.pk):
        raise PermissionDenied("Contract access denied.")


@transaction.atomic
def attach_upload(user, contract_id, upload_id, *, title, description="", is_proof=False):
    contract = Contract.objects.select_for_update().get(pk=contract_id)
    _require_party(user, contract)
    upload, _ = lock_eligible_upload(user, upload_id)
    return ContractDocument.objects.create(
        contract=contract, upload=upload, attached_by=user,
        title=title, description=description, is_proof=is_proof,
    )


@transaction.atomic
def detach_document(user, contract_id, document_id):
    contract = Contract.objects.select_for_update().get(pk=contract_id)
    _require_party(user, contract)
    document = ContractDocument.objects.get(pk=document_id, contract=contract)
    _, accesses = lock_uploads([document.upload_id])
    document.delete()
    reconcile_removed_accesses(accesses)


@transaction.atomic
def delete_contracts(contract_ids, *, actor=None, initiator_only=False):
    """Known contract API/admin cascades. actor=None is for authorized Django admin.

    All parent and file rows are locked before any deletion, including Uploads
    whose related_contract FK will be SET_NULL by Django's collector. Arbitrary
    ORM/account-wide cascades are deliberately not intercepted by signals.
    """
    contracts = list(Contract.objects.select_for_update().filter(pk__in=contract_ids).order_by("pk"))
    if actor is not None:
        for contract in contracts:
            _require_party(actor, contract, initiator_only=initiator_only)
    ids = [c.pk for c in contracts]
    upload_ids = list(Upload.objects.filter(
        models.Q(contract_documents__contract_id__in=ids) | models.Q(related_contract_id__in=ids),
    ).values_list("pk", flat=True).distinct())
    _, accesses = lock_uploads(upload_ids)
    result = Contract.objects.filter(pk__in=ids).delete()
    reconcile_removed_accesses(accesses)
    return result
