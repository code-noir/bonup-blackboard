# backend/api/uploads/views.py

import hashlib
import logging
import os
import secrets
import tempfile
import uuid
import zipfile
from datetime import timedelta
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.api.operator.permissions import file_content_prohibited, require_file_content_access
from backend.billing.storage import check_storage_write_admission, get_storage_capacity_snapshot
from backend.emailing.services import (
    EmailAttachment,
    EmailMessage,
    EmailProviderDeliveryError,
    EmailServiceUnavailable,
    send_email,
)
from backend.uploads.models import Upload, VaultEmailDelivery, VaultFolder, VaultShare
from backend.uploads.services import (
    archive_user_object_access,
    create_managed_upload,
    create_stored_object_metadata,
    get_active_uploads_for_user,
    get_active_canonical_uploads_for_user,
    get_storage_backend,
    get_stored_object_url,
    get_upload_url,
    grant_user_object_access,
    remove_user_object_access,
    StorageAdmissionRejected,
)

VALID_FILE_TYPES = {"pdf", "image", "video", "audio", "slides", "document", "other"}
VALID_SHARE_EXPIRATIONS = {
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "none": None,
}
DEFAULT_SHARE_EXPIRATION = "7d"
BULK_REMOVE_MAX_UPLOADS = 100
BULK_MOVE_MAX_UPLOADS = 100
BULK_DOWNLOAD_MAX_UPLOADS = 25
BULK_DOWNLOAD_DEFAULT_MAX_BYTES = 512 * 1024 * 1024
BULK_DOWNLOAD_FILENAME = "bonUP-Vault-Download.zip"
EMAIL_SUBJECT_MAX_LENGTH = 255
EMAIL_MESSAGE_MAX_LENGTH = 4000
SHARE_UNAVAILABLE_RESPONSE = {"detail": "Share is unavailable."}
logger = logging.getLogger(__name__)


def _storage_capacity_response(check):
    return Response(
        {
            "error": "Storage capacity exceeded.",
            "code": "storage_capacity_exceeded",
            "capacity_bytes": check.entitled_bytes,
            "used_bytes": check.used_bytes,
            "available_bytes": check.remaining_bytes,
            "incoming_bytes": check.incoming_bytes,
        },
        status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    )


def _cleanup_saved_object(saved_key):
    try:
        default_storage.delete(saved_key)
    except Exception:
        logger.exception("Failed to clean up saved upload object after database failure.")


def _cleanup_saved_object_with_storage(storage, saved_key):
    try:
        storage.delete(saved_key)
    except Exception:
        logger.exception("Failed to clean up saved duplicate upload object after database failure.")


def _active_uploads_for_user(user):
    return get_active_uploads_for_user(user)


def _active_canonical_uploads_for_user(user):
    return get_active_canonical_uploads_for_user(user)


def _serialize(upload, request):
    return {
        "id": str(upload.id),
        "file_url": None if file_content_prohibited(request) else get_upload_url(upload),
        "file_name": upload.file_name,
        "file_type": upload.file_type,
        "content_type": upload.stored_object.content_type if upload.stored_object_id else "",
        "file_size": upload.file_size,
        "folder_id": str(upload.vault_folder_id) if upload.vault_folder_id else None,
        "related_contract": str(upload.related_contract_id) if upload.related_contract_id else None,
        "related_session": str(upload.related_session_id) if upload.related_session_id else None,
        "is_prep_material": upload.is_prep_material,
        "is_draft_document": upload.is_draft_document,
        "uploaded_at": upload.uploaded_at,
    }


def _serialize_folder(folder):
    return {
        "id": str(folder.id),
        "name": folder.name,
        "parent_id": str(folder.parent_id) if folder.parent_id else None,
        "created_at": folder.created_at,
        "updated_at": folder.updated_at,
    }


