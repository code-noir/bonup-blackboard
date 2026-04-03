# backend/api/uploads/views.py

import uuid

from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.uploads.models import Upload

VALID_FILE_TYPES = {"pdf", "image", "video", "slides", "document"}


def _serialize(upload):
    return {
        "id": str(upload.id),
        "file_url": upload.file_url,
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

        original_name = file.name
        storage_key = f"uploads/{request.user.id}/{uuid.uuid4().hex}/{original_name}"
        saved_key = default_storage.save(storage_key, file)
        file_url = default_storage.url(saved_key)

        contract_id = request.data.get("contract_id") or None
        session_id = request.data.get("session_id") or None
        is_prep = request.data.get("is_prep_material", "false")
        if isinstance(is_prep, str):
            is_prep = is_prep.lower() in ("true", "1", "yes")

        upload = Upload.objects.create(
            user=request.user,
            file_url=file_url,
            file_name=original_name,
            file_type=file_type,
            file_size=file.size,
            storage_key=saved_key,
            related_contract_id=contract_id,
            related_session_id=session_id,
            is_prep_material=bool(is_prep),
        )

        return Response(_serialize(upload), status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        upload = get_object_or_404(Upload, pk=pk, user=request.user)

        if upload.storage_key:
            default_storage.delete(upload.storage_key)

        upload.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
