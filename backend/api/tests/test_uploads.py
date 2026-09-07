# backend/api/tests/test_uploads.py
#
# Tests for the Uploads domain:
#   - POST /api/uploads/    upload a file, get back file_url + record
#   - GET  /api/uploads/    list own uploads, ?contract_id and ?session_id filters
#   - DELETE /api/uploads/<id>/   removes the record (and would delete from storage)

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from backend.billing.models import StorageCapacityGrantOrigin, StorageEntitlement
from backend.billing.storage import (
    create_storage_capacity_grant,
    get_storage_capacity_snapshot,
    get_user_active_storage_usage_bytes,
)
from backend.documents.models import ContractDocument
from backend.uploads.models import StoredObject, Upload, UserObjectAccess, VaultEmailDelivery, VaultFolder, VaultShare
from backend.uploads.services import create_stored_object_metadata, grant_user_object_access
from .helpers import authed_client, make_contract, make_user

UPLOAD_URL = "/api/uploads/"

_MOCK_KEY = "uploads/1/abc/test.pdf"
_MOCK_FILE_URL = "https://current-provider.example/uploads/1/abc/test.pdf"


def _patched_storage(save_key=_MOCK_KEY, file_url=_MOCK_FILE_URL):
    """Return a mock that stands in for django.core.files.storage.default_storage."""
    mock = MagicMock()
    mock.save.return_value = save_key
    mock.url.return_value = file_url
    return mock


def _pdf(name="test.pdf", content=b"%PDF-1.4 fake content"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def _grant_capacity(user, capacity_bytes):
    return create_storage_capacity_grant(
        user=user,
        capacity_bytes=capacity_bytes,
        origin=StorageCapacityGrantOrigin.OPERATOR_ADJUSTMENT,
        reason="test capacity",
    )


def _managed_upload(
    user,
    *,
    name="file.pdf",
    key="uploads/managed/file.pdf",
    size=1024,
    file_type="pdf",
    content_type="application/pdf",
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
        file_url="https://example.com/file.pdf",
        file_name=name,
        file_type=file_type,
        file_size=size,
        storage_key=key,
        stored_object=stored_object,
    )


class UploadStorageSummaryTests(TestCase):
    def setUp(self):
        self.user = make_user("vault_summary", "vault_summary@example.com")
        self.client = authed_client(self.user)

    def test_authenticated_storage_summary_returns_authoritative_values(self):
        _grant_capacity(self.user, 10)
        _managed_upload(self.user, size=4)

        r = self.client.get(f"{UPLOAD_URL}storage/")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {
            "capacity_bytes": 10,
            "used_bytes": 4,
            "available_bytes": 6,
        })


