from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from backend.uploads.models import StoredObject, Upload, UserObjectAccess
from backend.uploads.services import (
    DEFAULT_STORAGE_BACKEND_ALIAS,
    UnknownStorageBackendError,
    create_stored_object_metadata,
    get_stored_object_url,
    get_upload_url,
    grant_user_object_access,
    reactivate_user_object_access,
    remove_user_object_access,
    user_can_access_stored_object,
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


class UserObjectAccessFoundationTests(TestCase):
    def setUp(self):
        self.user = make_user("stored_access_user", "stored_access_user@example.com")
        self.other = make_user("stored_access_other", "stored_access_other@example.com")
        self.stored_object = create_stored_object_metadata(
            backend="default",
            bucket="test-bucket",
            object_key="uploads/1/shared.pdf",
            size_bytes=2048,
            content_type="application/pdf",
        )

    def test_user_object_access_references_stored_object(self):
        access = grant_user_object_access(self.user, self.stored_object)

        self.assertEqual(access.user, self.user)
        self.assertEqual(access.stored_object, self.stored_object)
        self.assertTrue(access.is_active)
        self.assertTrue(access.is_visible)
        self.assertTrue(access.counts_toward_quota)
        self.assertIsNone(access.removed_at)

    def test_one_stored_object_can_have_access_for_two_users(self):
        first = grant_user_object_access(self.user, self.stored_object)
        second = grant_user_object_access(self.other, self.stored_object)

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(self.stored_object.user_accesses.count(), 2)

    def test_user_cannot_receive_duplicate_reference_to_same_stored_object(self):
        first = grant_user_object_access(self.user, self.stored_object)
        second = grant_user_object_access(self.user, self.stored_object)

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            UserObjectAccess.objects.filter(
                user=self.user,
                stored_object=self.stored_object,
            ).count(),
            1,
        )

    def test_database_prevents_duplicate_user_object_reference(self):
        grant_user_object_access(self.user, self.stored_object)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserObjectAccess.objects.create(
                    user=self.user,
                    stored_object=self.stored_object,
                )

    @patch("backend.uploads.services.default_storage")
    def test_remove_user_object_access_removes_logical_access_only(self, mock_storage):
        grant_user_object_access(self.user, self.stored_object)

        removed = remove_user_object_access(self.user, self.stored_object)

        self.assertFalse(removed.is_active)
        self.assertFalse(removed.is_visible)
        self.assertIsNotNone(removed.removed_at)
        self.assertTrue(StoredObject.objects.filter(pk=self.stored_object.pk).exists())
        mock_storage.delete.assert_not_called()

    @patch("backend.uploads.services.default_storage")
    def test_remove_user_object_access_does_not_perform_physical_storage_operation(self, mock_storage):
        grant_user_object_access(self.user, self.stored_object)

        remove_user_object_access(self.user, self.stored_object)

        mock_storage.delete.assert_not_called()
        mock_storage.save.assert_not_called()
        mock_storage.open.assert_not_called()
        mock_storage.url.assert_not_called()

    def test_user_can_access_only_active_stored_object_access(self):
        grant_user_object_access(self.user, self.stored_object)

        self.assertTrue(user_can_access_stored_object(self.user, self.stored_object))

        remove_user_object_access(self.user, self.stored_object)

        self.assertFalse(user_can_access_stored_object(self.user, self.stored_object))

    def test_existing_upload_does_not_imply_stored_object_access(self):
        Upload.objects.create(
            user=self.user,
            file_url="https://legacy-provider.example/file.pdf",
            file_name="file.pdf",
            file_type="pdf",
            file_size=2048,
            storage_key=self.stored_object.object_key,
        )

        self.assertFalse(user_can_access_stored_object(self.user, self.stored_object))

    def test_normal_grant_does_not_silently_restore_removed_access(self):
        grant_user_object_access(self.user, self.stored_object)
        remove_user_object_access(self.user, self.stored_object)

        with self.assertRaises(ValidationError):
            grant_user_object_access(self.user, self.stored_object)

        access = UserObjectAccess.objects.get(user=self.user, stored_object=self.stored_object)
        self.assertFalse(access.is_active)
        self.assertFalse(access.is_visible)
        self.assertIsNotNone(access.removed_at)

    def test_explicit_reactivation_restores_access_deliberately(self):
        grant_user_object_access(
            self.user,
            self.stored_object,
            is_visible=True,
            counts_toward_quota=True,
        )
        remove_user_object_access(self.user, self.stored_object)

        access = reactivate_user_object_access(
            self.user,
            self.stored_object,
            is_visible=False,
            counts_toward_quota=False,
        )

        self.assertTrue(access.is_active)
        self.assertFalse(access.is_visible)
        self.assertFalse(access.counts_toward_quota)
        self.assertIsNone(access.removed_at)
        self.assertTrue(user_can_access_stored_object(self.user, self.stored_object))

    def test_active_counting_references_are_available_for_future_quota_accounting(self):
        access = grant_user_object_access(
            self.user,
            self.stored_object,
            counts_toward_quota=True,
        )

        self.assertTrue(access.is_active)
        self.assertTrue(access.counts_toward_quota)

