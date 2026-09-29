import io
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.uploads.models import StoredObject, Upload, UserObjectAccess
from backend.users.models import BonUserProfile
from .helpers import make_user


def auth(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def image_upload(user, *, name="portrait.png", content_type="image/png", file_type="image"):
    stored_object = StoredObject.objects.create(
        backend="default",
        bucket="test-bucket",
        object_key=f"uploads/profile/{user.pk}/{name}",
        size_bytes=10,
        content_type=content_type,
    )
    UserObjectAccess.objects.create(user=user, stored_object=stored_object)
    return Upload.objects.create(
        user=user,
        file_url="",
        file_name=name,
        file_type=file_type,
        file_size=10,
        storage_key=stored_object.object_key,
        stored_object=stored_object,
    )


class ProfilePhotoAPITests(TestCase):
    def setUp(self):
        self.owner = make_user("profile-photo-owner", "profile-photo-owner@example.com")
        self.other = make_user("profile-photo-other", "profile-photo-other@example.com")
        self.viewer = make_user("profile-photo-viewer", "profile-photo-viewer@example.com")
        self.owner_client = auth(self.owner)
        self.viewer_client = auth(self.viewer)
        self.image = image_upload(self.owner)
        self.other_image = image_upload(self.other, name="other.png")
        self.pdf = image_upload(self.owner, name="terms.pdf", content_type="application/pdf", file_type="pdf")

    def test_owned_image_can_be_selected_and_projected(self):
        response = self.owner_client.patch(
            "/api/users/me/profile-photo/",
            {"profile_photo_id": str(self.image.id), "profile_photo_visible": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["profile_photo_id"], str(self.image.id))
        self.assertTrue(response.data["profile_photo_url"].endswith("/profile-photo/"))

    def test_foreign_and_non_image_assets_are_rejected(self):
        foreign = self.owner_client.patch(
            "/api/users/me/profile-photo/", {"profile_photo_id": str(self.other_image.id)}, format="json"
        )
        non_image = self.owner_client.patch(
            "/api/users/me/profile-photo/", {"profile_photo_id": str(self.pdf.id)}, format="json"
        )

        self.assertEqual(foreign.status_code, 400)
        self.assertEqual(non_image.status_code, 400)
        self.assertIsNone(self.owner.bon_profile.profile_photo_id)

    def test_visibility_off_suppresses_projection_without_clearing_asset(self):
        self.owner_client.patch(
            "/api/users/me/profile-photo/", {"profile_photo_id": str(self.image.id)}, format="json"
        )
        response = self.owner_client.patch(
            "/api/users/me/profile-photo/", {"profile_photo_visible": False}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["profile_photo_id"], str(self.image.id))
        self.assertIsNone(response.data["profile_photo_url"])
        self.assertFalse(response.data["profile_photo_visible"])

    def test_photo_can_be_cleared_without_removing_vault_asset(self):
        self.owner_client.patch(
            "/api/users/me/profile-photo/", {"profile_photo_id": str(self.image.id)}, format="json"
        )
        response = self.owner_client.patch(
            "/api/users/me/profile-photo/", {"profile_photo_id": None}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["profile_photo_id"])
        self.assertTrue(Upload.objects.filter(pk=self.image.id).exists())

    def test_profile_delivery_is_authenticated_and_rechecks_asset_access(self):
        self.owner_client.patch(
            "/api/users/me/profile-photo/", {"profile_photo_id": str(self.image.id)}, format="json"
        )
        storage = MagicMock()
        storage.size.return_value = 10
        storage.open.return_value = io.BytesIO(b"image-data")
        with patch("backend.uploads.services.default_storage", storage):
            path = f"/api/users/{self.owner.bon_profile.bon_id}/profile-photo/"
            response = self.viewer_client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"image-data")

            UserObjectAccess.objects.filter(user=self.owner, stored_object=self.image.stored_object).update(is_active=False)
            self.assertEqual(self.viewer_client.get(path).status_code, 404)

    def test_missing_profile_asset_falls_back_to_no_projection(self):
        profile = self.owner.bon_profile
        profile.profile_photo_visible = True
        profile.profile_photo_id = None
        profile.save(update_fields=["profile_photo", "profile_photo_visible"])

        response = self.owner_client.get("/api/users/me/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["profile_photo_id"])
        self.assertIsNone(response.data["profile_photo_url"])