class UploadCreateTests(TestCase):

    def setUp(self):
        self.user = make_user("uploader", "uploader@example.com")
        self.client = authed_client(self.user)
        _grant_capacity(self.user, 1024 * 1024)
        self.service_storage_patcher = patch("backend.uploads.services.default_storage")
        self.mock_service_storage = self.service_storage_patcher.start()
        self.addCleanup(self.service_storage_patcher.stop)
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

    def test_upload_creates_record(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(), "file_type": "pdf"},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["file_url"], _MOCK_FILE_URL)
        self.assertEqual(r.data["file_name"], "test.pdf")
        self.assertEqual(r.data["file_type"], "pdf")
        self.assertFalse(r.data["is_prep_material"])
        self.assertEqual(Upload.objects.filter(user=self.user).count(), 1)
        upload = Upload.objects.get(user=self.user)
        self.assertIsNotNone(upload.stored_object_id)
        self.assertEqual(upload.stored_object.object_key, _MOCK_KEY)
        self.assertEqual(upload.stored_object.size_bytes, upload.file_size)
        self.assertEqual(upload.stored_object.content_type, "application/pdf")
        self.assertEqual(get_user_active_storage_usage_bytes(self.user), upload.file_size)
        self.assertTrue(
            UserObjectAccess.objects.filter(
                user=self.user,
                stored_object=upload.stored_object,
                is_active=True,
                is_visible=True,
                counts_toward_quota=True,
            ).exists()
        )

    def test_upload_stores_correct_file_size(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(), "file_type": "pdf"},
            format="multipart",
        )
        upload = Upload.objects.get(user=self.user)
        self.assertGreater(upload.file_size, 0)
        self.assertEqual(r.data["file_size"], upload.file_size)
        self.assertEqual(upload.stored_object.size_bytes, upload.file_size)

    def test_upload_with_prep_material_flag(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(), "file_type": "pdf", "is_prep_material": "true"},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_prep_material"])
        upload = Upload.objects.get(user=self.user)
        self.assertTrue(upload.is_prep_material)

    def test_upload_with_contract_id(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL
        other = make_user("other_uc", "other_uc@example.com")
        contract = make_contract(self.user, other.email)

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(), "file_type": "pdf", "contract_id": str(contract.id)},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["related_contract"], str(contract.id))
        upload = Upload.objects.get(user=self.user)
        self.assertEqual(upload.related_contract_id, contract.id)

    def test_upload_missing_file_returns_400(self):
        r = self.client.post(UPLOAD_URL, {"file_type": "pdf"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("file", r.data["error"])

    def test_upload_invalid_file_type_returns_400(self):
        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(), "file_type": "exe"},
            format="multipart",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("file_type", r.data["error"])

    def test_upload_missing_file_type_returns_400(self):
        r = self.client.post(UPLOAD_URL, {"file": _pdf()}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_upload_all_valid_file_types(self):
        self.mock_service_storage.save.side_effect = [f"uploads/1/abc/file.{ft}" for ft in ("pdf", "image", "video", "audio", "slides", "document", "other")]
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        for ft in ("pdf", "image", "video", "audio", "slides", "document", "other"):
            r = self.client.post(
                UPLOAD_URL,
                {"file": _pdf(f"file.{ft}"), "file_type": ft},
                format="multipart",
            )
            self.assertEqual(r.status_code, 201, f"Expected 201 for file_type={ft}")

    def test_upload_exactly_filling_remaining_capacity_succeeds(self):
        exact_user = make_user("uploader_exact", "uploader_exact@example.com")
        client = authed_client(exact_user)
        content = b"12345"
        _grant_capacity(exact_user, len(content))
        self.mock_service_storage.save.return_value = "uploads/exact/file.pdf"
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        r = client.post(UPLOAD_URL, {"file": _pdf(content=content), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 201)
        self.assertEqual(get_user_active_storage_usage_bytes(exact_user), len(content))

    def test_upload_one_byte_over_remaining_capacity_is_rejected_before_storage(self):
        limited_user = make_user("uploader_limited", "uploader_limited@example.com")
        client = authed_client(limited_user)
        _grant_capacity(limited_user, 4)

        r = client.post(UPLOAD_URL, {"file": _pdf(content=b"12345"), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.data["code"], "storage_capacity_exceeded")
        self.assertEqual(r.data["capacity_bytes"], 4)
        self.assertEqual(r.data["used_bytes"], 0)
        self.assertEqual(r.data["available_bytes"], 4)
        self.assertEqual(r.data["incoming_bytes"], 5)
        self.mock_service_storage.save.assert_not_called()
        self.assertFalse(StoredObject.objects.filter(user_accesses__user=limited_user).exists())
        self.assertFalse(UserObjectAccess.objects.filter(user=limited_user).exists())
        self.assertFalse(Upload.objects.filter(user=limited_user).exists())

    def test_server_side_uploaded_size_is_used_instead_of_client_file_size(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(content=b"trusted"), "file_type": "pdf", "file_size": "999999"},
            format="multipart",
        )

        self.assertEqual(r.status_code, 201)
        upload = Upload.objects.get(user=self.user)
        self.assertEqual(upload.file_size, len(b"trusted"))
        self.assertEqual(upload.stored_object.size_bytes, len(b"trusted"))

    def test_stored_object_uses_actual_key_returned_by_storage_save(self):
        actual_key = "uploads/actual/renamed-by-storage.pdf"
        self.mock_service_storage.save.return_value = actual_key
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 201)
        upload = Upload.objects.get(user=self.user)
        self.assertEqual(upload.storage_key, actual_key)
        self.assertEqual(upload.stored_object.object_key, actual_key)

    def test_upload_response_uses_dynamic_provider_independent_url(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.side_effect = [
            "https://legacy-write-url.example/file.pdf",
            "https://current-provider.example/dynamic/file.pdf",
        ]

        r = self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["file_url"], "https://current-provider.example/dynamic/file.pdf")
        self.assertEqual(self.mock_service_storage.url.call_count, 2)

    def test_database_failure_after_storage_save_cleans_up_new_object(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL

        with patch("backend.api.uploads.views.Upload.objects.create", side_effect=RuntimeError("db failed")):
            with self.assertRaisesMessage(RuntimeError, "db failed"):
                self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        self.mock_service_storage.delete.assert_called_once_with(_MOCK_KEY)
        self.assertEqual(StoredObject.objects.count(), 0)
        self.assertEqual(UserObjectAccess.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), 0)

    def test_cleanup_failure_does_not_mask_original_database_error(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL
        self.mock_service_storage.delete.side_effect = RuntimeError("cleanup failed")

        with patch("backend.api.uploads.views.Upload.objects.create", side_effect=RuntimeError("db failed")):
            with self.assertRaisesMessage(RuntimeError, "db failed"):
                self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        self.mock_service_storage.delete.assert_called_once_with(_MOCK_KEY)
        self.assertEqual(StoredObject.objects.count(), 0)
        self.assertEqual(UserObjectAccess.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), 0)

    def test_upload_does_not_manually_mutate_legacy_storage_usage_bytes(self):
        self.mock_service_storage.save.return_value = _MOCK_KEY
        self.mock_service_storage.url.return_value = _MOCK_FILE_URL
        StorageEntitlement.objects.create(user=self.user, capacity_bytes=1024 * 1024, usage_bytes=123)

        r = self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 201)
        self.assertEqual(StorageEntitlement.objects.get(user=self.user).usage_bytes, 123)

    def test_upload_view_does_not_import_boto3_or_provider_client(self):
        from pathlib import Path

        source = Path("backend/api/uploads/views.py").read_text()

        self.assertNotIn("boto3", source)
        self.assertNotIn("S3Boto3Storage", source)


class UploadListTests(TestCase):

    def setUp(self):
        self.user = make_user("lister", "lister@example.com")
        self.other = make_user("lister_other", "lister_other@example.com")
        self.client = authed_client(self.user)

    def _make_upload(self, user=None, **kwargs):
        u = user or self.user
        defaults = dict(
            file_url="https://example.com/file.pdf",
            file_name="file.pdf",
            file_type="pdf",
            file_size=1024,
            storage_key="",
        )
        defaults.update(kwargs)
        return Upload.objects.create(user=u, **defaults)

    def test_list_returns_own_uploads_only(self):
        self._make_upload()
        self._make_upload(user=self.other)
        r = self.client.get(UPLOAD_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_list_empty_when_no_uploads(self):
        r = self.client.get(UPLOAD_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_list_filter_by_contract_id(self):
        other_user = make_user("other_lfc", "other_lfc@example.com")
        contract = make_contract(self.user, other_user.email)
        self._make_upload(related_contract=contract)
        self._make_upload()  # no contract

        r = self.client.get(f"{UPLOAD_URL}?contract_id={contract.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["related_contract"], str(contract.id))

    def test_list_filter_by_nonexistent_contract_returns_empty(self):
        self._make_upload()
        r = self.client.get(f"{UPLOAD_URL}?contract_id={uuid.uuid4()}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_list_has_expected_fields(self):
        self._make_upload()
        r = self.client.get(UPLOAD_URL)
        self.assertEqual(r.status_code, 200)
        item = r.data[0]
        for field in ("id", "file_url", "file_name", "file_type", "file_size",
                      "related_contract", "related_session", "is_prep_material",
                      "is_draft_document", "uploaded_at"):
            self.assertIn(field, item, f"Missing field: {field}")

    @patch("backend.uploads.services.default_storage")
    def test_list_uses_dynamic_url_when_storage_key_exists(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/example/file.pdf"
        self._make_upload(
            storage_key="uploads/example/file.pdf",
            file_url="https://old-provider.example/stale.pdf",
        )

        r = self.client.get(UPLOAD_URL)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data[0]["file_url"],
            "https://current-provider.example/uploads/example/file.pdf",
        )
        mock_storage.url.assert_called_once_with("uploads/example/file.pdf")

    @patch("backend.uploads.services.default_storage")
    def test_list_falls_back_to_legacy_file_url_without_storage_key(self, mock_storage):
        self._make_upload(
            storage_key="",
            file_url="https://legacy-provider.example/file.pdf",
        )

        r = self.client.get(UPLOAD_URL)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]["file_url"], "https://legacy-provider.example/file.pdf")
        mock_storage.url.assert_not_called()

    def test_list_includes_active_canonical_uploads_for_user(self):
        upload = _managed_upload(self.user, key="uploads/list/active.pdf")

        r = self.client.get(UPLOAD_URL)

        self.assertEqual(r.status_code, 200)
        self.assertEqual([item["id"] for item in r.data], [str(upload.id)])
        self.assertEqual(r.data[0]["content_type"], "application/pdf")

    @patch("backend.uploads.services.default_storage")
    def test_list_canonical_filter_returns_only_active_canonical_uploads(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/list/canonical.pdf"
        canonical = _managed_upload(self.user, key="uploads/list/canonical.pdf")
        _managed_upload(self.other, key="uploads/list/other.pdf")
        legacy = self._make_upload(storage_key="", file_url="https://legacy-provider.example/file.pdf")
        removed = _managed_upload(self.user, key="uploads/list/removed.pdf")
        removed.stored_object.user_accesses.filter(user=self.user).update(is_active=False, is_visible=False)

        r = self.client.get(f"{UPLOAD_URL}?canonical=true")

        self.assertEqual(r.status_code, 200)
        self.assertEqual([item["id"] for item in r.data], [str(canonical.id)])
        self.assertEqual(r.data[0]["file_name"], canonical.file_name)
        self.assertNotIn(str(legacy.id), [item["id"] for item in r.data])
        mock_storage.url.assert_called_once_with("uploads/list/canonical.pdf")

    def test_list_excludes_another_users_canonical_upload(self):
        _managed_upload(self.other, key="uploads/list/other.pdf")

        r = self.client.get(UPLOAD_URL)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_list_excludes_removed_canonical_upload(self):
        upload = _managed_upload(self.user, key="uploads/list/removed.pdf")
        upload.stored_object.user_accesses.filter(user=self.user).update(is_active=False, is_visible=False)

        r = self.client.get(UPLOAD_URL)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_list_filter_by_is_draft_document_true(self):
        self._make_upload(is_draft_document=True)
        self._make_upload(is_draft_document=False)
        r = self.client.get(f"{UPLOAD_URL}?is_draft_document=true")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertTrue(r.data[0]["is_draft_document"])

    def test_list_filter_by_is_draft_document_false(self):
        self._make_upload(is_draft_document=True)
        self._make_upload(is_draft_document=False)
        r = self.client.get(f"{UPLOAD_URL}?is_draft_document=false")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertFalse(r.data[0]["is_draft_document"])

    def test_list_no_filter_returns_all(self):
        self._make_upload(is_draft_document=True)
        self._make_upload(is_draft_document=False)
        r = self.client.get(UPLOAD_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)


class VaultFolderTests(TestCase):

    def setUp(self):
        self.user = make_user("folder_owner", "folder_owner@example.com")
        self.other = make_user("folder_other", "folder_other@example.com")
        self.client = authed_client(self.user)
        self.upload = _managed_upload(self.user, name="folder-file.pdf", key="uploads/folders/file.pdf", size=4096)
        _grant_capacity(self.user, 10000)

    def test_user_cannot_view_or_manage_other_users_folders(self):
        other_folder = VaultFolder.objects.create(user=self.other, name="Other Folder")
        own_folder = VaultFolder.objects.create(user=self.user, name="Own Folder")

        list_response = self.client.get(f"{UPLOAD_URL}folders/")
        rename_response = self.client.patch(f"{UPLOAD_URL}folders/{other_folder.id}/", {"name": "Renamed"}, format="json")
        delete_response = self.client.delete(f"{UPLOAD_URL}folders/{other_folder.id}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.data], [str(own_folder.id)])
        self.assertEqual(rename_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        other_folder.refresh_from_db()
        self.assertEqual(other_folder.name, "Other Folder")

    def test_create_rename_and_move_nested_folders(self):
        root_response = self.client.post(f"{UPLOAD_URL}folders/", {"name": "Projects"}, format="json")
        child_response = self.client.post(
            f"{UPLOAD_URL}folders/",
            {"name": "Contracts", "parent_id": root_response.data["id"]},
            format="json",
        )
        target_response = self.client.post(f"{UPLOAD_URL}folders/", {"name": "Archive"}, format="json")

        rename_response = self.client.patch(
            f"{UPLOAD_URL}folders/{child_response.data['id']}/",
            {"name": "Signed Contracts"},
            format="json",
        )
        move_response = self.client.patch(
            f"{UPLOAD_URL}folders/{child_response.data['id']}/",
            {"parent_id": target_response.data["id"]},
            format="json",
        )
        list_response = self.client.get(f"{UPLOAD_URL}folders/")

        self.assertEqual(root_response.status_code, 201)
        self.assertIsNone(root_response.data["parent_id"])
        self.assertEqual(child_response.status_code, 201)
        self.assertEqual(child_response.data["parent_id"], root_response.data["id"])
        self.assertEqual(rename_response.status_code, 200)
        self.assertEqual(rename_response.data["name"], "Signed Contracts")
        self.assertEqual(move_response.status_code, 200)
        self.assertEqual(move_response.data["parent_id"], target_response.data["id"])
        self.assertEqual(list_response.status_code, 200)
        folders_by_id = {item["id"]: item for item in list_response.data}
        self.assertEqual(folders_by_id[child_response.data["id"]]["name"], "Signed Contracts")
        self.assertEqual(folders_by_id[child_response.data["id"]]["parent_id"], target_response.data["id"])

    def test_user_cannot_create_or_move_into_other_users_parent_folder(self):
        other_folder = VaultFolder.objects.create(user=self.other, name="Other Folder")

        create_response = self.client.post(f"{UPLOAD_URL}folders/", {"name": "Child", "parent_id": str(other_folder.id)}, format="json")
        move_folder_response = self.client.patch(f"{UPLOAD_URL}folders/{other_folder.id}/", {"parent_id": None}, format="json")

        self.assertEqual(create_response.status_code, 404)
        self.assertEqual(move_folder_response.status_code, 404)

    def test_user_cannot_move_file_into_other_users_folder(self):
        other_folder = VaultFolder.objects.create(user=self.other, name="Other Folder")

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/folder/", {"folder_id": str(other_folder.id)}, format="json")

        self.assertEqual(response.status_code, 404)
        self.upload.refresh_from_db()
        self.assertIsNone(self.upload.vault_folder_id)

    @patch("backend.uploads.services.default_storage")
    def test_moving_file_changes_only_folder_metadata(self, mock_storage):
        mock_storage.url.return_value = "https://example.com/folder-file.pdf"
        folder = VaultFolder.objects.create(user=self.user, name="Projects")
        upload_count = Upload.objects.count()
        object_count = StoredObject.objects.count()
        access_count = UserObjectAccess.objects.count()
        object_key = self.upload.stored_object.object_key
        stored_object_id = self.upload.stored_object_id
        quota_before = get_storage_capacity_snapshot(self.user).used_bytes

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/folder/", {"folder_id": str(folder.id)}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["folder_id"], str(folder.id))
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.vault_folder_id, folder.id)
        self.assertEqual(self.upload.stored_object_id, stored_object_id)
        self.assertEqual(self.upload.stored_object.object_key, object_key)
        self.assertEqual(Upload.objects.count(), upload_count)
        self.assertEqual(StoredObject.objects.count(), object_count)
        self.assertEqual(UserObjectAccess.objects.count(), access_count)
        self.assertEqual(get_storage_capacity_snapshot(self.user).used_bytes, quota_before)
        mock_storage.open.assert_not_called()
        mock_storage.save.assert_not_called()
        mock_storage.delete.assert_not_called()

    def test_moving_file_back_to_vault_root(self):
        folder = VaultFolder.objects.create(user=self.user, name="Projects")
        self.upload.vault_folder = folder
        self.upload.save(update_fields=["vault_folder"])

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/folder/", {"folder_id": None}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["folder_id"])
        self.upload.refresh_from_db()
        self.assertIsNone(self.upload.vault_folder_id)

    def test_upload_list_exposes_file_folder_metadata(self):
        folder = VaultFolder.objects.create(user=self.user, name="Projects")
        self.upload.vault_folder = folder
        self.upload.save(update_fields=["vault_folder"])
        root_upload = _managed_upload(self.user, name="root.pdf", key="uploads/folders/root.pdf")

        response = self.client.get(f"{UPLOAD_URL}?canonical=true")

        self.assertEqual(response.status_code, 200)
        folder_ids = {item["file_name"]: item["folder_id"] for item in response.data}
        self.assertEqual(folder_ids[self.upload.file_name], str(folder.id))
        self.assertIsNone(folder_ids[root_upload.file_name])

    def test_moving_blackbod_referenced_upload_preserves_contract_document(self):
        folder = VaultFolder.objects.create(user=self.user, name="Contracts")
        contract = make_contract(self.user, self.other.email)
        doc = ContractDocument.objects.create(
            contract=contract,
            upload=self.upload,
            attached_by=self.user,
            title="Referenced Doc",
        )

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/folder/", {"folder_id": str(folder.id)}, format="json")

        self.assertEqual(response.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.upload_id, self.upload.id)
        self.assertTrue(ContractDocument.objects.filter(pk=doc.id, upload=self.upload).exists())

    def test_share_links_remain_valid_after_file_move(self):
        folder = VaultFolder.objects.create(user=self.user, name="Shared")
        share_response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/shares/", {"expiration": "7d"}, format="json")
        self.assertEqual(share_response.status_code, 201)
        token = urlparse(share_response.data["share_url"]).path.rsplit("/", 1)[-1]

        move_response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/folder/", {"folder_id": str(folder.id)}, format="json")
        public_response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(move_response.status_code, 200)
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.data["file_name"], self.upload.file_name)
        self.assertIsNone(VaultShare.objects.get().revoked_at)

    @patch("backend.api.uploads.views.default_storage")
    def test_folder_delete_does_not_remove_vault_files_or_provider_bytes(self, mock_storage):
        folder = VaultFolder.objects.create(user=self.user, name="Nonempty")
        self.upload.vault_folder = folder
        self.upload.save(update_fields=["vault_folder"])

        response = self.client.delete(f"{UPLOAD_URL}folders/{folder.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(VaultFolder.objects.filter(pk=folder.id).exists())
        self.assertTrue(Upload.objects.filter(pk=self.upload.id).exists())
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.vault_folder_id, folder.id)
        mock_storage.delete.assert_not_called()

    def test_empty_folder_can_be_deleted(self):
        folder = VaultFolder.objects.create(user=self.user, name="Empty")

        response = self.client.delete(f"{UPLOAD_URL}folders/{folder.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(VaultFolder.objects.filter(pk=folder.id).exists())
        self.assertTrue(Upload.objects.filter(pk=self.upload.id).exists())

    def test_folder_with_child_folder_cannot_be_deleted(self):
        folder = VaultFolder.objects.create(user=self.user, name="Parent")
        child = VaultFolder.objects.create(user=self.user, name="Child", parent=folder)

        response = self.client.delete(f"{UPLOAD_URL}folders/{folder.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "folder_not_empty")
        self.assertTrue(VaultFolder.objects.filter(pk=folder.id).exists())
        self.assertTrue(VaultFolder.objects.filter(pk=child.id).exists())

    def test_hidden_removed_upload_cannot_be_moved_through_folder_endpoint(self):
        folder = VaultFolder.objects.create(user=self.user, name="Projects")
        UserObjectAccess.objects.filter(user=self.user, stored_object=self.upload.stored_object).update(
            is_active=True,
            is_visible=False,
            removed_at=timezone.now(),
        )

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/folder/", {"folder_id": str(folder.id)}, format="json")

        self.assertEqual(response.status_code, 404)
        self.upload.refresh_from_db()
        self.assertIsNone(self.upload.vault_folder_id)

    def test_folder_hierarchy_cycles_are_rejected(self):
        parent = VaultFolder.objects.create(user=self.user, name="Parent")
        child = VaultFolder.objects.create(user=self.user, name="Child", parent=parent)

        self_response = self.client.patch(f"{UPLOAD_URL}folders/{parent.id}/", {"parent_id": str(parent.id)}, format="json")
        descendant_response = self.client.patch(f"{UPLOAD_URL}folders/{parent.id}/", {"parent_id": str(child.id)}, format="json")

        self.assertEqual(self_response.status_code, 400)
        self.assertEqual(self_response.data["code"], "invalid_folder")
        self.assertEqual(descendant_response.status_code, 400)
        self.assertEqual(descendant_response.data["code"], "invalid_folder")
        parent.refresh_from_db()
        self.assertIsNone(parent.parent_id)

    def test_upload_create_can_assign_new_file_to_owned_folder(self):
        folder = VaultFolder.objects.create(user=self.user, name="Uploads")
        before_quota = get_storage_capacity_snapshot(self.user).used_bytes

        with patch("backend.uploads.services.default_storage") as mock_storage:
            mock_storage.save.return_value = "uploads/folders/new.pdf"
            mock_storage.url.return_value = "https://example.com/new.pdf"
            response = self.client.post(
                UPLOAD_URL,
                {"file": _pdf("new.pdf", b"%PDF folder content"), "file_type": "pdf", "folder_id": str(folder.id)},
                format="multipart",
            )

        self.assertEqual(response.status_code, 201)
        upload = Upload.objects.get(pk=response.data["id"])
        self.assertEqual(upload.vault_folder_id, folder.id)
        self.assertEqual(Upload.objects.filter(vault_folder=folder).count(), 1)
        self.assertEqual(StoredObject.objects.filter(object_key="uploads/folders/new.pdf").count(), 1)
        self.assertEqual(UserObjectAccess.objects.filter(user=self.user, stored_object=upload.stored_object).count(), 1)
        self.assertEqual(get_storage_capacity_snapshot(self.user).used_bytes, before_quota + upload.file_size)

    def test_upload_create_rejects_other_users_folder_before_storage(self):
        other_folder = VaultFolder.objects.create(user=self.other, name="Other")

        with patch("backend.uploads.services.default_storage") as mock_storage:
            response = self.client.post(
                UPLOAD_URL,
                {"file": _pdf("blocked.pdf"), "file_type": "pdf", "folder_id": str(other_folder.id)},
                format="multipart",
            )

        self.assertEqual(response.status_code, 404)
        mock_storage.save.assert_not_called()



class UploadShareTests(TestCase):

    def setUp(self):
        self.user = make_user("sharer", "sharer@example.com")
        self.other = make_user("share_other", "share_other@example.com")
        self.client = authed_client(self.user)
        self.upload = _managed_upload(self.user, name="contract.pdf", key="uploads/share/contract.pdf", size=4477)
        _grant_capacity(self.user, 10000)

    def _create_share(self, expiration="7d"):
        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/shares/", {"expiration": expiration}, format="json")
        self.assertEqual(response.status_code, 201)
        token = urlparse(response.data["share_url"]).path.rsplit("/", 1)[-1]
        return response, token

    def test_authenticated_owner_can_create_share(self):
        response, token = self._create_share()

        self.assertTrue(token)
        self.assertEqual(VaultShare.objects.count(), 1)
        share = VaultShare.objects.get()
        self.assertEqual(share.owner, self.user)
        self.assertEqual(share.stored_object, self.upload.stored_object)
        self.assertNotEqual(share.token_hash, token)
        self.assertIsNotNone(share.expires_at)
        self.assertEqual(response.data["file_name"], "contract.pdf")
        self.assertEqual(response.data["content_type"], "application/pdf")

    def test_random_public_token_resolves_valid_share(self):
        _, token = self._create_share()

        response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file_name"], "contract.pdf")
        self.assertEqual(response.data["file_size"], 4477)
        self.assertEqual(response.data["delivery_url"], f"/api/uploads/shares/{token}/delivery/")

    def test_another_user_cannot_create_share_for_inaccessible_object(self):
        client = authed_client(self.other)

        response = client.post(f"{UPLOAD_URL}{self.upload.id}/shares/", {"expiration": "7d"}, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(VaultShare.objects.count(), 0)

    def test_expired_share_rejected(self):
        _, token = self._create_share()
        VaultShare.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Share is unavailable."})

    def test_revoked_share_rejected(self):
        _, token = self._create_share()
        share = VaultShare.objects.get()
        share.revoked_at = timezone.now()
        share.save(update_fields=["revoked_at"])

        response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Share is unavailable."})

    def test_removed_owner_access_invalidates_share(self):
        _, token = self._create_share()
        UserObjectAccess.objects.filter(user=self.user, stored_object=self.upload.stored_object).update(
            is_active=False,
            is_visible=False,
            removed_at=timezone.now(),
        )

        response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Share is unavailable."})

    def test_share_does_not_change_quota_usage(self):
        before = get_storage_capacity_snapshot(self.user)

        self._create_share()

        after = get_storage_capacity_snapshot(self.user)
        self.assertEqual(before.used_bytes, 4477)
        self.assertEqual(after.used_bytes, 4477)

    def test_multiple_shares_do_not_change_quota(self):
        before = get_storage_capacity_snapshot(self.user)

        self._create_share("1d")
        self._create_share("7d")
        self._create_share("30d")
        self._create_share("none")

        after = get_storage_capacity_snapshot(self.user)
        self.assertEqual(VaultShare.objects.count(), 4)
        self.assertEqual(before.used_bytes, after.used_bytes)

    def test_public_response_does_not_expose_provider_internals(self):
        _, token = self._create_share()

        response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 200)
        forbidden = {"stored_object", "stored_object_id", "backend", "bucket", "object_key", "file_url", "storage_key"}
        self.assertFalse(forbidden.intersection(response.data.keys()))

    def test_invalid_token_does_not_leak_object_existence(self):
        response = APIClient().get(f"{UPLOAD_URL}shares/not-a-real-token/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Share is unavailable."})

    @patch("backend.uploads.services.default_storage")
    def test_controlled_delivery_requires_valid_share(self, mock_storage):
        _, token = self._create_share()
        mock_storage.url.return_value = "https://provider.example/temp-signed-url"

        valid = APIClient().get(f"{UPLOAD_URL}shares/{token}/delivery/")
        invalid = APIClient().get(f"{UPLOAD_URL}shares/not-real/delivery/")

        self.assertEqual(valid.status_code, 302)
        self.assertEqual(valid["Location"], "https://provider.example/temp-signed-url")
        mock_storage.url.assert_called_once_with(self.upload.stored_object.object_key)
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(invalid.data, {"detail": "Share is unavailable."})

    def test_owner_can_revoke_share(self):
        create_response, _ = self._create_share()
        share_id = create_response.data["id"]

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/shares/{share_id}/revoke/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["revoked_at"])
        self.assertIsNotNone(VaultShare.objects.get(pk=share_id).revoked_at)

    def test_owner_can_list_active_shares_for_visible_canonical_file(self):
        first, _ = self._create_share("1d")
        second, _ = self._create_share("30d")

        response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/shares/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [second.data["id"], first.data["id"]])
        self.assertTrue(all(item["is_valid"] for item in response.data))
        self.assertTrue(all(item["created_at"] for item in response.data))
        self.assertTrue(all(item["expires_at"] for item in response.data))

    def test_share_listing_never_exposes_token_or_provider_internals(self):
        create_response, token = self._create_share()

        response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/shares/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], create_response.data["id"])
        forbidden = {"token", "token_hash", "share_url", "stored_object", "stored_object_id", "backend", "bucket", "object_key", "file_url", "storage_key"}
        self.assertFalse(forbidden.intersection(response.data[0].keys()))
        self.assertNotIn(token, str(response.data[0]))

    def test_cross_user_cannot_list_another_users_shares(self):
        self._create_share()

        response = authed_client(self.other).get(f"{UPLOAD_URL}{self.upload.id}/shares/")

        self.assertEqual(response.status_code, 404)

    def test_hidden_removed_upload_cannot_expose_share_management(self):
        self._create_share()
        UserObjectAccess.objects.filter(user=self.user, stored_object=self.upload.stored_object).update(
            is_active=True,
            is_visible=False,
            removed_at=timezone.now(),
        )

        list_response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/shares/")
        create_response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/shares/", {"expiration": "7d"}, format="json")

        self.assertEqual(list_response.status_code, 404)
        self.assertEqual(create_response.status_code, 404)

    def test_cross_user_cannot_revoke_another_users_share(self):
        create_response, token = self._create_share()
        share_id = create_response.data["id"]

        response = authed_client(self.other).post(f"{UPLOAD_URL}{self.upload.id}/shares/{share_id}/revoke/", {}, format="json")
        public_response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(public_response.status_code, 200)
        self.assertIsNone(VaultShare.objects.get(pk=share_id).revoked_at)

    def test_revoked_public_token_no_longer_resolves_or_delivers(self):
        create_response, token = self._create_share()
        share_id = create_response.data["id"]

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/shares/{share_id}/revoke/", {}, format="json")
        public_response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")
        delivery_response = APIClient().get(f"{UPLOAD_URL}shares/{token}/delivery/")
        list_response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/shares/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(public_response.status_code, 404)
        self.assertEqual(delivery_response.status_code, 404)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data, [])

    @patch("backend.uploads.services.default_storage")
    def test_share_operations_leave_storage_quota_and_contract_references_unchanged(self, mock_storage):
        contract = make_contract(self.user, self.other.email)
        doc = ContractDocument.objects.create(
            contract=contract,
            upload=self.upload,
            attached_by=self.user,
            title="Referenced Share Doc",
        )
        upload_count = Upload.objects.count()
        object_count = StoredObject.objects.count()
        access = UserObjectAccess.objects.get(user=self.user, stored_object=self.upload.stored_object)
        access_snapshot = (access.id, access.is_active, access.is_visible, access.counts_toward_quota, access.removed_at)
        object_key = self.upload.stored_object.object_key
        quota_before = get_storage_capacity_snapshot(self.user).used_bytes

        create_response, _ = self._create_share()
        list_response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/shares/")
        revoke_response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/shares/{create_response.data['id']}/revoke/", {}, format="json")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(revoke_response.status_code, 200)
        self.upload.refresh_from_db()
        self.upload.stored_object.refresh_from_db()
        access.refresh_from_db()
        self.assertEqual(Upload.objects.count(), upload_count)
        self.assertEqual(StoredObject.objects.count(), object_count)
        self.assertEqual(self.upload.stored_object.object_key, object_key)
        self.assertEqual(
            (access.id, access.is_active, access.is_visible, access.counts_toward_quota, access.removed_at),
            access_snapshot,
        )
        self.assertEqual(get_storage_capacity_snapshot(self.user).used_bytes, quota_before)
        self.assertTrue(ContractDocument.objects.filter(pk=doc.id, upload=self.upload).exists())
        mock_storage.open.assert_not_called()
        mock_storage.save.assert_not_called()
        mock_storage.delete.assert_not_called()

    def test_multiple_shares_can_be_revoked_independently(self):
        first, first_token = self._create_share("1d")
        second, second_token = self._create_share("30d")

        first_revoke = self.client.post(f"{UPLOAD_URL}{self.upload.id}/shares/{first.data['id']}/revoke/", {}, format="json")
        first_public = APIClient().get(f"{UPLOAD_URL}shares/{first_token}/")
        second_public = APIClient().get(f"{UPLOAD_URL}shares/{second_token}/")
        list_response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/shares/")

        self.assertEqual(first_revoke.status_code, 200)
        self.assertEqual(first_public.status_code, 404)
        self.assertEqual(second_public.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.data], [second.data["id"]])


