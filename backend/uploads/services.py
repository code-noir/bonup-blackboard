from django.core.files.storage import default_storage

from backend.uploads.models import StoredObject

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


def get_upload_url(upload):
    if upload.storage_key:
        return default_storage.url(upload.storage_key)
    if upload.file_url:
        return upload.file_url
    return None
