import logging
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from backend.uploads.models import StoredObject, Upload, UserObjectAccess

DEFAULT_STORAGE_BACKEND_ALIAS = "default"
logger = logging.getLogger(__name__)


class UnknownStorageBackendError(ValueError):
    pass


class StorageAdmissionRejected(Exception):
    def __init__(self, check):
        self.check = check
        super().__init__(check.reason)


def cleanup_saved_object(saved_key):
    try:
        default_storage.delete(saved_key)
    except Exception:
        logger.exception("Failed to clean up saved upload object after database failure.")


def get_storage_backend(backend):
    if backend == DEFAULT_STORAGE_BACKEND_ALIAS:
        return default_storage
    raise UnknownStorageBackendError(f"Unknown storage backend alias: {backend}")


def create_stored_object_metadata(
    *,
    backend=DEFAULT_STORAGE_BACKEND_ALIAS,
    bucket="",
    object_key,
    size_bytes,
    content_type="",
    checksum="",
    checksum_algorithm="",
):
    return StoredObject.objects.create(
        backend=backend,
        bucket=bucket or "",
        object_key=object_key,
        size_bytes=size_bytes,
        content_type=content_type or "",
        checksum=checksum or "",
        checksum_algorithm=checksum_algorithm or "",
    )


def create_managed_upload(
    *,
    user,
    file,
    file_type,
    related_contract_id=None,
    related_session_id=None,
    is_prep_material=False,
    is_draft_document=False,
):
    from backend.billing.storage import check_storage_write_admission

    incoming_size = file.size
    storage_check = check_storage_write_admission(user, incoming_size)
    if not storage_check.allowed:
        raise StorageAdmissionRejected(storage_check)

    original_name = file.name
    storage_key = f"uploads/{user.id}/{uuid.uuid4().hex}/{original_name}"
    saved_key = default_storage.save(storage_key, file)

    try:
        file_url = default_storage.url(saved_key)
        with transaction.atomic():
            stored_object = create_stored_object_metadata(
                backend=DEFAULT_STORAGE_BACKEND_ALIAS,
                bucket=getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""),
                object_key=saved_key,
                size_bytes=incoming_size,
                content_type=getattr(file, "content_type", "") or "",
            )
            grant_user_object_access(
                user,
                stored_object,
                is_visible=True,
                counts_toward_quota=True,
            )
            return Upload.objects.create(
                user=user,
                file_url=file_url,
                file_name=original_name,
                file_type=file_type,
                file_size=incoming_size,
                storage_key=saved_key,
                stored_object=stored_object,
                related_contract_id=related_contract_id,
                related_session_id=related_session_id,
                is_prep_material=bool(is_prep_material),
                is_draft_document=bool(is_draft_document),
            )
    except Exception:
        cleanup_saved_object(saved_key)
        raise


def get_stored_object_url(stored_object):
    storage = get_storage_backend(stored_object.backend)
    return storage.url(stored_object.object_key)


def grant_user_object_access(
    user,
    stored_object,
    *,
    is_visible=True,
    counts_toward_quota=True,
):
    access, created = UserObjectAccess.objects.get_or_create(
        user=user,
        stored_object=stored_object,
        defaults={
            "is_active": True,
            "is_visible": is_visible,
            "counts_toward_quota": counts_toward_quota,
        },
    )
    if not created and not access.is_active:
        raise ValidationError(
            "User object access was previously removed. Reactivate it explicitly."
        )
    return access


def remove_user_object_access(user, stored_object):
    access = UserObjectAccess.objects.get(user=user, stored_object=stored_object)
    access.is_active = False
    access.is_visible = False
    access.removed_at = timezone.now()
    access.save(update_fields=["is_active", "is_visible", "removed_at", "updated_at"])
    return access


def reactivate_user_object_access(
    user,
    stored_object,
    *,
    is_visible=True,
    counts_toward_quota=True,
):
    access = UserObjectAccess.objects.get(user=user, stored_object=stored_object)
    access.is_active = True
    access.is_visible = is_visible
    access.counts_toward_quota = counts_toward_quota
    access.removed_at = None
    access.save(
        update_fields=[
            "is_active",
            "is_visible",
            "counts_toward_quota",
            "removed_at",
            "updated_at",
        ]
    )
    return access


def user_can_access_stored_object(user, stored_object):
    return UserObjectAccess.objects.filter(
        user=user,
        stored_object=stored_object,
        is_active=True,
    ).exists()


def get_upload_url(upload):
    if upload.storage_key:
        return default_storage.url(upload.storage_key)
    if upload.file_url:
        return upload.file_url
    return None