class UploadShareFileDeliveryTests(TestCase):

    def setUp(self):
        self.user = make_user("share_file", "share_file@example.com")
        self.other = make_user("share_file_other", "share_file_other@example.com")
        self.client = authed_client(self.user)
        self.upload = _managed_upload(self.user, name="contract.pdf", key="uploads/share-file/contract.pdf", size=4477)
        _grant_capacity(self.user, 10000)

    def test_authenticated_owner_can_retrieve_existing_file_for_native_share(self):
        before_quota = get_storage_capacity_snapshot(self.user)
        before_uploads = Upload.objects.count()
        before_objects = StoredObject.objects.count()
        before_access = UserObjectAccess.objects.count()

        with patch("backend.uploads.services.default_storage") as mock_storage:
            mock_storage.open.return_value = ContentFile(b"%PDF-1.4 real bytes", name="contract.pdf")

            response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/delivery/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("contract.pdf", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 real bytes")
        mock_storage.open.assert_called_once_with(self.upload.stored_object.object_key, "rb")
        self.assertEqual(VaultShare.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), before_uploads)
        self.assertEqual(StoredObject.objects.count(), before_objects)
        self.assertEqual(UserObjectAccess.objects.count(), before_access)
        self.assertEqual(get_storage_capacity_snapshot(self.user).used_bytes, before_quota.used_bytes)

    def test_share_file_delivery_requires_authentication(self):
        response = APIClient().get(f"{UPLOAD_URL}{self.upload.id}/delivery/")

        self.assertEqual(response.status_code, 401)

    def test_another_user_cannot_retrieve_file_for_native_share(self):
        client = authed_client(self.other)

        with patch("backend.uploads.services.default_storage") as mock_storage:
            response = client.get(f"{UPLOAD_URL}{self.upload.id}/delivery/")

        self.assertEqual(response.status_code, 404)
        mock_storage.open.assert_not_called()
        self.assertEqual(VaultShare.objects.count(), 0)

    def test_removed_access_cannot_retrieve_file_for_native_share(self):
        UserObjectAccess.objects.filter(user=self.user, stored_object=self.upload.stored_object).update(
            is_active=False,
            is_visible=False,
            removed_at=timezone.now(),
        )

        with patch("backend.uploads.services.default_storage") as mock_storage:
            response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/delivery/")

        self.assertEqual(response.status_code, 404)
        mock_storage.open.assert_not_called()
        self.assertEqual(VaultShare.objects.count(), 0)

    def test_delivery_response_does_not_expose_provider_internals(self):
        with patch("backend.uploads.services.default_storage") as mock_storage:
            mock_storage.open.return_value = ContentFile(b"bytes", name="contract.pdf")
            response = self.client.get(f"{UPLOAD_URL}{self.upload.id}/delivery/")

        self.assertEqual(response.status_code, 200)
        forbidden_values = [
            self.upload.stored_object.object_key,
            self.upload.stored_object.bucket,
            str(self.upload.stored_object_id),
        ]
        exposed_headers = "\n".join(f"{key}: {value}" for key, value in response.items())
        for value in forbidden_values:
            if value:
                self.assertNotIn(value, exposed_headers)




