# backend/api/tests/test_documents.py
#
# Tests for the Documents domain:
#   POST   /api/contracts/<id>/documents/        attach upload to contract
#   GET    /api/contracts/<id>/documents/        list attached documents
#   DELETE /api/contracts/<id>/documents/<doc>/  detach (upload untouched)

import uuid
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from backend.billing.models import StorageCapacityGrantOrigin
from backend.billing.storage import create_storage_capacity_grant, get_storage_capacity_snapshot
from backend.documents.models import ContractDocument
from backend.uploads.models import StoredObject, Upload, UserObjectAccess
from backend.uploads.services import create_stored_object_metadata, grant_user_object_access
from .helpers import authed_client, make_contract, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def grant_capacity(user, capacity_bytes):
    return create_storage_capacity_grant(
        user=user,
        capacity_bytes=capacity_bytes,
        origin=StorageCapacityGrantOrigin.OPERATOR_ADJUSTMENT,
        reason="test capacity",
    )


def pdf_upload(name="contract-device.pdf", content=b"%PDF-1.4 test contract"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def make_canonical_upload(
    user,
    *,
    name="file.pdf",
    key="uploads/canonical/file.pdf",
    size=1024,
    file_type="pdf",
    content_type="application/pdf",
    file_url="https://example.com/file.pdf",
):
    stored_object = create_stored_object_metadata(
        backend="default",
        bucket="test-bucket",
        object_key=key,
        size_bytes=size,
        content_type=content_type,
    )
    grant_user_object_access(user, stored_object)
    return Upload.objects.create(
        user=user,
        file_url=file_url,
        file_name=name,
        file_type=file_type,
        file_size=size,
        storage_key=key,
        stored_object=stored_object,
    )


def make_upload(user, file_type="pdf"):
    return Upload.objects.create(
        user=user,
        file_url="https://example.com/file.pdf",
        file_name="file.pdf",
        file_type=file_type,
        file_size=1024,
        storage_key="",
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
        self.assertEqual(r.data["file_size"], self.upload.file_size)

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
                      "file_type", "file_size", "attached_by_id", "title", "description",
                      "is_proof", "attached_at"):
            self.assertIn(field, item, f"Missing field: {field}")

    def test_list_uses_dynamic_upload_url_when_storage_key_exists(self):
        self.upload.storage_key = "uploads/example/file.pdf"
        self.upload.file_url = "https://old-provider.example/stale.pdf"
        self.upload.save(update_fields=["storage_key", "file_url"])
        attach_doc(self.contract, self.upload, self.initiator, "Dynamic URL")

        with patch("backend.uploads.services.default_storage") as mock_storage:
            mock_storage.url.return_value = "https://current-provider.example/uploads/example/file.pdf"
            r = self.client.get(doc_url(self.contract.id))

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data[0]["file_url"],
            f"/api/contracts/{self.contract.pk}/documents/{r.data[0]['id']}/delivery/",
        )
        mock_storage.url.assert_not_called()

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


