# backend/api/contracts/document_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import Contract
from backend.documents.models import ContractDocument
from backend.uploads.models import Upload
from .permissions import contract_party_response, is_party


def _serialize(doc):
    return {
        "id": str(doc.id),
        "contract_id": str(doc.contract_id),
        "upload_id": str(doc.upload_id),
        "file_url": doc.upload.file_url,
        "file_name": doc.upload.file_name,
        "file_type": doc.upload.file_type,
        "attached_by_id": doc.attached_by_id,
        "title": doc.title,
        "description": doc.description,
        "is_proof": doc.is_proof,
        "attached_at": doc.attached_at,
    }


class ContractDocumentListCreateAPIView(APIView):
    """
    GET  /api/contracts/<contract_id>/documents/
    POST /api/contracts/<contract_id>/documents/
    """

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        docs = ContractDocument.objects.filter(contract=contract).select_related("upload")
        return Response([_serialize(d) for d in docs])

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        upload_id = request.data.get("upload_id")
        if not upload_id:
            return Response({"error": "upload_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        title = request.data.get("title", "").strip()
        if not title:
            return Response({"error": "title is required"}, status=status.HTTP_400_BAD_REQUEST)

        upload = get_object_or_404(Upload, pk=upload_id)

        description = request.data.get("description", "")
        is_proof = request.data.get("is_proof", False)
        if isinstance(is_proof, str):
            is_proof = is_proof.lower() in ("true", "1", "yes")

        doc = ContractDocument.objects.create(
            contract=contract,
            upload=upload,
            attached_by=request.user,
            title=title,
            description=description,
            is_proof=bool(is_proof),
        )

        return Response(_serialize(doc), status=status.HTTP_201_CREATED)


class ContractDocumentDeleteAPIView(APIView):
    """
    DELETE /api/contracts/<contract_id>/documents/<doc_id>/
    """

    def delete(self, request, contract_id, doc_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        doc = get_object_or_404(ContractDocument, pk=doc_id, contract=contract)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