class UploadEmailFileTests(TestCase):

    def setUp(self):
        self.user = make_user("email_file", "email_file@example.com")
        self.other = make_user("email_file_other", "email_file_other@example.com")
        self.client = authed_client(self.user)
        self.upload = _managed_upload(self.user, name="contract.pdf", key="uploads/email-file/contract.pdf", size=4477)
        _grant_capacity(self.user, 10000)

    def _post_email(self, client=None, upload=None, data=None, **headers):
        return (client or self.client).post(
            f"{UPLOAD_URL}{(upload or self.upload).id}/email/",
            data or {"to": "recipient@example.com", "subject": "contract.pdf from bonUP", "message": "Please review."},
            format="json",
            **headers,
        )

    def _mock_storage(self, mock_storage, content=b"%PDF-1.4 real bytes"):
        mock_storage.open.return_value.__enter__.return_value = ContentFile(content, name="contract.pdf")

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_owner_can_email_active_vault_file(self, mock_storage, mock_send_email):
        self._mock_storage(mock_storage)
        mock_send_email.return_value.provider = "resend"
        mock_send_email.return_value.provider_message_id = "em_123"

        response = self._post_email()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "sent")
        mock_send_email.assert_called_once()

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_actual_attachment_metadata_and_bytes_are_provided_to_email_service(self, mock_storage, mock_send_email):
        self._mock_storage(mock_storage, content=b"trusted attachment bytes")
        mock_send_email.return_value.provider = "resend"
        mock_send_email.return_value.provider_message_id = "em_123"

        response = self._post_email()

        self.assertEqual(response.status_code, 201)
        message = mock_send_email.call_args.args[0]
        attachment = message.attachments[0]
        self.assertEqual(attachment.filename, "contract.pdf")
        self.assertEqual(attachment.content, b"trusted attachment bytes")
        self.assertEqual(attachment.content_type, "application/pdf")
        self.assertEqual(message.to, ["recipient@example.com"])
        self.assertEqual(message.subject, "contract.pdf from bonUP")
        self.assertNotIn("share/", message.text.lower())

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_email_file_does_not_create_vault_storage_or_share_records(self, mock_storage, mock_send_email):
        before_objects = StoredObject.objects.count()
        before_uploads = Upload.objects.count()
        before_access = UserObjectAccess.objects.count()
        before_shares = VaultShare.objects.count()
        before_quota = get_storage_capacity_snapshot(self.user).used_bytes
        self._mock_storage(mock_storage)
        mock_send_email.return_value.provider = "resend"
        mock_send_email.return_value.provider_message_id = "em_123"

        response = self._post_email()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(StoredObject.objects.count(), before_objects)
        self.assertEqual(Upload.objects.count(), before_uploads)
        self.assertEqual(UserObjectAccess.objects.count(), before_access)
        self.assertEqual(VaultShare.objects.count(), before_shares)
        self.assertEqual(get_storage_capacity_snapshot(self.user).used_bytes, before_quota)

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_successful_send_records_delivery_metadata(self, mock_storage, mock_send_email):
        self._mock_storage(mock_storage)
        mock_send_email.return_value.provider = "resend"
        mock_send_email.return_value.provider_message_id = "em_123"

        response = self._post_email(data={"to": " Recipient@Example.COM ", "subject": " Subject ", "message": " Body "})

        self.assertEqual(response.status_code, 201)
        delivery = VaultEmailDelivery.objects.get()
        self.assertEqual(delivery.sender_user, self.user)
        self.assertEqual(delivery.stored_object, self.upload.stored_object)
        self.assertEqual(delivery.recipient_email, "recipient@example.com")
        self.assertEqual(delivery.subject, "Subject")
        self.assertEqual(delivery.provider, "resend")
        self.assertEqual(delivery.provider_message_id, "em_123")
        self.assertEqual(delivery.status, VaultEmailDelivery.Status.SENT)
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(delivery.failure_code, "")

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_sender_cannot_spoof_from(self, mock_storage, mock_send_email):
        self._mock_storage(mock_storage)
        mock_send_email.return_value.provider = "resend"
        mock_send_email.return_value.provider_message_id = "em_123"

        response = self._post_email(data={"to": "recipient@example.com", "subject": "Hi", "message": "Body", "from": "spoof@example.com"})

        self.assertEqual(response.status_code, 201)
        message = mock_send_email.call_args.args[0]
        self.assertFalse(hasattr(message, "from_email"))
        self.assertNotIn("spoof@example.com", message.text)

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_unauthorized_user_cannot_email_object(self, mock_storage, mock_send_email):
        client = authed_client(self.other)

        response = self._post_email(client=client)

        self.assertEqual(response.status_code, 404)
        mock_storage.open.assert_not_called()
        mock_send_email.assert_not_called()
        self.assertEqual(VaultEmailDelivery.objects.count(), 0)

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_removed_access_cannot_email_object(self, mock_storage, mock_send_email):
        UserObjectAccess.objects.filter(user=self.user, stored_object=self.upload.stored_object).update(
            is_active=False,
            is_visible=False,
            removed_at=timezone.now(),
        )

        response = self._post_email()

        self.assertEqual(response.status_code, 404)
        mock_storage.open.assert_not_called()
        mock_send_email.assert_not_called()
        self.assertEqual(VaultEmailDelivery.objects.count(), 0)

    @patch("backend.api.uploads.views.send_email")
    def test_malformed_recipient_rejected(self, mock_send_email):
        response = self._post_email(data={"to": "not an email", "subject": "Hi", "message": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_recipient")
        mock_send_email.assert_not_called()

    @patch("backend.api.uploads.views.send_email")
    def test_missing_subject_rejected(self, mock_send_email):
        response = self._post_email(data={"to": "recipient@example.com", "subject": "  ", "message": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "subject_required")
        mock_send_email.assert_not_called()

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_oversized_attachment_rejected_before_provider_call(self, mock_storage, mock_send_email):
        self.upload.stored_object.size_bytes = 100
        self.upload.stored_object.save(update_fields=["size_bytes"])

        with self.settings(BONUP_EMAIL_ATTACHMENT_MAX_BYTES=99):
            response = self._post_email()

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data["code"], "attachment_too_large")
        mock_storage.open.assert_not_called()
        mock_send_email.assert_not_called()
        self.assertEqual(VaultEmailDelivery.objects.count(), 0)

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_actual_bytes_over_limit_rejected_before_provider_call(self, mock_storage, mock_send_email):
        self.upload.stored_object.size_bytes = 99
        self.upload.stored_object.save(update_fields=["size_bytes"])
        self._mock_storage(mock_storage, content=b"x" * 101)

        with self.settings(BONUP_EMAIL_ATTACHMENT_MAX_BYTES=100):
            response = self._post_email()

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data["code"], "attachment_too_large")
        mock_send_email.assert_not_called()
        delivery = VaultEmailDelivery.objects.get()
        self.assertEqual(delivery.status, VaultEmailDelivery.Status.FAILED)
        self.assertEqual(delivery.failure_code, "attachment_too_large")

    @patch("backend.uploads.services.default_storage")
    def test_provider_unavailable_handled(self, mock_storage):
        from backend.emailing.services import EmailServiceUnavailable

        self._mock_storage(mock_storage)
        with patch("backend.api.uploads.views.send_email", side_effect=EmailServiceUnavailable("missing config")) as mock_send_email:
            response = self._post_email()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "email_service_unavailable")
        mock_send_email.assert_called_once()
        delivery = VaultEmailDelivery.objects.get()
        self.assertEqual(delivery.status, VaultEmailDelivery.Status.FAILED)
        self.assertEqual(delivery.failure_code, "email_service_unavailable")

    @patch("backend.uploads.services.default_storage")
    def test_provider_failure_handled(self, mock_storage):
        from backend.emailing.services import EmailProviderDeliveryError

        self._mock_storage(mock_storage)
        with patch("backend.api.uploads.views.send_email", side_effect=EmailProviderDeliveryError("provider failed")) as mock_send_email:
            response = self._post_email()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "provider_delivery_failure")
        mock_send_email.assert_called_once()
        delivery = VaultEmailDelivery.objects.get()
        self.assertEqual(delivery.status, VaultEmailDelivery.Status.FAILED)
        self.assertEqual(delivery.failure_code, "provider_delivery_failure")

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_repeated_idempotent_request_returns_existing_delivery_without_second_send(self, mock_storage, mock_send_email):
        self._mock_storage(mock_storage)
        mock_send_email.return_value.provider = "resend"
        mock_send_email.return_value.provider_message_id = "em_123"
        headers = {"HTTP_IDEMPOTENCY_KEY": "vault-email-once"}

        first = self._post_email(**headers)
        second = self._post_email(**headers)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["idempotent"])
        self.assertEqual(VaultEmailDelivery.objects.count(), 1)
        mock_send_email.assert_called_once()
        mock_storage.open.assert_called_once_with(self.upload.stored_object.object_key, "rb")

    @patch("backend.api.uploads.views.send_email")
    @patch("backend.uploads.services.default_storage")
    def test_rate_limit_rejects_before_provider_call(self, mock_storage, mock_send_email):
        for index in range(2):
            VaultEmailDelivery.objects.create(
                sender_user=self.user,
                stored_object=self.upload.stored_object,
                recipient_email=f"recipient{index}@example.com",
                subject="Existing",
                provider="resend",
                status=VaultEmailDelivery.Status.FAILED,
            )

        with self.settings(BONUP_VAULT_EMAIL_RATE_LIMIT_PER_HOUR=2):
            response = self._post_email()

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["code"], "rate_limited")
        mock_storage.open.assert_not_called()
        mock_send_email.assert_not_called()


