# backend/api/tests/test_uploads.py
#
# Tests for the Uploads domain:
#   - POST /api/uploads/    upload a file, get back file_url + record
#   - GET  /api/uploads/    list own uploads, ?contract_id and ?session_id filters
#   - DELETE /api/uploads/<id>/   removes the record (and would delete from storage)

import uuid
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from backend.billing.models import StorageCapacityGrantOrigin, StorageEntitlement
from backend.billing.storage import (
    create_storage_capacity_grant,
    get_user_active_storage_usage_bytes,
)
from backend.uploads.models import StoredObject, Upload, UserObjectAccess
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

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_creates_record(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL

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

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_stores_correct_file_size(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(), "file_type": "pdf"},
            format="multipart",
        )
        upload = Upload.objects.get(user=self.user)
        self.assertGreater(upload.file_size, 0)
        self.assertEqual(r.data["file_size"], upload.file_size)
        self.assertEqual(upload.stored_object.size_bytes, upload.file_size)

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_with_prep_material_flag(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(), "file_type": "pdf", "is_prep_material": "true"},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_prep_material"])
        upload = Upload.objects.get(user=self.user)
        self.assertTrue(upload.is_prep_material)

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_with_contract_id(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL
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

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_all_valid_file_types(self, mock_storage):
        mock_storage.save.side_effect = [f"uploads/1/abc/file.{ft}" for ft in ("pdf", "image", "video", "audio", "slides", "document", "other")]
        mock_storage.url.return_value = _MOCK_FILE_URL

        for ft in ("pdf", "image", "video", "audio", "slides", "document", "other"):
            r = self.client.post(
                UPLOAD_URL,
                {"file": _pdf(f"file.{ft}"), "file_type": ft},
                format="multipart",
            )
            self.assertEqual(r.status_code, 201, f"Expected 201 for file_type={ft}")

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_exactly_filling_remaining_capacity_succeeds(self, mock_storage):
        exact_user = make_user("uploader_exact", "uploader_exact@example.com")
        client = authed_client(exact_user)
        content = b"12345"
        _grant_capacity(exact_user, len(content))
        mock_storage.save.return_value = "uploads/exact/file.pdf"
        mock_storage.url.return_value = _MOCK_FILE_URL

        r = client.post(UPLOAD_URL, {"file": _pdf(content=content), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 201)
        self.assertEqual(get_user_active_storage_usage_bytes(exact_user), len(content))

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_one_byte_over_remaining_capacity_is_rejected_before_storage(self, mock_storage):
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
        mock_storage.save.assert_not_called()
        self.assertFalse(StoredObject.objects.filter(user_accesses__user=limited_user).exists())
        self.assertFalse(UserObjectAccess.objects.filter(user=limited_user).exists())
        self.assertFalse(Upload.objects.filter(user=limited_user).exists())

    @patch("backend.api.uploads.views.default_storage")
    def test_server_side_uploaded_size_is_used_instead_of_client_file_size(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(
            UPLOAD_URL,
            {"file": _pdf(content=b"trusted"), "file_type": "pdf", "file_size": "999999"},
            format="multipart",
        )

        self.assertEqual(r.status_code, 201)
        upload = Upload.objects.get(user=self.user)
        self.assertEqual(upload.file_size, len(b"trusted"))
        self.assertEqual(upload.stored_object.size_bytes, len(b"trusted"))

    @patch("backend.api.uploads.views.default_storage")
    def test_stored_object_uses_actual_key_returned_by_storage_save(self, mock_storage):
        actual_key = "uploads/actual/renamed-by-storage.pdf"
        mock_storage.save.return_value = actual_key
        mock_storage.url.return_value = _MOCK_FILE_URL

        r = self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 201)
        upload = Upload.objects.get(user=self.user)
        self.assertEqual(upload.storage_key, actual_key)
        self.assertEqual(upload.stored_object.object_key, actual_key)

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_response_uses_dynamic_provider_independent_url(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = "https://legacy-write-url.example/file.pdf"
        self.mock_service_storage.url.return_value = "https://current-provider.example/dynamic/file.pdf"

        r = self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["file_url"], "https://current-provider.example/dynamic/file.pdf")
        self.mock_service_storage.url.assert_called_once_with(_MOCK_KEY)

    @patch("backend.api.uploads.views.default_storage")
    def test_database_failure_after_storage_save_cleans_up_new_object(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL

        with patch("backend.api.uploads.views.Upload.objects.create", side_effect=RuntimeError("db failed")):
            with self.assertRaisesMessage(RuntimeError, "db failed"):
                self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        mock_storage.delete.assert_called_once_with(_MOCK_KEY)
        self.assertEqual(StoredObject.objects.count(), 0)
        self.assertEqual(UserObjectAccess.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), 0)

    @patch("backend.api.uploads.views.default_storage")
    def test_cleanup_failure_does_not_mask_original_database_error(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL
        mock_storage.delete.side_effect = RuntimeError("cleanup failed")

        with patch("backend.api.uploads.views.Upload.objects.create", side_effect=RuntimeError("db failed")):
            with self.assertRaisesMessage(RuntimeError, "db failed"):
                self.client.post(UPLOAD_URL, {"file": _pdf(), "file_type": "pdf"}, format="multipart")

        mock_storage.delete.assert_called_once_with(_MOCK_KEY)
        self.assertEqual(StoredObject.objects.count(), 0)
        self.assertEqual(UserObjectAccess.objects.count(), 0)
        self.assertEqual(Upload.objects.count(), 0)

    @patch("backend.api.uploads.views.default_storage")
    def test_upload_does_not_manually_mutate_legacy_storage_usage_bytes(self, mock_storage):
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL
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
