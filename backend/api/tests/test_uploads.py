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

from backend.uploads.models import Upload
from .helpers import authed_client, make_contract, make_user

UPLOAD_URL = "/api/uploads/"

_MOCK_KEY = "uploads/1/abc/test.pdf"
_MOCK_FILE_URL = "https://bonup-storage.nyc3.digitaloceanspaces.com/uploads/1/abc/test.pdf"


def _patched_storage(save_key=_MOCK_KEY, file_url=_MOCK_FILE_URL):
    """Return a mock that stands in for django.core.files.storage.default_storage."""
    mock = MagicMock()
    mock.save.return_value = save_key
    mock.url.return_value = file_url
    return mock


def _pdf(name="test.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake content", content_type="application/pdf")


class UploadCreateTests(TestCase):

    def setUp(self):
        self.user = make_user("uploader", "uploader@example.com")
        self.client = authed_client(self.user)

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
        mock_storage.save.return_value = _MOCK_KEY
        mock_storage.url.return_value = _MOCK_FILE_URL

        for ft in ("pdf", "image", "video", "slides", "document"):
            r = self.client.post(
                UPLOAD_URL,
                {"file": _pdf(f"file.{ft}"), "file_type": ft},
                format="multipart",
            )
            self.assertEqual(r.status_code, 201, f"Expected 201 for file_type={ft}")


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
            storage_key="uploads/1/abc/file.pdf",
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