class UploadDuplicateTests(TestCase):

    def setUp(self):
        self.user = make_user("duplicator", "duplicator@example.com")
        self.client = authed_client(self.user)
        _grant_capacity(self.user, 2048)
        self.upload = _managed_upload(self.user, name="receipt.pdf", key="uploads/source/receipt.pdf", size=512)

    def _mock_copy_storage(self, mock_storage, saved_key="uploads/copy/receipt-copy.pdf"):
        source = ContentFile(b"source bytes", name="receipt.pdf")
        mock_storage.open.return_value.__enter__.return_value = source
        mock_storage.save.return_value = saved_key
        mock_storage.url.return_value = "https://current-provider.example/uploads/copy/receipt-copy.pdf"

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_creates_new_upload(self, mock_storage):
        self._mock_copy_storage(mock_storage)

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Upload.objects.filter(user=self.user).count(), 2)
        self.assertEqual(response.data["file_name"], "receipt copy.pdf")

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_creates_new_stored_object(self, mock_storage):
        self._mock_copy_storage(mock_storage)

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        self.assertEqual(response.status_code, 201)
        duplicate = Upload.objects.get(pk=response.data["id"])
        self.assertNotEqual(duplicate.stored_object_id, self.upload.stored_object_id)
        self.assertEqual(StoredObject.objects.count(), 2)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_creates_new_user_object_access(self, mock_storage):
        self._mock_copy_storage(mock_storage)

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        self.assertEqual(response.status_code, 201)
        duplicate = Upload.objects.get(pk=response.data["id"])
        self.assertTrue(UserObjectAccess.objects.filter(user=self.user, stored_object=duplicate.stored_object, is_active=True).exists())
        self.assertEqual(UserObjectAccess.objects.filter(user=self.user, is_active=True).count(), 2)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_new_object_key_differs_from_original(self, mock_storage):
        self._mock_copy_storage(mock_storage)

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        duplicate = Upload.objects.get(pk=response.data["id"])
        self.assertNotEqual(duplicate.storage_key, self.upload.storage_key)
        self.assertNotEqual(duplicate.stored_object.object_key, self.upload.stored_object.object_key)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_increases_quota_by_exact_object_size(self, mock_storage):
        self._mock_copy_storage(mock_storage)
        before = get_storage_capacity_snapshot(self.user)

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        self.assertEqual(response.status_code, 201)
        after = get_storage_capacity_snapshot(self.user)
        self.assertEqual(after.used_bytes, before.used_bytes + self.upload.stored_object.size_bytes)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_leaves_original_unchanged(self, mock_storage):
        self._mock_copy_storage(mock_storage)
        original_object_id = self.upload.stored_object_id
        original_key = self.upload.storage_key

        response = self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        self.assertEqual(response.status_code, 201)
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.stored_object_id, original_object_id)
        self.assertEqual(self.upload.storage_key, original_key)
        self.assertTrue(UserObjectAccess.objects.filter(user=self.user, stored_object_id=original_object_id, is_active=True).exists())

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_exact_remaining_capacity_succeeds(self, mock_storage):
        exact_user = make_user("duplicator_exact", "duplicator_exact@example.com")
        client = authed_client(exact_user)
        _grant_capacity(exact_user, 1024)
        upload = _managed_upload(exact_user, key="uploads/source/exact.pdf", size=512)
        self._mock_copy_storage(mock_storage)

        response = client.post(f"{UPLOAD_URL}{upload.id}/duplicate/")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(get_storage_capacity_snapshot(exact_user).used_bytes, 1024)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_one_byte_over_capacity_fails_before_copy(self, mock_storage):
        limited_user = make_user("duplicator_limited", "duplicator_limited@example.com")
        client = authed_client(limited_user)
        _grant_capacity(limited_user, 1023)
        upload = _managed_upload(limited_user, key="uploads/source/limited.pdf", size=512)

        response = client.post(f"{UPLOAD_URL}{upload.id}/duplicate/")

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data["code"], "storage_capacity_exceeded")
        mock_storage.open.assert_not_called()
        mock_storage.save.assert_not_called()
        self.assertEqual(Upload.objects.filter(user=limited_user).count(), 1)
        self.assertEqual(StoredObject.objects.filter(user_accesses__user=limited_user).distinct().count(), 1)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_provider_failure_creates_no_canonical_duplicate(self, mock_storage):
        mock_storage.open.side_effect = RuntimeError("copy failed")

        with self.assertRaisesMessage(RuntimeError, "copy failed"):
            self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        self.assertEqual(Upload.objects.filter(user=self.user).count(), 1)
        self.assertEqual(StoredObject.objects.filter(user_accesses__user=self.user).distinct().count(), 1)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_database_failure_compensates_new_physical_duplicate(self, mock_storage):
        self._mock_copy_storage(mock_storage)

        with patch("backend.api.uploads.views.Upload.objects.create", side_effect=RuntimeError("db failed")):
            with self.assertRaisesMessage(RuntimeError, "db failed"):
                self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        mock_storage.delete.assert_called_once_with("uploads/copy/receipt-copy.pdf")
        self.assertEqual(Upload.objects.filter(user=self.user).count(), 1)
        self.assertEqual(StoredObject.objects.filter(user_accesses__user=self.user).distinct().count(), 1)

    @patch("backend.uploads.services.default_storage")
    def test_duplicate_cleanup_failure_does_not_mask_original_error(self, mock_storage):
        self._mock_copy_storage(mock_storage)
        mock_storage.delete.side_effect = RuntimeError("cleanup failed")

        with patch("backend.api.uploads.views.Upload.objects.create", side_effect=RuntimeError("db failed")):
            with self.assertRaisesMessage(RuntimeError, "db failed"):
                self.client.post(f"{UPLOAD_URL}{self.upload.id}/duplicate/")

        mock_storage.delete.assert_called_once_with("uploads/copy/receipt-copy.pdf")
        self.assertEqual(Upload.objects.filter(user=self.user).count(), 1)

    def test_upload_view_does_not_introduce_digitalocean_specific_api(self):
        from pathlib import Path

        source = Path("backend/api/uploads/views.py").read_text()

        self.assertNotIn("boto3", source)
        self.assertNotIn("digitalocean", source.lower())
        self.assertNotIn("S3Boto3Storage", source)


