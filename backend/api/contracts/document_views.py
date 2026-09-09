# backend/api/contracts/document_views.py

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.operator.permissions import file_content_prohibited, require_file_content_access
from backend.contracts.models import Contract
from backend.documents.models import ContractDocument
from backend.documents.services import attach_upload, detach_document
from backend.uploads.models import Upload
from backend.uploads.services import StorageAdmissionRejected, create_managed_upload
from .permissions import contract_party_response, is_party

from backend.uploads.delivery import deliver_upload, document_delivery_url, DeliveryPrivacyMixin

VALID_CONTRACT_DOCUMENT_FILE_TYPES = {choice[0] for choice in Upload.FILE_TYPE_CHOICES}


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


def _file_type_from_upload_request(request_file, raw_file_type):
    value = (raw_file_type or "").strip().lower()
    if value in VALID_CONTRACT_DOCUMENT_FILE_TYPES:
        return value

    content_type = (getattr(request_file, "content_type", "") or "").lower()
    extension = (getattr(request_file, "name", "") or "").rsplit(".", 1)[-1].lower()
    if content_type == "application/pdf" or extension == "pdf":
        return "pdf"
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"
    if extension in {"ppt", "pptx", "key"}:
        return "slides"
    if extension in {"doc", "docx", "txt", "rtf", "xls", "xlsx", "csv"} or "document" in content_type:
        return "document"
    return "other"


def _serialize(doc, request):
    return {
        "id": str(doc.id),
        "contract_id": str(doc.contract_id),
        "upload_id": str(doc.upload_id),
        "file_url": None if file_content_prohibited(request) else document_delivery_url(doc),
        "file_name": doc.upload.file_name,
        "file_type": doc.upload.file_type,
        "file_size": doc.upload.file_size,
        "attached_by_id": doc.attached_by_id,
        "title": doc.title,
        "description": doc.description,
        "is_proof": doc.is_proof,
        "attached_at": doc.attached_at,
    }


class ContractDocumentListCreateAPIView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    """
    GET  /api/contracts/<contract_id>/documents/
    POST /api/contracts/<contract_id>/documents/
    """

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        docs = ContractDocument.objects.filter(contract=contract).select_related("upload")
        return Response([_serialize(d, request) for d in docs])

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        upload_id = request.data.get("upload_id")
        file = request.FILES.get("file")
        if upload_id and file:
            return Response({"error": "Provide either upload_id or file, not both."}, status=status.HTTP_400_BAD_REQUEST)
        if not upload_id and not file:
            return Response({"error": "upload_id or file is required"}, status=status.HTTP_400_BAD_REQUEST)

        title = request.data.get("title", "").strip()
        if not title:
            return Response({"error": "title is required"}, status=status.HTTP_400_BAD_REQUEST)

        if file:
            try:
                upload = create_managed_upload(
                    user=request.user,
                    file=file,
                    file_type=_file_type_from_upload_request(file, request.data.get("file_type", "")),
                    related_contract_id=contract.id,
                )
            except ValidationError:
                return Response(
                    {"error": "Invalid file size.", "code": "invalid_file_size"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except StorageAdmissionRejected as exc:
                return _storage_capacity_response(exc.check)
        else:
            upload = None

        description = request.data.get("description", "")
        is_proof = request.data.get("is_proof", False)
        if isinstance(is_proof, str):
            is_proof = is_proof.lower() in ("true", "1", "yes")

        try:
            doc = attach_upload(
                request.user, contract.pk, upload.pk if upload is not None else upload_id,
                title=title, description=description, is_proof=bool(is_proof),
            )
        except (Upload.DoesNotExist, ValidationError, ValueError, TypeError):
            return Response({"error": "Upload not found."}, status=status.HTTP_404_NOT_FOUND)
        except Contract.DoesNotExist:
            raise Http404("Contract not found.")

        return Response(_serialize(doc, request), status=status.HTTP_201_CREATED)


class ContractDocumentDeleteAPIView(APIView):
    """
    DELETE /api/contracts/<contract_id>/documents/<doc_id>/
    """

    def delete(self, request, contract_id, doc_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        try:
            detach_document(request.user, contract.pk, doc_id)
        except (Contract.DoesNotExist, ContractDocument.DoesNotExist):
            raise Http404("Document not found.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContractDocumentDeliveryAPIView(DeliveryPrivacyMixin, APIView):
    def get(self, request, contract_id, doc_id):
        require_file_content_access(request)
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()
        document = get_object_or_404(
            ContractDocument.objects.select_related("upload__stored_object"),
            pk=doc_id, contract=contract,
        )
        return deliver_upload(request, document.upload)
