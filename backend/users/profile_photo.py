"""Canonical bonUP profile-photo eligibility and projection helpers."""

PROFILE_PHOTO_CONTENT_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/avif",
})
PROFILE_PHOTO_FILE_TYPE = "image"


def profile_photo_is_eligible(profile):
    """Return whether the selected asset is a supported, owned Vault image."""
    upload = getattr(profile, "profile_photo", None)
    if not upload or upload.user_id != profile.user_id:
        return False
    if upload.vault_removed_at is not None or upload.file_type != PROFILE_PHOTO_FILE_TYPE:
        return False
    if not upload.stored_object_id or not upload.stored_object:
        return False
    return upload.stored_object.content_type.split(";", 1)[0].strip().lower() in PROFILE_PHOTO_CONTENT_TYPES


def profile_photo_url(profile):
    if not profile.profile_photo_visible or not profile_photo_is_eligible(profile):
        return None
    return f"/api/users/{profile.bon_id}/profile-photo/"


def profile_photo_id(profile):
    return str(profile.profile_photo_id) if profile_photo_is_eligible(profile) else None