class UploadRenameTests(TestCase):

    def setUp(self):
        self.user = make_user("renamer", "renamer@example.com")
        self.other = make_user("renamer_other", "renamer_other@example.com")
        self.client = authed_client(self.user)
        _grant_capacity(self.user, 10000)
        self.upload = _managed_upload(
            self.user,
            name="old-name.pdf",
            key="uploads/rename/original.pdf",
            size=2048,
        )

    def _rename(self, upload=None, file_name="New Name.pdf", client=None):
        return (client or self.client).patch(
            f"{UPLOAD_URL}{(upload or self.upload).id}/",
            {"file_name": file_name},
            format="json",
        )

    @patch("backend.uploads.services.default_storage")
    def test_owner_can_rename_active_visible_canonical_upload(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/rename/original.pdf"

        response = self._rename(file_name=" Renamed File.pdf ")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file_name"], "Renamed File.pdf")
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "Renamed File.pdf")

    def test_cross_user_rename_is_rejected(self):
        response = self._rename(client=authed_client(self.other))

        self.assertEqual(response.status_code, 404)
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "old-name.pdf")

    def test_inactive_removed_canonical_upload_cannot_be_renamed(self):
        UserObjectAccess.objects.filter(user=self.user, stored_object=self.upload.stored_object).update(
            is_active=False,
            is_visible=False,
            removed_at=timezone.now(),
        )

        response = self._rename()

        self.assertEqual(response.status_code, 404)
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "old-name.pdf")

    def test_active_hidden_canonical_upload_cannot_be_renamed(self):
        UserObjectAccess.objects.filter(user=self.user, stored_object=self.upload.stored_object).update(
            is_active=True,
            is_visible=False,
            removed_at=timezone.now(),
        )

        response = self._rename()

        self.assertEqual(response.status_code, 404)
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "old-name.pdf")

    def test_empty_filename_rejected(self):
        response = self._rename(file_name="   ")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "file_name_required")
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "old-name.pdf")

    def test_forward_slash_filename_rejected(self):
        response = self._rename(file_name="folder/new-name.pdf")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_file_name")
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "old-name.pdf")

    def test_backslash_filename_rejected(self):
        response = self._rename(file_name=r"folder\new-name.pdf")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_file_name")
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "old-name.pdf")

    def test_too_long_filename_rejected(self):
        response = self._rename(file_name=f"{'a' * 252}.pdf")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "file_name_too_long")
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.file_name, "old-name.pdf")

    @patch("backend.uploads.services.default_storage")
    def test_successful_rename_changes_upload_file_name_only(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/rename/original.pdf"
        stored_object_id = self.upload.stored_object_id
        object_key = self.upload.stored_object.object_key
        access = UserObjectAccess.objects.get(user=self.user, stored_object=self.upload.stored_object)
        access_snapshot = (access.id, access.is_active, access.is_visible, access.counts_toward_quota, access.removed_at)
        quota_before = get_storage_capacity_snapshot(self.user).used_bytes
        upload_count = Upload.objects.count()
        object_count = StoredObject.objects.count()
        access_count = UserObjectAccess.objects.count()

        response = self._rename(file_name="Renamed File.pdf")

        self.assertEqual(response.status_code, 200)
        self.upload.refresh_from_db()
        self.upload.stored_object.refresh_from_db()
        access.refresh_from_db()
        self.assertEqual(self.upload.file_name, "Renamed File.pdf")
        self.assertEqual(self.upload.stored_object_id, stored_object_id)
        self.assertEqual(self.upload.stored_object.object_key, object_key)
        self.assertEqual(Upload.objects.count(), upload_count)
        self.assertEqual(StoredObject.objects.count(), object_count)
        self.assertEqual(UserObjectAccess.objects.count(), access_count)
        self.assertEqual(
            (access.id, access.is_active, access.is_visible, access.counts_toward_quota, access.removed_at),
            access_snapshot,
        )
        self.assertEqual(get_storage_capacity_snapshot(self.user).used_bytes, quota_before)
        mock_storage.open.assert_not_called()
        mock_storage.save.assert_not_called()
        mock_storage.delete.assert_not_called()

    @patch("backend.uploads.services.default_storage")
    def test_contract_document_reference_survives_rename(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/rename/original.pdf"
        contract = make_contract(self.user, self.other.email)
        doc = ContractDocument.objects.create(
            contract=contract,
            upload=self.upload,
            attached_by=self.user,
            title="Referenced Doc",
        )

        response = self._rename(file_name="Renamed Contract File.pdf")
        doc_response = self.client.get(f"/api/contracts/{contract.id}/documents/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ContractDocument.objects.filter(pk=doc.id, upload=self.upload).exists())
        self.assertEqual(doc_response.status_code, 200)
        self.assertEqual(doc_response.data[0]["upload_id"], str(self.upload.id))
        self.assertEqual(doc_response.data[0]["file_name"], "Renamed Contract File.pdf")


class UploadBulkRemoveTests(TestCase):

    def setUp(self):
        self.user = make_user("bulk_remover", "bulk_remover@example.com")
        self.other = make_user("bulk_other", "bulk_other@example.com")
        self.client = authed_client(self.user)
        _grant_capacity(self.user, 100 * 1024 * 1024)

    def _bulk_remove(self, upload_ids):
        return self.client.post(f"{UPLOAD_URL}bulk-remove/", {"upload_ids": upload_ids}, format="json")

    @patch("backend.api.uploads.views.default_storage")
    def test_bulk_remove_two_owned_canonical_files_uses_existing_metadata_removal(self, mock_storage):
        first = _managed_upload(self.user, name="first.pdf", key="uploads/bulk/first.pdf", size=1024)
        second = _managed_upload(self.user, name="second.pdf", key="uploads/bulk/second.pdf", size=2048)
        upload_count = Upload.objects.count()
        object_count = StoredObject.objects.count()
        access_count = UserObjectAccess.objects.count()
        first_object_key = first.stored_object.object_key
        second_object_key = second.stored_object.object_key
        quota_before = get_user_active_storage_usage_bytes(self.user)

        response = self._bulk_remove([str(first.id), str(second.id)])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 2)
        self.assertEqual(response.data["failed_count"], 0)
        self.assertEqual([item["status"] for item in response.data["results"]], ["removed", "removed"])
        self.assertEqual(Upload.objects.count(), upload_count - 2)
        self.assertEqual(StoredObject.objects.count(), object_count)
        self.assertEqual(UserObjectAccess.objects.count(), access_count)
        self.assertTrue(StoredObject.objects.filter(object_key=first_object_key).exists())
        self.assertTrue(StoredObject.objects.filter(object_key=second_object_key).exists())
        self.assertEqual(get_user_active_storage_usage_bytes(self.user), quota_before - first.file_size - second.file_size)
        mock_storage.delete.assert_not_called()

    def test_bulk_remove_duplicate_ids_processes_once(self):
        upload = _managed_upload(self.user, name="duplicate.pdf", key="uploads/bulk/duplicate.pdf")

        response = self._bulk_remove([str(upload.id), str(upload.id)])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 1)
        self.assertEqual(response.data["failed_count"], 0)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertFalse(Upload.objects.filter(pk=upload.id).exists())

    def test_bulk_remove_rejects_empty_upload_ids(self):
        response = self._bulk_remove([])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "empty_upload_ids")

    def test_bulk_remove_rejects_malformed_request(self):
        response = self.client.post(f"{UPLOAD_URL}bulk-remove/", {"upload_ids": "not-a-list"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_upload_ids")

    def test_bulk_remove_rejects_malformed_uuid(self):
        response = self._bulk_remove(["not-a-uuid"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_upload_id")

    def test_bulk_remove_enforces_batch_limit(self):
        response = self._bulk_remove([str(uuid.uuid4()) for _ in range(101)])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "too_many_upload_ids")

    def test_bulk_remove_cross_user_upload_uses_safe_not_found_semantics(self):
        other_upload = _managed_upload(self.other, name="other.pdf", key="uploads/bulk/other.pdf")

        response = self._bulk_remove([str(other_upload.id)])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 0)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "failed")
        self.assertEqual(response.data["results"][0]["error"], "File not found.")
        self.assertTrue(Upload.objects.filter(pk=other_upload.id).exists())

    def test_bulk_remove_hidden_already_removed_upload_is_safe_not_found(self):
        upload = _managed_upload(self.user, name="hidden.pdf", key="uploads/bulk/hidden.pdf")
        UserObjectAccess.objects.filter(user=self.user, stored_object=upload.stored_object).update(
            is_active=False,
            is_visible=False,
            removed_at=timezone.now(),
        )

        response = self._bulk_remove([str(upload.id)])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 0)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertEqual(response.data["results"][0]["error"], "File not found.")
        self.assertTrue(Upload.objects.filter(pk=upload.id).exists())

    def test_bulk_remove_mixed_success_and_failure_keeps_successful_removal(self):
        owned = _managed_upload(self.user, name="owned.pdf", key="uploads/bulk/owned.pdf")
        other_upload = _managed_upload(self.other, name="other.pdf", key="uploads/bulk/mixed-other.pdf")

        response = self._bulk_remove([str(owned.id), str(other_upload.id), str(uuid.uuid4())])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 1)
        self.assertEqual(response.data["failed_count"], 2)
        self.assertEqual([item["status"] for item in response.data["results"]], ["removed", "failed", "failed"])
        self.assertFalse(Upload.objects.filter(pk=owned.id).exists())
        self.assertTrue(Upload.objects.filter(pk=other_upload.id).exists())

    @patch("backend.api.uploads.views.default_storage")
    def test_bulk_remove_referenced_upload_preserves_blackbod_document_and_quota(self, mock_storage):
        upload = _managed_upload(self.user, name="referenced.pdf", key="uploads/bulk/referenced.pdf", size=5 * 1024 * 1024)
        access = UserObjectAccess.objects.get(user=self.user, stored_object=upload.stored_object)
        contract = make_contract(self.user, self.other.email)
        doc = ContractDocument.objects.create(
            contract=contract,
            upload=upload,
            attached_by=self.user,
            title="Referenced Doc",
        )
        before_quota = get_user_active_storage_usage_bytes(self.user)
        object_id = upload.stored_object_id
        object_key = upload.stored_object.object_key

        response = self._bulk_remove([str(upload.id)])
        vault_list = self.client.get(f"{UPLOAD_URL}?canonical=true")
        doc_list = self.client.get(f"/api/contracts/{contract.id}/documents/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 1)
        self.assertTrue(Upload.objects.filter(pk=upload.id).exists())
        self.assertTrue(StoredObject.objects.filter(pk=object_id, object_key=object_key).exists())
        self.assertTrue(ContractDocument.objects.filter(pk=doc.id, upload=upload).exists())
        self.assertEqual(vault_list.status_code, 200)
        self.assertEqual(vault_list.data, [])
        self.assertEqual(doc_list.status_code, 200)
        self.assertEqual([item["id"] for item in doc_list.data], [str(doc.id)])
        self.assertEqual(get_user_active_storage_usage_bytes(self.user), before_quota)
        access.refresh_from_db()
        self.assertTrue(access.is_active)
        self.assertFalse(access.is_visible)
        self.assertTrue(access.counts_toward_quota)
        self.assertIsNotNone(access.removed_at)
        mock_storage.delete.assert_not_called()

    def test_bulk_remove_revokes_active_vault_shares_through_existing_policy(self):
        upload = _managed_upload(self.user, name="shared.pdf", key="uploads/bulk/shared.pdf")
        create_response = self.client.post(f"{UPLOAD_URL}{upload.id}/shares/", {"expiration": "7d"}, format="json")
        self.assertEqual(create_response.status_code, 201)
        token = urlparse(create_response.data["share_url"]).path.rsplit("/", 1)[-1]

        response = self._bulk_remove([str(upload.id)])
        public_response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 1)
        self.assertIsNotNone(VaultShare.objects.get().revoked_at)
        self.assertEqual(public_response.status_code, 404)

    @patch("backend.api.uploads.views.default_storage")
    def test_bulk_remove_folder_membership_does_not_change_removal_policy(self, mock_storage):
        folder = VaultFolder.objects.create(user=self.user, name="Folder")
        upload = _managed_upload(self.user, name="foldered.pdf", key="uploads/bulk/foldered.pdf", size=4096)
        upload.vault_folder = folder
        upload.save(update_fields=["vault_folder"])
        stored_object_id = upload.stored_object_id
        quota_before = get_user_active_storage_usage_bytes(self.user)

        response = self._bulk_remove([str(upload.id)])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 1)
        self.assertFalse(Upload.objects.filter(pk=upload.id).exists())
        self.assertTrue(VaultFolder.objects.filter(pk=folder.id).exists())
        self.assertTrue(StoredObject.objects.filter(pk=stored_object_id).exists())
        self.assertEqual(get_user_active_storage_usage_bytes(self.user), quota_before - upload.file_size)
        mock_storage.delete.assert_not_called()