class ContractDocumentDeviceUploadVaultIntegrationTests(TestCase):

    def setUp(self):
        self.initiator = make_user("init_doc_device", "init_doc_device@example.com")
        self.counterparty = make_user("cp_doc_device", "cp_doc_device@example.com")
        self.stranger = make_user("stranger_doc_device", "stranger_doc_device@example.com")
        self.contract = make_contract(self.initiator, self.counterparty.email)
        self.client = authed_client(self.initiator)
        grant_capacity(self.initiator, 1024 * 1024)

    def _post_file(self, client=None, contract=None, uploaded_file=None, **data):
        uploaded_file = uploaded_file or pdf_upload(content=b"device bytes")
        payload = {
            "file": uploaded_file,
            "file_type": "pdf",
            "title": uploaded_file.name,
        }
        payload.update(data)
        return (client or self.client).post(
            doc_url((contract or self.contract).id),
            payload,
            format="multipart",
        )

    @patch("backend.uploads.services.default_storage")
    def test_authorized_device_upload_creates_one_canonical_vault_object(self, mock_storage):
        content = b"device contract bytes"
        mock_storage.save.return_value = "uploads/device/contract.pdf"
        mock_storage.url.return_value = "https://current-provider.example/uploads/device/contract.pdf"
        before = get_storage_capacity_snapshot(self.initiator)

        response = self._post_file(uploaded_file=pdf_upload(content=content), is_proof="true", description="Device contract")

        self.assertEqual(response.status_code, 201)
        upload = Upload.objects.get(pk=response.data["upload_id"])
        doc = ContractDocument.objects.get(pk=response.data["id"])
        self.assertEqual(doc.upload, upload)
        self.assertEqual(doc.contract, self.contract)
        self.assertEqual(doc.attached_by, self.initiator)
        self.assertTrue(doc.is_proof)
        self.assertEqual(doc.description, "Device contract")
        self.assertIsNotNone(upload.stored_object_id)
        self.assertEqual(StoredObject.objects.count(), 1)
        self.assertEqual(upload.stored_object.object_key, "uploads/device/contract.pdf")
        self.assertEqual(upload.stored_object.size_bytes, len(content))
        self.assertEqual(upload.related_contract_id, self.contract.id)
        self.assertEqual(
            UserObjectAccess.objects.filter(
                user=self.initiator,
                stored_object=upload.stored_object,
                is_active=True,
                is_visible=True,
                counts_toward_quota=True,
            ).count(),
            1,
        )
        after = get_storage_capacity_snapshot(self.initiator)
        self.assertEqual(after.used_bytes, before.used_bytes + len(content))
        vault_response = self.client.get("/api/uploads/")
        self.assertEqual(vault_response.status_code, 200)
        self.assertIn(str(upload.id), [item["id"] for item in vault_response.data])
        mock_storage.save.assert_called_once()
        mock_storage.open.assert_not_called()
        mock_storage.delete.assert_not_called()

    @patch("backend.uploads.services.default_storage")
    def test_unauthorized_contract_user_cannot_device_upload(self, mock_storage):
        response = self._post_file(client=authed_client(self.stranger))

        self.assertEqual(response.status_code, 403)
        mock_storage.save.assert_not_called()
        self.assertEqual(StoredObject.objects.count(), 0)
        self.assertEqual(UserObjectAccess.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), 0)
        self.assertEqual(ContractDocument.objects.count(), 0)

    @patch("backend.uploads.services.default_storage")
    def test_cross_user_upload_id_attack_is_rejected_for_canonical_upload(self, mock_storage):
        other_upload = make_upload(self.counterparty)
        response = self.client.post(
            doc_url(self.contract.id),
            {"upload_id": str(other_upload.id), "title": "Wrong user"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        mock_storage.save.assert_not_called()
        self.assertEqual(ContractDocument.objects.count(), 0)

    @patch("backend.uploads.services.default_storage")
    def test_quota_rejection_prevents_storage_write(self, mock_storage):
        limited = make_user("limited_doc_device", "limited_doc_device@example.com")
        contract = make_contract(limited, self.counterparty.email)
        client = authed_client(limited)
        grant_capacity(limited, 4)

        response = self._post_file(
            client=client,
            contract=contract,
            uploaded_file=pdf_upload(content=b"12345"),
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data["code"], "storage_capacity_exceeded")
        mock_storage.save.assert_not_called()
        self.assertEqual(StoredObject.objects.count(), 0)
        self.assertEqual(UserObjectAccess.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), 0)
        self.assertEqual(ContractDocument.objects.count(), 0)

    @patch("backend.uploads.services.default_storage")
    def test_canonical_upload_failure_cleans_provider_object_and_leaves_no_db_records(self, mock_storage):
        mock_storage.save.return_value = "uploads/device/failure.pdf"
        mock_storage.url.return_value = "https://current-provider.example/uploads/device/failure.pdf"

        with patch("backend.uploads.services.Upload.objects.create", side_effect=RuntimeError("db failed")):
            with self.assertRaisesMessage(RuntimeError, "db failed"):
                self._post_file()

        mock_storage.delete.assert_called_once_with("uploads/device/failure.pdf")
        self.assertEqual(StoredObject.objects.count(), 0)
        self.assertEqual(UserObjectAccess.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), 0)
        self.assertEqual(ContractDocument.objects.count(), 0)

    @patch("backend.uploads.services.default_storage")
    def test_contract_document_failure_preserves_committed_vault_upload(self, mock_storage):
        mock_storage.save.return_value = "uploads/device/kept.pdf"
        mock_storage.url.return_value = "https://current-provider.example/uploads/device/kept.pdf"

        with patch("backend.api.contracts.document_views.ContractDocument.objects.create", side_effect=RuntimeError("document failed")):
            with self.assertRaisesMessage(RuntimeError, "document failed"):
                self._post_file()

        upload = Upload.objects.get()
        self.assertIsNotNone(upload.stored_object_id)
        self.assertEqual(StoredObject.objects.count(), 1)
        self.assertEqual(UserObjectAccess.objects.count(), 1)
        mock_storage.delete.assert_not_called()
        vault_response = self.client.get("/api/uploads/")
        self.assertEqual(vault_response.status_code, 200)
        self.assertEqual(vault_response.data[0]["id"], str(upload.id))
        self.assertEqual(ContractDocument.objects.count(), 0)

    @patch("backend.uploads.services.default_storage")
    def test_legacy_upload_id_attach_remains_compatible(self, mock_storage):
        legacy_upload = make_upload(self.initiator)

        response = self.client.post(
            doc_url(self.contract.id),
            {"upload_id": str(legacy_upload.id), "title": "Legacy attach"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        doc = ContractDocument.objects.get(pk=response.data["id"])
        self.assertEqual(doc.upload, legacy_upload)
        self.assertIsNone(legacy_upload.stored_object_id)
        mock_storage.save.assert_not_called()
        mock_storage.delete.assert_not_called()


class ContractDocumentVaultSelectionTests(TestCase):

    def setUp(self):
        self.initiator = make_user("init_doc_vault", "init_doc_vault@example.com")
        self.counterparty = make_user("cp_doc_vault", "cp_doc_vault@example.com")
        self.stranger = make_user("stranger_doc_vault", "stranger_doc_vault@example.com")
        self.contract = make_contract(self.initiator, self.counterparty.email)
        self.other_contract = make_contract(self.initiator, make_user("cp_doc_vault_other", "cp_doc_vault_other@example.com").email)
        self.client = authed_client(self.initiator)
        grant_capacity(self.initiator, 1024 * 1024)

    def _post_vault_attachment(self, upload, *, client=None, contract=None, title="Vault Attachment", **data):
        payload = {"upload_id": str(upload.id), "source": "vault", "title": title}
        payload.update(data)
        return (client or self.client).post(
            doc_url((contract or self.contract).id),
            payload,
            format="json",
        )

    @patch("backend.uploads.services.default_storage")
    def test_authorized_user_can_choose_active_canonical_vault_file(self, mock_storage):
        upload = make_canonical_upload(
            self.initiator,
            name="vault-receipt.pdf",
            key="uploads/canonical/vault-receipt.pdf",
            size=5 * 1024 * 1024,
            file_url="https://example.com/vault-receipt.pdf",
        )
        before = get_storage_capacity_snapshot(self.initiator)
        mock_storage.url.return_value = "https://current-provider.example/uploads/canonical/vault-receipt.pdf"

        with patch("backend.api.contracts.document_views.create_managed_upload", side_effect=AssertionError("vault selection must not create a managed upload")) as mock_create_managed_upload:
            response = self._post_vault_attachment(upload, title="Vault Receipt")

        self.assertEqual(response.status_code, 201)
        mock_create_managed_upload.assert_not_called()
        doc = ContractDocument.objects.get(pk=response.data["id"])
        self.assertEqual(doc.upload, upload)
        self.assertEqual(doc.contract, self.contract)
        self.assertEqual(doc.title, "Vault Receipt")
        self.assertEqual(StoredObject.objects.count(), 1)
        self.assertEqual(UserObjectAccess.objects.count(), 1)
        self.assertEqual(Upload.objects.count(), 1)
        self.assertEqual(get_storage_capacity_snapshot(self.initiator).used_bytes, before.used_bytes)
        self.assertEqual(upload.related_contract_id, None)
        mock_storage.save.assert_not_called()
        mock_storage.open.assert_not_called()
        mock_storage.delete.assert_not_called()

    @patch("backend.uploads.services.default_storage")
    def test_same_vault_object_can_be_referenced_by_second_contract_zero_quota(self, mock_storage):
        upload = make_canonical_upload(
            self.initiator,
            name="shared-vault.pdf",
            key="uploads/canonical/shared-vault.pdf",
            size=2048,
            file_url="https://example.com/shared-vault.pdf",
        )
        other_contract = self.other_contract
        before = get_storage_capacity_snapshot(self.initiator)
        mock_storage.url.return_value = "https://current-provider.example/uploads/canonical/shared-vault.pdf"

        with patch("backend.api.contracts.document_views.create_managed_upload", side_effect=AssertionError("vault selection must not create a managed upload")) as mock_create_managed_upload:
            first = self._post_vault_attachment(upload, contract=self.contract, title="Shared One")
            second = self._post_vault_attachment(upload, contract=other_contract, title="Shared Two")

        self.assertEqual(first.status_code, 201)
        mock_create_managed_upload.assert_not_called()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(ContractDocument.objects.filter(upload=upload).count(), 2)
        self.assertEqual(StoredObject.objects.count(), 1)
        self.assertEqual(UserObjectAccess.objects.count(), 1)
        self.assertEqual(Upload.objects.count(), 1)
        self.assertEqual(get_storage_capacity_snapshot(self.initiator).used_bytes, before.used_bytes)
        mock_storage.save.assert_not_called()
        mock_storage.open.assert_not_called()
        mock_storage.delete.assert_not_called()

    @patch("backend.uploads.services.default_storage")
    def test_cross_user_upload_id_attack_is_rejected_on_vault_path(self, mock_storage):
        other_upload = make_canonical_upload(
            self.counterparty,
            name="other-user.pdf",
            key="uploads/canonical/other-user.pdf",
            size=1024,
            file_url="https://example.com/other-user.pdf",
        )

        response = self._post_vault_attachment(other_upload)

        self.assertEqual(response.status_code, 404)
        mock_storage.save.assert_not_called()
        mock_storage.url.assert_not_called()
        self.assertEqual(ContractDocument.objects.count(), 0)

    @patch("backend.uploads.services.default_storage")
    def test_inactive_user_object_access_cannot_be_selected_through_vault_path(self, mock_storage):
        upload = make_canonical_upload(
            self.initiator,
            name="inactive-vault.pdf",
            key="uploads/canonical/inactive-vault.pdf",
            size=1024,
            file_url="https://example.com/inactive-vault.pdf",
        )
        upload.stored_object.user_accesses.filter(user=self.initiator).update(is_active=False, is_visible=False)

        response = self._post_vault_attachment(upload)

        self.assertEqual(response.status_code, 404)
        mock_storage.save.assert_not_called()
        mock_storage.url.assert_not_called()
        self.assertEqual(ContractDocument.objects.count(), 0)

    @patch("backend.uploads.services.default_storage")
    def test_reference_safe_removal_preserves_document_and_blocks_vault_selection(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/canonical/referenced-vault.pdf"
        upload = make_canonical_upload(
            self.initiator,
            name="referenced-vault.pdf",
            key="uploads/canonical/referenced-vault.pdf",
            size=5 * 1024 * 1024,
            file_url="https://example.com/referenced-vault.pdf",
        )
        create_response = self._post_vault_attachment(upload, title="Referenced Vault")
        self.assertEqual(create_response.status_code, 201)
        before = get_storage_capacity_snapshot(self.initiator)

        delete_response = self.client.delete(f"/api/uploads/{upload.id}/")
        doc_list = self.client.get(doc_url(self.contract.id))
        vault_list = self.client.get(f"/api/uploads/?canonical=true")
        vault_attach = self._post_vault_attachment(upload, title="Hidden Vault")

        self.assertEqual(delete_response.status_code, 204)
        self.assertEqual(doc_list.status_code, 200)
        self.assertEqual([item["id"] for item in doc_list.data], [create_response.data["id"]])
        self.assertEqual(vault_list.status_code, 200)
        self.assertEqual(vault_list.data, [])
        self.assertEqual(vault_attach.status_code, 404)
        self.assertEqual(get_storage_capacity_snapshot(self.initiator).used_bytes, before.used_bytes)
        doc = ContractDocument.objects.get(pk=create_response.data["id"])
        self.assertEqual(doc.upload_id, upload.id)
        self.assertTrue(Upload.objects.filter(pk=upload.id).exists())
        self.assertTrue(StoredObject.objects.filter(pk=upload.stored_object_id).exists())
        access = upload.stored_object.user_accesses.get(user=self.initiator)
        self.assertTrue(access.is_active)
        self.assertFalse(access.is_visible)
        self.assertTrue(access.counts_toward_quota)
        self.assertIsNotNone(access.removed_at)
        mock_storage.delete.assert_not_called()

    @patch("backend.uploads.services.default_storage")
    def test_unauthorized_contract_user_cannot_attach_vault_file(self, mock_storage):
        upload = make_canonical_upload(
            self.initiator,
            name="party-only.pdf",
            key="uploads/canonical/party-only.pdf",
            size=1024,
            file_url="https://example.com/party-only.pdf",
        )

        response = self._post_vault_attachment(upload, client=authed_client(self.stranger))

        self.assertEqual(response.status_code, 403)
        mock_storage.save.assert_not_called()
        mock_storage.url.assert_not_called()
        self.assertEqual(ContractDocument.objects.count(), 0)
