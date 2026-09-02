# backend/api/uploads/views.py

import hashlib
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db import IntegrityError, models, transaction
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.billing.storage import check_storage_write_admission, get_storage_capacity_snapshot
from backend.uploads.models import Upload, VaultShare
from backend.uploads.services import (
    DEFAULT_STORAGE_BACKEND_ALIAS,
    create_stored_object_metadata,
    get_storage_backend,
    get_stored_object_url,
    get_upload_url,
    grant_user_object_access,
    remove_user_object_access,
)

VALID_FILE_TYPES = {"pdf", "image", "video", "audio", "slides", "document", "other"}
VALID_SHARE_EXPIRATIONS = {
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "none": None,
}
DEFAULT_SHARE_EXPIRATION = "7d"
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
    return Upload.objects.filter(user=user).filter(
        models.Q(stored_object__isnull=True)
        | models.Q(
            stored_object__user_accesses__user=user,
            stored_object__user_accesses__is_active=True,
        )
    ).distinct()


def _active_canonical_uploads_for_user(user):
    return _active_uploads_for_user(user).filter(stored_object__isnull=False)


def _serialize(upload):
    return {
        "id": str(upload.id),
        "file_url": get_upload_url(upload),
        "file_name": upload.file_name,
        "file_type": upload.file_type,
        "content_type": upload.stored_object.content_type if upload.stored_object_id else "",
        "file_size": upload.file_size,
        "related_contract": str(upload.related_contract_id) if upload.related_contract_id else None,
        "related_session": str(upload.related_session_id) if upload.related_session_id else None,
        "is_prep_material": upload.is_prep_material,
        "is_draft_document": upload.is_draft_document,
        "uploaded_at": upload.uploaded_at,
    }


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


class UploadsViewSet(ViewSet):

    def list(self, request):
        qs = _active_uploads_for_user(request.user)

        contract_id = request.query_params.get("contract_id")
        if contract_id:
            qs = qs.filter(related_contract_id=contract_id)

        session_id = request.query_params.get("session_id")
        if session_id:
            qs = qs.filter(related_session_id=session_id)

        is_draft = request.query_params.get("is_draft_document")
        if is_draft is not None:
            qs = qs.filter(is_draft_document=is_draft.lower() in ("true", "1", "yes"))

        return Response([_serialize(u) for u in qs])

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

        incoming_size = file.size
        try:
            storage_check = check_storage_write_admission(request.user, incoming_size)
        except ValidationError:
            return Response(
                {"error": "Invalid file size.", "code": "invalid_file_size"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not storage_check.allowed:
            return _storage_capacity_response(storage_check)

        original_name = file.name
        storage_key = f"uploads/{request.user.id}/{uuid.uuid4().hex}/{original_name}"
        saved_key = default_storage.save(storage_key, file)

        try:
            file_url = default_storage.url(saved_key)
            contract_id = request.data.get("contract_id") or None
            session_id = request.data.get("session_id") or None
            is_prep = request.data.get("is_prep_material", "false")
            if isinstance(is_prep, str):
                is_prep = is_prep.lower() in ("true", "1", "yes")

            with transaction.atomic():
                stored_object = create_stored_object_metadata(
                    backend=DEFAULT_STORAGE_BACKEND_ALIAS,
                    bucket=getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""),
                    object_key=saved_key,
                    size_bytes=incoming_size,
                    content_type=getattr(file, "content_type", "") or "",
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
                    file_name=original_name,
                    file_type=file_type,
                    file_size=incoming_size,
                    storage_key=saved_key,
                    stored_object=stored_object,
                    related_contract_id=contract_id,
                    related_session_id=session_id,
                    is_prep_material=bool(is_prep),
                )
        except Exception:
            _cleanup_saved_object(saved_key)
            raise

        return Response(_serialize(upload), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="storage")
    def storage(self, request):
        snapshot = get_storage_capacity_snapshot(request.user)
        return Response({
            "capacity_bytes": snapshot.entitled_bytes,
            "used_bytes": snapshot.used_bytes,
            "available_bytes": snapshot.remaining_bytes,
        })

    @action(detail=True, methods=["get"], url_path="delivery")
    def delivery(self, request, pk=None):
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)
        storage = get_storage_backend(upload.stored_object.backend)
        content_type = upload.stored_object.content_type or "application/octet-stream"
        return FileResponse(
            storage.open(upload.stored_object.object_key, "rb"),
            as_attachment=True,
            filename=upload.file_name,
            content_type=content_type,
        )

    @action(detail=True, methods=["get", "post"], url_path="shares")
    def shares(self, request, pk=None):
        upload = get_object_or_404(_active_canonical_uploads_for_user(request.user), pk=pk)

        if request.method == "GET":
            shares = VaultShare.objects.filter(owner=request.user, stored_object=upload.stored_object).order_by("-created_at")
            return Response([
                {
                    "id": str(share.id),
                    "expires_at": share.expires_at,
                    "revoked_at": share.revoked_at,
                    "is_valid": _is_share_valid(share),
                }
                for share in shares
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

        return Response(_serialize(upload), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path=r"shares/(?P<token>[^/.]+)")
    def public_share(self, request, token=None):
        share = _resolve_valid_share(token or "")
        if share is None:
            return Response(SHARE_UNAVAILABLE_RESPONSE, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_public_share(share, token or ""))

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], url_path=r"shares/(?P<token>[^/.]+)/delivery")
    def public_share_delivery(self, request, token=None):
        share = _resolve_valid_share(token or "")
        if share is None:
            return Response(SHARE_UNAVAILABLE_RESPONSE, status=status.HTTP_404_NOT_FOUND)
        return HttpResponseRedirect(get_stored_object_url(share.stored_object))

    def destroy(self, request, pk=None):
        upload = get_object_or_404(_active_uploads_for_user(request.user), pk=pk)

        if upload.stored_object_id:
            now = timezone.now()
            VaultShare.objects.filter(
                owner=request.user,
                stored_object=upload.stored_object,
                revoked_at__isnull=True,
            ).update(revoked_at=now)
            remove_user_object_access(request.user, upload.stored_object)
        elif upload.storage_key:
            default_storage.delete(upload.storage_key)

        upload.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