class UploadDeleteTests(TestCase):

    def setUp(self):
        self.user = make_user("deleter", "deleter@example.com")
        self.other = make_user("deleter_other", "deleter_other@example.com")
        self.client = authed_client(self.user)

    def _make_upload(self, user=None):
        u = user or self.user
        return Upload.objects.create(
            user=u,
            file_url="https://example.com/file.pdf",
            file_name="file.pdf",
            file_type="pdf",
            file_size=1024,
            storage_key="uploads/1/abc/file.pdf",
        )

    @patch("backend.api.uploads.views.default_storage")
    def test_delete_removes_record(self, mock_storage):
        upload = self._make_upload()
        r = self.client.delete(f"{UPLOAD_URL}{upload.id}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Upload.objects.filter(pk=upload.id).exists())

    @patch("backend.api.uploads.views.default_storage")
    def test_delete_calls_storage_delete(self, mock_storage):
        upload = self._make_upload()
        self.client.delete(f"{UPLOAD_URL}{upload.id}/")
        mock_storage.delete.assert_called_once_with(upload.storage_key)

    @patch("backend.api.uploads.views.default_storage")
    def test_delete_canonical_upload_removes_access_without_physical_delete(self, mock_storage):
        stored_object = create_stored_object_metadata(
            backend="default",
            bucket="test-bucket",
            object_key="uploads/1/abc/canonical.pdf",
            size_bytes=1024,
        )
        access = grant_user_object_access(self.user, stored_object)
        upload = Upload.objects.create(
            user=self.user,
            file_url="https://example.com/file.pdf",
            file_name="file.pdf",
            file_type="pdf",
            file_size=1024,
            storage_key=stored_object.object_key,
            stored_object=stored_object,
        )
        self.assertEqual(get_user_active_storage_usage_bytes(self.user), 1024)

        r = self.client.delete(f"{UPLOAD_URL}{upload.id}/")

        self.assertEqual(r.status_code, 204)
        self.assertEqual(get_user_active_storage_usage_bytes(self.user), 0)
        access.refresh_from_db()
        self.assertFalse(access.is_active)
        self.assertFalse(access.is_visible)
        self.assertIsNotNone(access.removed_at)
        self.assertTrue(StoredObject.objects.filter(pk=stored_object.pk).exists())
        self.assertFalse(Upload.objects.filter(pk=upload.id).exists())
        mock_storage.delete.assert_not_called()

    @patch("backend.api.uploads.views.default_storage")
    def test_delete_referenced_canonical_upload_preserves_document_and_blocks_vault_actions(self, mock_storage):
        stored_object = create_stored_object_metadata(
            backend="default",
            bucket="test-bucket",
            object_key="uploads/1/abc/referenced.pdf",
            size_bytes=5 * 1024 * 1024,
            content_type="application/pdf",
        )
        access = grant_user_object_access(self.user, stored_object)
        upload = Upload.objects.create(
            user=self.user,
            file_url="https://example.com/referenced.pdf",
            file_name="referenced.pdf",
            file_type="pdf",
            file_size=5 * 1024 * 1024,
            storage_key=stored_object.object_key,
            stored_object=stored_object,
        )
        contract = make_contract(self.user, self.other.email)
        doc = ContractDocument.objects.create(
            contract=contract,
            upload=upload,
            attached_by=self.user,
            title="Referenced Doc",
        )
        share_response = self.client.post(f"{UPLOAD_URL}{upload.id}/shares/", {"expiration": "7d"}, format="json")
        self.assertEqual(share_response.status_code, 201)
        share_token = urlparse(share_response.data["share_url"]).path.rsplit("/", 1)[-1]
        before = get_user_active_storage_usage_bytes(self.user)

        response = self.client.delete(f"{UPLOAD_URL}{upload.id}/")
        public_response = APIClient().get(f"{UPLOAD_URL}shares/{share_token}/")
        doc_list = self.client.get(f"/api/contracts/{contract.id}/documents/")
        vault_list = self.client.get(f"{UPLOAD_URL}?canonical=true")
        vault_attach = self.client.post(
            f"/api/contracts/{contract.id}/documents/",
            {"upload_id": str(upload.id), "source": "vault", "title": "Hidden Vault"},
            format="json",
        )
        share_post = self.client.post(f"{UPLOAD_URL}{upload.id}/shares/", {"expiration": "7d"}, format="json")
        email_post = self.client.post(
            f"{UPLOAD_URL}{upload.id}/email/",
            {"to": "recipient@example.com", "subject": "Hidden", "message": "Body"},
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(public_response.status_code, 404)
        self.assertEqual(doc_list.status_code, 200)
        self.assertEqual([item["id"] for item in doc_list.data], [str(doc.id)])
        self.assertEqual(vault_list.status_code, 200)
        self.assertEqual(vault_list.data, [])
        self.assertEqual(vault_attach.status_code, 404)
        self.assertEqual(share_post.status_code, 404)
        self.assertEqual(email_post.status_code, 404)
        self.assertEqual(get_user_active_storage_usage_bytes(self.user), before)

        access.refresh_from_db()
        self.assertTrue(access.is_active)
        self.assertFalse(access.is_visible)
        self.assertTrue(access.counts_toward_quota)
        self.assertIsNotNone(access.removed_at)
        self.assertTrue(StoredObject.objects.filter(pk=stored_object.pk).exists())
        self.assertTrue(Upload.objects.filter(pk=upload.id).exists())
        self.assertTrue(ContractDocument.objects.filter(pk=doc.id).exists())
        self.assertIsNotNone(VaultShare.objects.get().revoked_at)
        mock_storage.delete.assert_not_called()



    @patch("backend.api.uploads.views.default_storage")
    def test_delete_canonical_upload_revokes_active_public_shares(self, mock_storage):
        upload = _managed_upload(self.user, key="uploads/delete/share.pdf")
        create_response = self.client.post(f"{UPLOAD_URL}{upload.id}/shares/", {"expiration": "7d"}, format="json")
        self.assertEqual(create_response.status_code, 201)
        token = urlparse(create_response.data["share_url"]).path.rsplit("/", 1)[-1]

        response = self.client.delete(f"{UPLOAD_URL}{upload.id}/")
        public_response = APIClient().get(f"{UPLOAD_URL}shares/{token}/")

        self.assertEqual(response.status_code, 204)
        share = VaultShare.objects.get()
        self.assertIsNotNone(share.revoked_at)
        self.assertEqual(public_response.status_code, 404)
        mock_storage.delete.assert_not_called()

    def test_delete_other_users_upload_returns_404(self):
        upload = self._make_upload(user=self.other)
        r = self.client.delete(f"{UPLOAD_URL}{upload.id}/")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Upload.objects.filter(pk=upload.id).exists())

    def test_delete_nonexistent_returns_404(self):
        r = self.client.delete(f"{UPLOAD_URL}{uuid.uuid4()}/")
        self.assertEqual(r.status_code, 404)

    def test_unauthenticated_delete_returns_401(self):
        from rest_framework.test import APIClient
        upload = self._make_upload()
        r = APIClient().delete(f"{UPLOAD_URL}{upload.id}/")
        self.assertEqual(r.status_code, 401)
