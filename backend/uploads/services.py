from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.utils import timezone

from backend.uploads.models import StoredObject, UserObjectAccess

DEFAULT_STORAGE_BACKEND_ALIAS = "default"


class UnknownStorageBackendError(ValueError):
    pass


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
