"""Short database-only transactions for customer removal and file references.

Lock order: Contract (when applicable), all Uploads by PK, then all relevant
UserObjectAccess rows by (user_id, stored_object_id). Never lock a Contract
from here. Physical storage is not modified by customer removal.
"""
from django.db import connection, models, transaction
from django.utils import timezone

from backend.documents.models import ContractDocument
from backend.uploads.models import Upload, UserObjectAccess, VaultShare
from backend.uploads.services import archive_user_object_access


def lock_uploads(upload_ids):
    """Caller owns an atomic block and has acquired any required Contract locks."""
    if not connection.in_atomic_block:
        raise RuntimeError("File mutation requires an atomic transaction.")
    uploads = list(Upload.objects.select_for_update(of=("self",)).filter(
        pk__in=upload_ids,
    ).order_by("pk"))
    pairs = {(u.user_id, u.stored_object_id) for u in uploads if u.stored_object_id}
    accesses = {}
    if pairs:
        query = models.Q()
        for user_id, object_id in pairs:
            query |= models.Q(user_id=user_id, stored_object_id=object_id)
        accesses = {
            (access.user_id, access.stored_object_id): access
            for access in UserObjectAccess.objects.select_for_update().filter(query).order_by(
                "user_id", "stored_object_id",
            )
        }
    return {u.pk: u for u in uploads}, accesses


def require_vault_eligibility(upload, access, user, *, canonical_only=False):
    """Recheck stored eligibility after locking; missing canonical UOA fails closed."""
    if upload.user_id != user.pk:
        raise Upload.DoesNotExist
    if upload.stored_object_id:
        if access is None or not access.is_active or not access.is_visible:
            raise Upload.DoesNotExist
    elif canonical_only or upload.vault_removed_at is not None:
        raise Upload.DoesNotExist


def lock_eligible_upload(user, upload_id, *, canonical_only=False):
    uploads, accesses = lock_uploads([upload_id])
    # Normalize UUID input through the field without using a DISTINCT/joined lock query.
    key = Upload._meta.pk.to_python(upload_id)
    upload = uploads.get(key)
    if upload is None:
        raise Upload.DoesNotExist
    access = accesses.get((upload.user_id, upload.stored_object_id))
    require_vault_eligibility(upload, access, user, canonical_only=canonical_only)
    return upload, access


def has_customer_references(user_id, stored_object_id):
    return ContractDocument.objects.filter(
        upload__user_id=user_id, upload__stored_object_id=stored_object_id,
    ).exists()


def revoke_customer_shares(user_id, stored_object_id):
    VaultShare.objects.filter(
        owner_id=user_id, stored_object_id=stored_object_id, revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())


@transaction.atomic
def remove_from_vault(user, upload_id):
    upload, access = lock_eligible_upload(user, upload_id)
    if upload.stored_object_id is None:
        upload.vault_removed_at = timezone.now()
        upload.save(update_fields=["vault_removed_at"])
        return

    revoke_customer_shares(user.pk, upload.stored_object_id)
    retained = has_customer_references(user.pk, upload.stored_object_id)
    archive_user_object_access(
        user, upload.stored_object, is_active=retained, counts_toward_quota=retained,
    )
    if not retained:
        # Metadata deletion only. StoredObject/provider bytes remain retained.
        upload.delete()


@transaction.atomic
def create_vault_share(user, upload_id, *, token_hash, expires_at):
    upload, _ = lock_eligible_upload(user, upload_id, canonical_only=True)
    return VaultShare.objects.create(
        owner=user, stored_object_id=upload.stored_object_id,
        token_hash=token_hash, expires_at=expires_at,
    )


def reconcile_removed_accesses(accesses):
    """Caller still holds Upload/UOA locks after deleting references.

    Hidden grants without a removal timestamp are not customer removals. Only
    the uploader's UOA is supplied, including when a counterparty detaches.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("Reference reconciliation requires an atomic transaction.")
    for access in accesses.values():
        if access.is_visible or access.removed_at is None:
            continue
        if has_customer_references(access.user_id, access.stored_object_id):
            continue
        access.is_active = False
        access.counts_toward_quota = False
        access.save(update_fields=["is_active", "counts_toward_quota", "updated_at"])
        revoke_customer_shares(access.user_id, access.stored_object_id)
