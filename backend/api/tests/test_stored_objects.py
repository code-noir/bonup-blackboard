from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from backend.uploads.models import StoredObject, Upload
from backend.uploads.services import (
    DEFAULT_STORAGE_BACKEND_ALIAS,
    UnknownStorageBackendError,
    create_stored_object_metadata,
    get_stored_object_url,
    get_upload_url,
)

from .helpers import make_user


class StoredObjectFoundationTests(TestCase):
    @override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")
    def test_stored_object_represents_physical_storage_identity(self):
        obj = create_stored_object_metadata(
            backend=DEFAULT_STORAGE_BACKEND_ALIAS,
            bucket=settings.AWS_STORAGE_BUCKET_NAME,
            object_key="uploads/1/example.pdf",
            size_bytes=1234,
            content_type="application/pdf",
        )

        self.assertEqual(obj.backend, "default")
        self.assertEqual(obj.bucket, "test-bucket")
        self.assertEqual(obj.object_key, "uploads/1/example.pdf")
        self.assertEqual(obj.size_bytes, 1234)
        self.assertEqual(obj.content_type, "application/pdf")
        self.assertEqual(obj.checksum, "")
        self.assertEqual(obj.checksum_algorithm, "")

    def test_physical_identity_is_unique_per_backend_bucket_and_key(self):
        create_stored_object_metadata(
            backend="default",
            bucket="test-bucket",
            object_key="uploads/1/example.pdf",
            size_bytes=1234,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_stored_object_metadata(
                    backend="default",
                    bucket="test-bucket",
                    object_key="uploads/1/example.pdf",
                    size_bytes=1234,
                )

    def test_same_object_key_can_exist_in_different_backend_or_bucket(self):
        first = create_stored_object_metadata(
            backend="default",
            bucket="test-bucket",
            object_key="uploads/1/example.pdf",
            size_bytes=1234,
        )
        second = create_stored_object_metadata(
            backend="default",
            bucket="archive-bucket",
            object_key="uploads/1/example.pdf",
            size_bytes=1234,
        )
        third = create_stored_object_metadata(
            backend="future_backend",
            bucket="test-bucket",
            object_key="uploads/1/example.pdf",
            size_bytes=1234,
        )

        self.assertNotEqual(first.id, second.id)
        self.assertNotEqual(first.id, third.id)

    @patch("backend.uploads.services.default_storage")
    def test_get_stored_object_url_uses_resolved_storage_backend(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/1/example.pdf"
        obj = create_stored_object_metadata(
            backend="default",
            bucket="test-bucket",
            object_key="uploads/1/example.pdf",
            size_bytes=1234,
        )

        url = get_stored_object_url(obj)

        self.assertEqual(url, "https://current-provider.example/uploads/1/example.pdf")
        mock_storage.url.assert_called_once_with("uploads/1/example.pdf")

    def test_unknown_backend_alias_fails_explicitly(self):
        obj = create_stored_object_metadata(
            backend="unknown_backend",
            bucket="test-bucket",
            object_key="uploads/1/example.pdf",
            size_bytes=1234,
        )

        with self.assertRaises(UnknownStorageBackendError):
            get_stored_object_url(obj)

    def test_negative_size_is_rejected_by_model_validation(self):
        obj = StoredObject(
            backend="default",
            bucket="test-bucket",
            object_key="uploads/1/example.pdf",
            size_bytes=-1,
        )

        with self.assertRaises(ValidationError):
            obj.full_clean()


class ExistingUploadUrlBehaviorTests(TestCase):
    def setUp(self):
        self.user = make_user("stored_upload_user", "stored_upload_user@example.com")

    @patch("backend.uploads.services.default_storage")
    def test_get_upload_url_still_uses_storage_key_when_present(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/example/file.pdf"
        upload = Upload.objects.create(
            user=self.user,
            file_url="https://old-provider.example/stale.pdf",
            file_name="file.pdf",
            file_type="pdf",
            file_size=1234,
            storage_key="uploads/example/file.pdf",
        )

        self.assertEqual(
            get_upload_url(upload),
            "https://current-provider.example/uploads/example/file.pdf",
        )
        mock_storage.url.assert_called_once_with("uploads/example/file.pdf")

    @patch("backend.uploads.services.default_storage")
    def test_get_upload_url_still_falls_back_to_legacy_file_url(self, mock_storage):
        upload = Upload.objects.create(
            user=self.user,
            file_url="https://legacy-provider.example/file.pdf",
            file_name="file.pdf",
            file_type="pdf",
            file_size=1234,
            storage_key="",
        )

        self.assertEqual(get_upload_url(upload), "https://legacy-provider.example/file.pdf")
        mock_storage.url.assert_not_called()