def _validate_folder_name(value):
    name = value.strip() if isinstance(value, str) else ""
    if not name:
        return None, _validation_error("folder_name_required", "Folder name is required.")
    if len(name) > VaultFolder._meta.get_field("name").max_length:
        return None, _validation_error("folder_name_too_long", "Folder name must be 255 characters or fewer.")
    if "/" in name or "\\" in name:
        return None, _validation_error("invalid_folder_name", "Folder name cannot contain path separators.")
    return name, None


def _folder_for_user(user, folder_id):
    if not folder_id:
        return None, None
    return get_object_or_404(VaultFolder, pk=folder_id, user=user), folder_id


def _folder_destination_for_user(user, folder_id):
    if folder_id in (None, ""):
        return None, None
    try:
        normalized_id = uuid.UUID(str(folder_id))
    except (TypeError, ValueError):
        return None, _validation_error("invalid_folder_id", "folder_id must be null or a valid UUID.")

    folder = VaultFolder.objects.filter(pk=normalized_id, user=user).first()
    if folder is None:
        return None, _validation_error("folder_not_found", "Destination folder could not be found.", status_code=status.HTTP_404_NOT_FOUND)
    return folder, None


def _folder_validation_response(exc):
    messages = []
    if hasattr(exc, "message_dict"):
        for values in exc.message_dict.values():
            messages.extend(values)
    elif hasattr(exc, "messages"):
        messages.extend(exc.messages)
    detail = messages[0] if messages else "Folder could not be saved."
    return _validation_error("invalid_folder", detail)


def _copy_name(file_name, existing_names):
    if "." not in file_name.strip("."):
        stem = file_name
        extension = ""
    else:
        stem, extension = file_name.rsplit(".", 1)
        extension = f".{extension}"

    candidate = f"{stem} copy{extension}"
    if candidate not in existing_names:
        return candidate

    index = 2
    while True:
        candidate = f"{stem} copy {index}{extension}"
        if candidate not in existing_names:
            return candidate
        index += 1


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_share_token():
    return secrets.token_urlsafe(32)


def _share_expires_at(choice):
    delta = VALID_SHARE_EXPIRATIONS[choice]
    if delta is None:
        return None
    return timezone.now() + delta


def _owner_has_active_access(share):
    return share.stored_object.user_accesses.filter(
        user=share.owner,
        is_active=True,
        is_visible=True,
    ).exists()


def _is_share_valid(share):
    if share.revoked_at is not None:
        return False
    if share.expires_at is not None and share.expires_at <= timezone.now():
        return False
    return _owner_has_active_access(share)


def _resolve_valid_share(token):
    try:
        share = VaultShare.objects.select_related("owner", "stored_object").get(token_hash=_token_hash(token))
    except VaultShare.DoesNotExist:
        return None
    if not _is_share_valid(share):
        return None
    return share


def _owner_upload_for_share(share):
    return Upload.objects.filter(
        user=share.owner,
        stored_object=share.stored_object,
    ).order_by("-uploaded_at").first()


def _serialize_share(share, token, request):
    upload = _owner_upload_for_share(share)
    filename = upload.file_name if upload else "Shared file"
    file_type = upload.file_type if upload else "other"
    return {
        "id": str(share.id),
        "share_url": request.build_absolute_uri(f"/share/{token}"),
        "expires_at": share.expires_at,
        "revoked_at": share.revoked_at,
        "file_name": filename,
        "file_type": file_type,
        "content_type": share.stored_object.content_type,
        "file_size": share.stored_object.size_bytes,
    }


def _serialize_public_share(share, token):
    upload = _owner_upload_for_share(share)
    filename = upload.file_name if upload else "Shared file"
    file_type = upload.file_type if upload else "other"
    return {
        "file_name": filename,
        "file_type": file_type,
        "content_type": share.stored_object.content_type,
        "file_size": share.stored_object.size_bytes,
        "delivery_url": f"/api/uploads/shares/{token}/delivery/",
    }


