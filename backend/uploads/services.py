from django.core.files.storage import default_storage


def get_upload_url(upload):
    if upload.storage_key:
        return default_storage.url(upload.storage_key)
    if upload.file_url:
        return upload.file_url
    return None
