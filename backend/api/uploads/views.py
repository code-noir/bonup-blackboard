# backend/api/uploads/views.py

import logging
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.billing.storage import check_storage_write_admission
from backend.uploads.models import Upload
from backend.uploads.services import (
    DEFAULT_STORAGE_BACKEND_ALIAS,
    create_stored_object_metadata,
    get_upload_url,
    grant_user_object_access,
    remove_user_object_access,
)

VALID_FILE_TYPES = {"pdf", "image", "video", "slides", "document"}
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


def _serialize(upload):
    return {
        "id": str(upload.id),
        "file_url": get_upload_url(upload),
        "file_name": upload.file_name,
        "file_type": upload.file_type,
        "file_size": upload.file_size,
        "related_contract": str(upload.related_contract_id) if upload.related_contract_id else None,
        "related_session": str(upload.related_session_id) if upload.related_session_id else None,
        "is_prep_material": upload.is_prep_material,
        "is_draft_document": upload.is_draft_document,
        "uploaded_at": upload.uploaded_at,
    }


class UploadsViewSet(ViewSet):

    def list(self, request):
        qs = Upload.objects.filter(user=request.user)

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

    def destroy(self, request, pk=None):
        upload = get_object_or_404(Upload, pk=pk, user=request.user)

        if upload.stored_object_id:
            remove_user_object_access(request.user, upload.stored_object)
        elif upload.storage_key:
            default_storage.delete(upload.storage_key)

        upload.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