def _validation_error(code, detail, *, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"code": code, "detail": detail}, status=status_code)


def _normalize_upload_ids(upload_ids, *, max_count):
    if not isinstance(upload_ids, list):
        return None, _validation_error("invalid_upload_ids", "upload_ids must be a list.")
    if not upload_ids:
        return None, _validation_error("empty_upload_ids", "Select at least one file.")

    normalized_ids = []
    seen = set()
    for raw_upload_id in upload_ids:
        try:
            normalized_id = str(uuid.UUID(str(raw_upload_id)))
        except (TypeError, ValueError):
            return None, _validation_error("invalid_upload_id", "Each upload_id must be a valid UUID.")
        if normalized_id not in seen:
            seen.add(normalized_id)
            normalized_ids.append(normalized_id)

    if len(normalized_ids) > max_count:
        return None, _validation_error("too_many_upload_ids", f"Select up to {max_count} files.")
    return normalized_ids, None


def _bulk_download_max_bytes():
    return int(getattr(settings, "BONUP_VAULT_BULK_DOWNLOAD_MAX_BYTES", BULK_DOWNLOAD_DEFAULT_MAX_BYTES) or 0)


def _safe_zip_member_name(file_name, existing_names):
    normalized = (file_name or "file").replace("\\", "/").replace("\x00", "")
    candidate = PurePosixPath(normalized).name.strip()
    if candidate in ("", ".", ".."):
        candidate = "file"

    if candidate not in existing_names:
        existing_names.add(candidate)
        return candidate

    if "." in candidate.strip("."):
        stem, extension = candidate.rsplit(".", 1)
        extension = f".{extension}"
    else:
        stem = candidate
        extension = ""

    index = 2
    while True:
        disambiguated = f"{stem} ({index}){extension}"
        if disambiguated not in existing_names:
            existing_names.add(disambiguated)
            return disambiguated
        index += 1


class TemporaryArchiveFile:
    def __init__(self, path):
        self.path = path
        self.file = open(path, "rb")

    def read(self, *args):
        return self.file.read(*args)

    def seek(self, *args):
        return self.file.seek(*args)

    def tell(self):
        return self.file.tell()

    def close(self):
        try:
            self.file.close()
        finally:
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass
            except Exception:
                logger.exception("Failed to clean up temporary Vault bulk-download archive.")


def _move_upload_to_folder(upload, folder):
    folder_id = folder.id if folder else None
    if upload.vault_folder_id != folder_id:
        upload.vault_folder = folder
        upload.save(update_fields=["vault_folder"])
    return upload


def _remove_upload_from_vault(user, upload):
    if upload.stored_object_id:
        now = timezone.now()
        VaultShare.objects.filter(
            owner=user,
            stored_object=upload.stored_object,
            revoked_at__isnull=True,
        ).update(revoked_at=now)

        if upload.contract_documents.exists():
            archive_user_object_access(
                user,
                upload.stored_object,
                is_active=True,
                counts_toward_quota=True,
            )
            return

        remove_user_object_access(user, upload.stored_object)
        upload.delete()
        return

    if upload.storage_key:
        default_storage.delete(upload.storage_key)

    upload.delete()


def _validate_file_name(value):
    file_name = value.strip() if isinstance(value, str) else ""
    if not file_name:
        return None, _validation_error("file_name_required", "Filename is required.")
    if len(file_name) > Upload._meta.get_field("file_name").max_length:
        return None, _validation_error("file_name_too_long", "Filename must be 255 characters or fewer.")
    if "/" in file_name or "\\" in file_name:
        return None, _validation_error("invalid_file_name", "Filename cannot contain path separators.")
    return file_name, None


def _normalize_recipient(value):
    recipient = (value or "").strip()
    validate_email(recipient)
    return recipient.lower()


