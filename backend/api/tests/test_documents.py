# backend/api/tests/test_documents.py
#
# Tests for the Documents domain:
#   POST   /api/contracts/<id>/documents/        attach upload to contract
#   GET    /api/contracts/<id>/documents/        list attached documents
#   DELETE /api/contracts/<id>/documents/<doc>/  detach (upload untouched)

import uuid

from django.test import TestCase

from backend.documents.models import ContractDocument
from backend.uploads.models import Upload
from .helpers import authed_client, make_contract, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_upload(user, file_type="pdf"):
    return Upload.objects.create(
        user=user,
        file_url="https://example.com/file.pdf",
        file_name="file.pdf",
        file_type=file_type,
        file_size=1024,
        storage_key="uploads/1/abc/file.pdf",
    )


def attach_doc(contract, upload, attached_by, title="Contract Doc", is_proof=False):
    return ContractDocument.objects.create(
        contract=contract,
        upload=upload,
        attached_by=attached_by,
        title=title,
        is_proof=is_proof,
    )


def doc_url(contract_id):
    return f"/api/contracts/{contract_id}/documents/"


def doc_detail_url(contract_id, doc_id):
    return f"/api/contracts/{contract_id}/documents/{doc_id}/"


# ---------------------------------------------------------------------------
# POST — attach document
# ---------------------------------------------------------------------------