def _email_body(message, *, sender, filename):
    parts = []
    if message:
        parts.append(message)
    parts.append(f"Attached: {filename}")
    parts.append(f"Sent by {sender} through bonUP Vault.")
    return "\n\n".join(parts)


def _recent_vault_email_count(user):
    since = timezone.now() - timedelta(hours=1)
    return VaultEmailDelivery.objects.filter(sender_user=user, created_at__gte=since).count()


def _serialize_email_delivery(delivery, *, idempotent=False):
    return {
        "status": delivery.status,
        "delivery_id": str(delivery.id),
        "provider": delivery.provider,
        "provider_message_id": delivery.provider_message_id,
        "idempotent": idempotent,
    }


class UploadsViewSet(ViewSet):

    def list(self, request):
        qs = _active_uploads_for_user(request.user)

        canonical = request.query_params.get("canonical")
        if canonical is not None and canonical.lower() in ("true", "1", "yes"):
            qs = _active_canonical_uploads_for_user(request.user)

        contract_id = request.query_params.get("contract_id")
        if contract_id:
            qs = qs.filter(related_contract_id=contract_id)

        session_id = request.query_params.get("session_id")
        if session_id:
            qs = qs.filter(related_session_id=session_id)

        is_draft = request.query_params.get("is_draft_document")
        if is_draft is not None:
            qs = qs.filter(is_draft_document=is_draft.lower() in ("true", "1", "yes"))

        return Response([_serialize(u, request) for u in qs])

    def partial_update(self, request, pk=None):
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)
        file_name, error = _validate_file_name(request.data.get("file_name"))
        if error is not None:
            return error

        upload.file_name = file_name
        upload.save(update_fields=["file_name"])
        return Response(_serialize(upload, request))

    def create(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "file is required"}, status=status.HTTP_400_BAD_REQUEST)

        file_type = request.data.get("file_type", "").strip().lower()
        if file_type not in VALID_FILE_TYPES:
            return Response(
                {"error": f"file_type must be one of: {', '.join(sorted(VALID_FILE_TYPES))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract_id = request.data.get("contract_id") or None
        session_id = request.data.get("session_id") or None
        folder_id = request.data.get("folder_id") or None
        folder, _ = _folder_for_user(request.user, folder_id)
        is_prep = request.data.get("is_prep_material", "false")
        if isinstance(is_prep, str):
            is_prep = is_prep.lower() in ("true", "1", "yes")

        try:
            upload = create_managed_upload(
                user=request.user,
                file=file,
                file_type=file_type,
                related_contract_id=contract_id,
                related_session_id=session_id,
                vault_folder_id=folder.id if folder else None,
                is_prep_material=is_prep,
            )
        except ValidationError:
            return Response(
                {"error": "Invalid file size.", "code": "invalid_file_size"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except StorageAdmissionRejected as exc:
            return _storage_capacity_response(exc.check)

        return Response(_serialize(upload, request), status=status.HTTP_201_CREATED)


    @action(detail=False, methods=["get", "post"], url_path="folders")
    def folders(self, request):
        if request.method == "GET":
            folders = VaultFolder.objects.filter(user=request.user).select_related("parent").order_by("name", "created_at")
            return Response([_serialize_folder(folder) for folder in folders])

        name, error = _validate_folder_name(request.data.get("name"))
        if error is not None:
            return error
        parent_id = request.data.get("parent_id") or None
        parent, _ = _folder_for_user(request.user, parent_id)
        folder = VaultFolder(user=request.user, name=name, parent=parent)
        try:
            folder.save()
        except ValidationError as exc:
            return _folder_validation_response(exc)
        except IntegrityError:
            return _validation_error("duplicate_folder_name", "A folder with this name already exists in this location.", status_code=status.HTTP_409_CONFLICT)
        return Response(_serialize_folder(folder), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["patch", "delete"], url_path=r"folders/(?P<folder_id>[^/.]+)")
    def folder_detail(self, request, folder_id=None):
        folder = get_object_or_404(VaultFolder, pk=folder_id, user=request.user)

        if request.method == "DELETE":
            if folder.children.exists() or folder.uploads.exists():
                return _validation_error("folder_not_empty", "Only empty folders can be deleted.", status_code=status.HTTP_409_CONFLICT)
            folder.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if "name" in request.data:
            name, error = _validate_folder_name(request.data.get("name"))
            if error is not None:
                return error
            folder.name = name
        if "parent_id" in request.data:
            parent_id = request.data.get("parent_id") or None
            parent, _ = _folder_for_user(request.user, parent_id)
            folder.parent = parent

        try:
            folder.save()
        except ValidationError as exc:
            return _folder_validation_response(exc)
        except IntegrityError:
            return _validation_error("duplicate_folder_name", "A folder with this name already exists in this location.", status_code=status.HTTP_409_CONFLICT)
        return Response(_serialize_folder(folder))

    @action(detail=False, methods=["get"], url_path="storage")
    def storage(self, request):
        snapshot = get_storage_capacity_snapshot(request.user)
        return Response({
            "capacity_bytes": snapshot.entitled_bytes,
            "used_bytes": snapshot.used_bytes,
            "available_bytes": snapshot.remaining_bytes,
        })

    @action(detail=False, methods=["post"], url_path="bulk-remove")
    def bulk_remove(self, request):
        normalized_ids, error = _normalize_upload_ids(request.data.get("upload_ids"), max_count=BULK_REMOVE_MAX_UPLOADS)
        if error is not None:
            return error

        accessible_uploads = {
            str(upload.id): upload
            for upload in _active_uploads_for_user(request.user).filter(pk__in=normalized_ids)
        }
        results = []
        removed_count = 0
        failed_count = 0

        for upload_id in normalized_ids:
            upload = accessible_uploads.get(upload_id)
            if upload is None:
                failed_count += 1
                results.append({
                    "upload_id": upload_id,
                    "status": "failed",
                    "error": "File not found.",
                })
                continue

            _remove_upload_from_vault(request.user, upload)
            removed_count += 1
            results.append({
                "upload_id": upload_id,
                "status": "removed",
            })

        return Response({
            "results": results,
            "removed_count": removed_count,
            "failed_count": failed_count,
        })

    @action(detail=False, methods=["post"], url_path="bulk-move")
    def bulk_move(self, request):
        normalized_ids, error = _normalize_upload_ids(request.data.get("upload_ids"), max_count=BULK_MOVE_MAX_UPLOADS)
        if error is not None:
            return error

        folder, error = _folder_destination_for_user(request.user, request.data.get("folder_id"))
        if error is not None:
            return error

        accessible_uploads = {
            str(upload.id): upload
            for upload in _active_canonical_uploads_for_user(request.user).filter(pk__in=normalized_ids)
        }
        results = []
        moved_count = 0
        failed_count = 0

        for upload_id in normalized_ids:
            upload = accessible_uploads.get(upload_id)
            if upload is None:
                failed_count += 1
                results.append({
                    "upload_id": upload_id,
                    "status": "failed",
                    "error": "File not found.",
                })
                continue

            _move_upload_to_folder(upload, folder)
            moved_count += 1
            results.append({
                "upload_id": upload_id,
                "status": "moved",
            })

        return Response({
            "results": results,
            "moved_count": moved_count,
            "failed_count": failed_count,
        })

    @action(detail=False, methods=["post"], url_path="bulk-download")
    def bulk_download(self, request):
        require_file_content_access(request)
        normalized_ids, error = _normalize_upload_ids(request.data.get("upload_ids"), max_count=BULK_DOWNLOAD_MAX_UPLOADS)
        if error is not None:
            return error

        uploads_by_id = {
            str(upload.id): upload
            for upload in _active_canonical_uploads_for_user(request.user)
            .filter(pk__in=normalized_ids)
            .select_related("stored_object", "vault_folder")
        }
        if len(uploads_by_id) != len(normalized_ids):
            return _validation_error("file_not_found", "One or more selected files could not be found.", status_code=status.HTTP_404_NOT_FOUND)

        uploads = [uploads_by_id[upload_id] for upload_id in normalized_ids]
        total_source_bytes = sum(upload.stored_object.size_bytes for upload in uploads)
        max_bytes = _bulk_download_max_bytes()
        if max_bytes < 1 or total_source_bytes > max_bytes:
            return _validation_error(
                "bulk_download_too_large",
                "Selected files are too large to download together. Select fewer or smaller files.",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        tmp = tempfile.NamedTemporaryFile(prefix="bonup-vault-", suffix=".zip", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            used_names = set()
            with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for upload in uploads:
                    storage = get_storage_backend(upload.stored_object.backend)
                    member_name = _safe_zip_member_name(upload.file_name, used_names)
                    with storage.open(upload.stored_object.object_key, "rb") as source_file:
                        with archive.open(member_name, "w") as target_file:
                            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                                target_file.write(chunk)
        except Exception:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            except Exception:
                logger.exception("Failed to clean up temporary Vault bulk-download archive after failure.")
            logger.exception("Failed to prepare Vault bulk-download archive.")
            return _validation_error(
                "bulk_download_unavailable",
                "One or more selected files could not be prepared for download.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = FileResponse(
            TemporaryArchiveFile(tmp_path),
            as_attachment=True,
            filename=BULK_DOWNLOAD_FILENAME,
            content_type="application/zip",
        )
        return response

    @action(detail=True, methods=["post"], url_path="folder")
    def move_to_folder(self, request, pk=None):
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)
        folder, error = _folder_destination_for_user(request.user, request.data.get("folder_id"))
        if error is not None:
            return error
        _move_upload_to_folder(upload, folder)
        return Response(_serialize(upload, request))

    @action(detail=True, methods=["get"], url_path="delivery")
    def delivery(self, request, pk=None, format=None):
        require_file_content_access(request)
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)
        storage = get_storage_backend(upload.stored_object.backend)
        content_type = upload.stored_object.content_type or "application/octet-stream"
        return FileResponse(
            storage.open(upload.stored_object.object_key, "rb"),
            as_attachment=True,
            filename=upload.file_name,
            content_type=content_type,
        )

    @action(detail=True, methods=["post"], url_path="email")
    def email_file(self, request, pk=None):
        require_file_content_access(request)
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)

        try:
            recipient = _normalize_recipient(request.data.get("to", ""))
        except ValidationError:
            return _validation_error("invalid_recipient", "Enter one valid recipient email address.")

        subject = (request.data.get("subject") or "").strip()
        message = (request.data.get("message") or "").strip()
        if not subject:
            return _validation_error("subject_required", "Subject is required.")
        if len(subject) > EMAIL_SUBJECT_MAX_LENGTH:
            return _validation_error("subject_too_long", f"Subject must be {EMAIL_SUBJECT_MAX_LENGTH} characters or fewer.")
        if len(message) > EMAIL_MESSAGE_MAX_LENGTH:
            return _validation_error("message_too_long", f"Message must be {EMAIL_MESSAGE_MAX_LENGTH} characters or fewer.")

        idempotency_key = (request.headers.get("Idempotency-Key") or "").strip()
        if len(idempotency_key) > 256:
            return _validation_error("invalid_idempotency_key", "Idempotency-Key must be 256 characters or fewer.")
        if idempotency_key:
            existing = VaultEmailDelivery.objects.filter(
                sender_user=request.user,
                idempotency_key=idempotency_key,
            ).first()
            if existing and existing.status == VaultEmailDelivery.Status.SENT:
                return Response(_serialize_email_delivery(existing, idempotent=True))
            if existing:
                return _validation_error("duplicate_request", "Use a new idempotency key for a retry.", status_code=status.HTTP_409_CONFLICT)

        max_attachment_bytes = getattr(settings, "BONUP_EMAIL_ATTACHMENT_MAX_BYTES", 0)
        if max_attachment_bytes < 1:
            return _validation_error("email_service_unavailable", "Email delivery is not configured.", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        if upload.stored_object.size_bytes > max_attachment_bytes:
            return _validation_error("attachment_too_large", "This file is too large to email as an attachment.", status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        hourly_limit = getattr(settings, "BONUP_VAULT_EMAIL_RATE_LIMIT_PER_HOUR", 10)
        if hourly_limit < 1:
            return _validation_error("email_service_unavailable", "Email delivery is not configured.", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        if _recent_vault_email_count(request.user) >= hourly_limit:
            return _validation_error("rate_limited", "Too many email attempts. Please try again later.", status_code=status.HTTP_429_TOO_MANY_REQUESTS)

        provider = getattr(settings, "BONUP_EMAIL_PROVIDER", "resend").strip().lower() or "resend"
        delivery = VaultEmailDelivery.objects.create(
            sender_user=request.user,
            stored_object=upload.stored_object,
            recipient_email=recipient,
            subject=subject,
            provider=provider,
            idempotency_key=idempotency_key,
        )

        storage = get_storage_backend(upload.stored_object.backend)
        try:
            with storage.open(upload.stored_object.object_key, "rb") as source_file:
                attachment_bytes = source_file.read()
        except Exception:
            delivery.status = VaultEmailDelivery.Status.FAILED
            delivery.failure_code = "attachment_read_failed"
            delivery.save(update_fields=["status", "failure_code"])
            return _validation_error("attachment_unavailable", "This file could not be prepared for email.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if len(attachment_bytes) > max_attachment_bytes:
            delivery.status = VaultEmailDelivery.Status.FAILED
            delivery.failure_code = "attachment_too_large"
            delivery.save(update_fields=["status", "failure_code"])
            return _validation_error("attachment_too_large", "This file is too large to email as an attachment.", status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        email_message = EmailMessage(
            to=[recipient],
            subject=subject,
            text=_email_body(message, sender=getattr(request.user, "email", "") or "a bonUP user", filename=upload.file_name),
            attachments=[
                EmailAttachment(
                    filename=upload.file_name,
                    content=attachment_bytes,
                    content_type=upload.stored_object.content_type or "application/octet-stream",
                ),
            ],
        )

        try:
            result = send_email(email_message, idempotency_key=idempotency_key)
        except EmailServiceUnavailable:
            delivery.status = VaultEmailDelivery.Status.FAILED
            delivery.failure_code = "email_service_unavailable"
            delivery.save(update_fields=["status", "failure_code"])
            return _validation_error("email_service_unavailable", "Email delivery is not configured.", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        except EmailProviderDeliveryError:
            delivery.status = VaultEmailDelivery.Status.FAILED
            delivery.failure_code = "provider_delivery_failure"
            delivery.save(update_fields=["status", "failure_code"])
            return _validation_error("provider_delivery_failure", "Email provider delivery failed.", status_code=status.HTTP_502_BAD_GATEWAY)

        delivery.status = VaultEmailDelivery.Status.SENT
        delivery.provider = result.provider
        delivery.provider_message_id = result.provider_message_id
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "provider", "provider_message_id", "sent_at"])
        return Response(_serialize_email_delivery(delivery), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="shares")
    def shares(self, request, pk=None):
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)

        if request.method == "GET":
            shares = VaultShare.objects.filter(owner=request.user, stored_object=upload.stored_object).order_by("-created_at")
            return Response([
                {
                    "id": str(share.id),
                    "created_at": share.created_at,
                    "expires_at": share.expires_at,
                    "revoked_at": share.revoked_at,
                    "is_valid": True,
                }
                for share in shares
                if _is_share_valid(share)
            ])

        expiration = request.data.get("expiration", DEFAULT_SHARE_EXPIRATION)
        if expiration not in VALID_SHARE_EXPIRATIONS:
            return Response(
                {"error": "expiration must be one of: 1d, 7d, 30d, none"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for _ in range(5):
            token = _new_share_token()
            try:
                share = VaultShare.objects.create(
                    owner=request.user,
                    stored_object=upload.stored_object,
                    token_hash=_token_hash(token),
                    expires_at=_share_expires_at(expiration),
                )
                return Response(_serialize_share(share, token, request), status=status.HTTP_201_CREATED)
            except IntegrityError:
                continue
        return Response({"error": "Could not create share."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path=r"shares/(?P<share_id>[^/.]+)/revoke")
    def revoke_share(self, request, pk=None, share_id=None):
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)
        share = get_object_or_404(
            VaultShare,
            pk=share_id,
            owner=request.user,
            stored_object=upload.stored_object,
        )
        if share.revoked_at is None:
            share.revoked_at = timezone.now()
            share.save(update_fields=["revoked_at"])
        return Response({"id": str(share.id), "revoked_at": share.revoked_at})

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        source = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)
        incoming_size = source.stored_object.size_bytes
        storage_check = check_storage_write_admission(request.user, incoming_size)
        if not storage_check.allowed:
            return _storage_capacity_response(storage_check)

        storage = get_storage_backend(source.stored_object.backend)
        existing_names = set(_active_uploads_for_user(request.user).values_list("file_name", flat=True))
        duplicate_name = _copy_name(source.file_name, existing_names)
        storage_key = f"uploads/{request.user.id}/{uuid.uuid4().hex}/{duplicate_name}"
        saved_key = None

        with storage.open(source.stored_object.object_key, "rb") as source_file:
            saved_key = storage.save(storage_key, File(source_file, name=duplicate_name))

        try:
            file_url = storage.url(saved_key)
            with transaction.atomic():
                stored_object = create_stored_object_metadata(
                    backend=source.stored_object.backend,
                    bucket=source.stored_object.bucket,
                    object_key=saved_key,
                    size_bytes=incoming_size,
                    content_type=source.stored_object.content_type,
                )
                grant_user_object_access(
                    request.user,
                    stored_object,
                    is_visible=True,
                    counts_toward_quota=True,
                )
                upload = Upload.objects.create(
                    user=request.user,
                    file_url=file_url,
                    file_name=duplicate_name,
                    file_type=source.file_type,
                    file_size=incoming_size,
                    storage_key=saved_key,
                    stored_object=stored_object,
                    related_contract=source.related_contract,
                    related_session=source.related_session,
                    is_prep_material=source.is_prep_material,
                    is_draft_document=source.is_draft_document,
                )
        except Exception:
            if saved_key:
                _cleanup_saved_object_with_storage(storage, saved_key)
            raise

        return Response(_serialize(upload, request), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path=r"shares/(?P<token>[^/.]+)")
    def public_share(self, request, token=None, format=None):
        require_file_content_access(request)
        share = _resolve_valid_share(token or "")
        if share is None:
            return Response(SHARE_UNAVAILABLE_RESPONSE, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_public_share(share, token or ""))

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path=r"shares/(?P<token>[^/.]+)/delivery")
    def public_share_delivery(self, request, token=None, format=None):
        require_file_content_access(request)
        share = _resolve_valid_share(token or "")
        if share is None:
            return Response(SHARE_UNAVAILABLE_RESPONSE, status=status.HTTP_404_NOT_FOUND)
        return HttpResponseRedirect(get_stored_object_url(share.stored_object))

    def destroy(self, request, pk=None):
        upload = get_object_or_404(_active_uploads_for_user(request.user), pk=pk)
        _remove_upload_from_vault(request.user, upload)
        return Response(status=status.HTTP_204_NO_CONTENT)