class AttachDocumentTests(TestCase):

    def setUp(self):
        self.initiator = make_user("init_doc", "init_doc@example.com")
        self.counterparty = make_user("cp_doc", "cp_doc@example.com")
        self.stranger = make_user("stranger_doc", "stranger_doc@example.com")
        self.contract = make_contract(self.initiator, self.counterparty.email)
        self.upload = make_upload(self.initiator)
        self.client = authed_client(self.initiator)

    def test_initiator_can_attach_document(self):
        r = self.client.post(
            doc_url(self.contract.id),
            {"upload_id": str(self.upload.id), "title": "Signed Agreement"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["title"], "Signed Agreement")
        self.assertEqual(r.data["upload_id"], str(self.upload.id))
        self.assertEqual(r.data["contract_id"], str(self.contract.id))
        self.assertEqual(r.data["attached_by_id"], self.initiator.pk)
        self.assertFalse(r.data["is_proof"])

    def test_counterparty_can_attach_document(self):
        client = authed_client(self.counterparty)
        upload = make_upload(self.counterparty)
        r = client.post(
            doc_url(self.contract.id),
            {"upload_id": str(upload.id), "title": "Counterparty Evidence"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["attached_by_id"], self.counterparty.pk)

    def test_stranger_cannot_attach_document(self):
        client = authed_client(self.stranger)
        r = client.post(
            doc_url(self.contract.id),
            {"upload_id": str(self.upload.id), "title": "Sneaky Doc"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertFalse(ContractDocument.objects.filter(contract=self.contract).exists())

    def test_attach_missing_upload_id_returns_400(self):
        r = self.client.post(
            doc_url(self.contract.id),
            {"title": "No Upload"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("upload_id", r.data["error"])

    def test_attach_missing_title_returns_400(self):
        r = self.client.post(
            doc_url(self.contract.id),
            {"upload_id": str(self.upload.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.data["error"])

    def test_attach_nonexistent_upload_returns_404(self):
        r = self.client.post(
            doc_url(self.contract.id),
            {"upload_id": str(uuid.uuid4()), "title": "Ghost"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_attach_nonexistent_contract_returns_404(self):
        r = self.client.post(
            doc_url(uuid.uuid4()),
            {"upload_id": str(self.upload.id), "title": "No Contract"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_attach_with_is_proof_flag(self):
        r = self.client.post(
            doc_url(self.contract.id),
            {"upload_id": str(self.upload.id), "title": "Proof Doc", "is_proof": True},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_proof"])
        doc = ContractDocument.objects.get(pk=r.data["id"])
        self.assertTrue(doc.is_proof)

    def test_attach_with_description(self):
        r = self.client.post(
            doc_url(self.contract.id),
            {
                "upload_id": str(self.upload.id),
                "title": "Full Doc",
                "description": "This is the signed PDF.",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["description"], "This is the signed PDF.")

    def test_response_includes_file_url_and_name(self):
        r = self.client.post(
            doc_url(self.contract.id),
            {"upload_id": str(self.upload.id), "title": "Check Fields"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("file_url", r.data)
        self.assertIn("file_name", r.data)
        self.assertIn("file_type", r.data)

    def test_party_cannot_attach_upload_owned_by_other_user(self):
        # counterparty is a valid contract party but self.upload belongs to the initiator
        client = authed_client(self.counterparty)
        r = client.post(
            doc_url(self.contract.id),
            {"upload_id": str(self.upload.id), "title": "Stolen Doc"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)
        self.assertFalse(ContractDocument.objects.filter(contract=self.contract).exists())

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().post(
            doc_url(self.contract.id),
            {"upload_id": str(self.upload.id), "title": "Anon"},
            format="json",
        )
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# GET — list documents
# ---------------------------------------------------------------------------

class ListDocumentsTests(TestCase):

    def setUp(self):
        self.initiator = make_user("init_list", "init_list@example.com")
        self.counterparty = make_user("cp_list", "cp_list@example.com")
        self.stranger = make_user("stranger_list", "stranger_list@example.com")
        self.contract = make_contract(self.initiator, self.counterparty.email)
        self.upload = make_upload(self.initiator)
        self.client = authed_client(self.initiator)

    def test_list_empty_when_no_documents(self):
        r = self.client.get(doc_url(self.contract.id))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_list_returns_attached_documents(self):
        attach_doc(self.contract, self.upload, self.initiator, "Doc A")
        attach_doc(self.contract, self.upload, self.initiator, "Doc B")
        r = self.client.get(doc_url(self.contract.id))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_counterparty_can_list_documents(self):
        attach_doc(self.contract, self.upload, self.initiator, "Shared Doc")
        r = authed_client(self.counterparty).get(doc_url(self.contract.id))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_stranger_cannot_list_documents(self):
        attach_doc(self.contract, self.upload, self.initiator, "Private")
        r = authed_client(self.stranger).get(doc_url(self.contract.id))
        self.assertEqual(r.status_code, 403)

    def test_list_does_not_include_other_contracts_documents(self):
        other_cp = make_user("other_cp_list", "other_cp_list@example.com")
        other_contract = make_contract(self.initiator, other_cp.email)
        other_upload = make_upload(self.initiator)
        attach_doc(other_contract, other_upload, self.initiator, "Other Contract Doc")
        attach_doc(self.contract, self.upload, self.initiator, "This Contract Doc")

        r = self.client.get(doc_url(self.contract.id))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["title"], "This Contract Doc")

    def test_list_item_has_expected_fields(self):
        attach_doc(self.contract, self.upload, self.initiator, "Field Check")
        r = self.client.get(doc_url(self.contract.id))
        item = r.data[0]
        for field in ("id", "contract_id", "upload_id", "file_url", "file_name",
                      "file_type", "attached_by_id", "title", "description",
                      "is_proof", "attached_at"):
            self.assertIn(field, item, f"Missing field: {field}")

    def test_list_nonexistent_contract_returns_404(self):
        r = self.client.get(doc_url(uuid.uuid4()))
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# DELETE — detach document
# ---------------------------------------------------------------------------

class DetachDocumentTests(TestCase):

    def setUp(self):
        self.initiator = make_user("init_del", "init_del@example.com")
        self.counterparty = make_user("cp_del", "cp_del@example.com")
        self.stranger = make_user("stranger_del", "stranger_del@example.com")
        self.contract = make_contract(self.initiator, self.counterparty.email)
        self.upload = make_upload(self.initiator)
        self.client = authed_client(self.initiator)

    def test_initiator_can_detach_document(self):
        doc = attach_doc(self.contract, self.upload, self.initiator, "Remove Me")
        r = self.client.delete(doc_detail_url(self.contract.id, doc.id))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(ContractDocument.objects.filter(pk=doc.id).exists())

    def test_counterparty_can_detach_document(self):
        doc = attach_doc(self.contract, self.upload, self.initiator, "CP Removes")
        r = authed_client(self.counterparty).delete(doc_detail_url(self.contract.id, doc.id))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(ContractDocument.objects.filter(pk=doc.id).exists())

    def test_stranger_cannot_detach_document(self):
        doc = attach_doc(self.contract, self.upload, self.initiator, "Protected")
        r = authed_client(self.stranger).delete(doc_detail_url(self.contract.id, doc.id))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(ContractDocument.objects.filter(pk=doc.id).exists())

    def test_detach_nonexistent_doc_returns_404(self):
        r = self.client.delete(doc_detail_url(self.contract.id, uuid.uuid4()))
        self.assertEqual(r.status_code, 404)

    def test_detach_doc_on_wrong_contract_returns_404(self):
        other_cp = make_user("other_cp_del", "other_cp_del@example.com")
        other_contract = make_contract(self.initiator, other_cp.email)
        other_upload = make_upload(self.initiator)
        doc = attach_doc(other_contract, other_upload, self.initiator, "Wrong Contract")
        # Doc belongs to other_contract — using self.contract.id should 404
        r = self.client.delete(doc_detail_url(self.contract.id, doc.id))
        self.assertEqual(r.status_code, 404)

    def test_detach_does_not_delete_upload(self):
        doc = attach_doc(self.contract, self.upload, self.initiator, "Keep Upload")
        self.client.delete(doc_detail_url(self.contract.id, doc.id))
        self.assertFalse(ContractDocument.objects.filter(pk=doc.id).exists())
        self.assertTrue(Upload.objects.filter(pk=self.upload.id).exists())

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        doc = attach_doc(self.contract, self.upload, self.initiator, "Auth Check")
        r = APIClient().delete(doc_detail_url(self.contract.id, doc.id))
        self.assertEqual(r.status_code, 401)
