"""New-reference and bare-upload authorization must follow database state."""
import io
import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.billing.storage import get_user_active_storage_usage_bytes
from backend.documents.models import ContractDocument
from backend.uploads.models import StoredObject, Upload, UserObjectAccess
from backend.uploads.services import get_upload_for_new_reference
from .helpers import make_contract, make_user
from .test_documents import make_canonical_upload, make_upload
from .test_ai_contract_tools import (
    _ANALYZE_JSON, _COUNTER_JSON, _IMPORT_JSON, _make_subscription,
    _mock_anthropic_response,
)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CanonicalFileAuthorizationTests(TestCase):
    SOURCES = ({}, {"source": ""}, {"source": "vault"}, {"source": "device"},
               {"source": "legacy"}, {"source": None}, {"source": {"mode": "legacy"}})
    AI_PATHS = (
        ("/api/ai/analyze-contract/", _ANALYZE_JSON, 200),
        ("/api/ai/counter-contract/", _COUNTER_JSON, 200),
        ("/api/ai/import-contract/", _IMPORT_JSON, 201),
    )

    def setUp(self):
        self.owner = make_user("canonical-owner", "canonical-owner@example.com")
        self.party = make_user("canonical-party", "canonical-party@example.com")
        self.stranger = make_user("canonical-stranger", "canonical-stranger@example.com")
        _make_subscription(self.owner, ai_tier="full", has_sol=True)
        self.client = self.authenticated(self.owner)
        self.contract = make_contract(self.owner, self.party.email)
        self.other_contract = make_contract(self.owner, self.party.email)

    @staticmethod
    def authenticated(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        return client

    def upload_in_state(self, state):
        upload = make_canonical_upload(self.party if state == "other_owner" else self.owner,
                                       key=f"fixture/{uuid.uuid4()}")
        access = UserObjectAccess.objects.get(user=upload.user, stored_object=upload.stored_object)
        if state == "inactive":
            access.is_active = False
            access.save(update_fields=["is_active"])
        elif state == "hidden":
            access.is_visible = False
            access.save(update_fields=["is_visible"])
        elif state in {"missing", "wrong_access_user", "wrong_object"}:
            access.delete()
            if state == "wrong_access_user":
                UserObjectAccess.objects.create(user=self.party, stored_object=upload.stored_object)
            elif state == "wrong_object":
                make_canonical_upload(self.owner, key=f"fixture/{uuid.uuid4()}")
        return upload

    def attach(self, upload, source, contract=None, client=None):
        return (client or self.client).post(
            f"/api/contracts/{(contract or self.contract).id}/documents/",
            {"upload_id": str(upload.id), "title": "Fixture document", **source}, format="json",
        )

    def test_all_source_values_fail_closed_for_ineligible_canonical_uploads(self):
        with patch("backend.uploads.services.default_storage") as storage:
            for state in ["inactive", "hidden", "missing", "wrong_access_user", "wrong_object", "other_owner"]:
                upload = self.upload_in_state(state)
                for source in self.SOURCES:
                    with self.subTest(state=state, source=source):
                        self.assertEqual(self.attach(upload, source).status_code, 404)
            self.assertEqual(ContractDocument.objects.count(), 0)
            storage.open.assert_not_called()
            storage.url.assert_not_called()
            storage.save.assert_not_called()

    def test_all_sources_allow_active_visible_zero_copy_references(self):
        upload = self.upload_in_state("active")
        before = get_user_active_storage_usage_bytes(self.owner)
        counts = (Upload.objects.count(), StoredObject.objects.count(), UserObjectAccess.objects.count())
        with patch("backend.uploads.services.default_storage") as storage:
            storage.url.return_value = "https://example.invalid/fixture"
            for source in self.SOURCES:
                response = self.attach(upload, source)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(ContractDocument.objects.get(pk=response.data["id"]).upload_id, upload.id)
            self.assertEqual(self.attach(upload, {}, contract=self.other_contract).status_code, 201)
            storage.open.assert_not_called()
            storage.save.assert_not_called()
            storage.delete.assert_not_called()
        self.assertEqual(counts, (Upload.objects.count(), StoredObject.objects.count(), UserObjectAccess.objects.count()))
        self.assertEqual(get_user_active_storage_usage_bytes(self.owner), before)
        self.assertEqual(self.attach(upload, {}, client=self.authenticated(self.stranger)).status_code, 403)

    def test_legacy_owner_policy_is_preserved_independently_of_source(self):
        upload = make_upload(self.owner)
        for source in self.SOURCES:
            self.assertEqual(self.attach(upload, source).status_code, 201)
            self.assertEqual(self.attach(upload, source, client=self.authenticated(self.party)).status_code, 404)
        self.assertEqual(get_upload_for_new_reference(self.owner, upload.id), upload)

    def test_retained_hidden_reference_survives_without_new_reference_or_vault_visibility(self):
        upload = self.upload_in_state("active")
        with patch("backend.uploads.services.default_storage") as storage:
            storage.url.return_value = "https://example.invalid/fixture"
            created = self.attach(upload, {})
            self.assertEqual(created.status_code, 201)
            before = get_user_active_storage_usage_bytes(self.owner)
            self.assertEqual(self.client.delete(f"/api/uploads/{upload.id}/").status_code, 204)
            access = UserObjectAccess.objects.get(user=self.owner, stored_object=upload.stored_object)
            self.assertTrue(access.is_active)
            self.assertFalse(access.is_visible)
            self.assertTrue(access.counts_toward_quota)
            self.assertEqual(get_user_active_storage_usage_bytes(self.owner), before)
            for user in [self.owner, self.party]:
                client = self.authenticated(user)
                response = client.get(f"/api/contracts/{self.contract.id}/documents/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data[0]["id"], created.data["id"])
                self.assertTrue(response.data[0]["file_url"])
            for query in ["", "?canonical=true", "?canonical=false"]:
                self.assertEqual(self.client.get("/api/uploads/" + query).data, [])
            results = self.client.get("/api/search/?q=file").data
            self.assertEqual(results["uploads"], [])
            self.assertEqual(len(results["documents"]), 1)
            self.assertEqual(len(self.client.get("/api/search/documents/").data), 1)
            for source in self.SOURCES:
                self.assertEqual(self.attach(upload, source, contract=self.other_contract).status_code, 404)
            storage.delete.assert_not_called()
            storage.save.assert_not_called()

    def test_all_ai_endpoints_reject_ineligible_uploads_before_any_content_processing(self):
        with patch("backend.uploads.services.default_storage") as storage, \
             patch("django.core.files.storage.default_storage") as legacy_storage, \
             patch("backend.api.ai.views._extract_pdf_text") as extract, \
             patch("backend.api.ai.views.anthropic.Anthropic") as provider:
            for state in ["inactive", "hidden", "missing", "wrong_access_user", "wrong_object", "other_owner"]:
                upload = self.upload_in_state(state)
                for path, _, _ in self.AI_PATHS:
                    with self.subTest(state=state, path=path):
                        response = self.client.post(path, {"upload_id": str(upload.id)}, format="json")
                        self.assertEqual(response.status_code, 404)
            storage.open.assert_not_called()
            storage.url.assert_not_called()
            legacy_storage.open.assert_not_called()
            extract.assert_not_called()
            provider.assert_not_called()

    def test_all_ai_endpoints_use_canonical_backend_identity_not_upload_locator(self):
        upload = self.upload_in_state("active")
        upload.storage_key = "different-legacy-locator"
        upload.save(update_fields=["storage_key"])
        for path, payload, expected_status in self.AI_PATHS:
            with self.subTest(path=path), \
                 patch("backend.uploads.services.get_storage_backend") as resolve_storage, \
                 patch("django.core.files.storage.default_storage") as legacy_storage, \
                 patch("backend.api.ai.views._extract_pdf_text", return_value="fixture text") as extract, \
                 patch("backend.api.ai.views.anthropic.Anthropic", new=_mock_anthropic_response(payload)):
                stream = io.BytesIO(b"fixture canonical bytes")
                resolve_storage.return_value.open.return_value = stream
                response = self.client.post(path, {"upload_id": str(upload.id)}, format="json")
                self.assertEqual(response.status_code, expected_status)
                resolve_storage.assert_called_once_with(upload.stored_object.backend)
                resolve_storage.return_value.open.assert_called_once_with(upload.stored_object.object_key)
                legacy_storage.open.assert_not_called()
                extract.assert_called_once_with(b"fixture canonical bytes")
                self.assertTrue(stream.closed)

    def test_all_ai_endpoints_preserve_legacy_reads(self):
        upload = make_upload(self.owner)
        upload.storage_key = "legacy-fixture"
        upload.save(update_fields=["storage_key"])
        for path, payload, expected_status in self.AI_PATHS:
            with self.subTest(path=path), \
                 patch("django.core.files.storage.default_storage") as storage, \
                 patch("backend.uploads.services.get_storage_backend") as resolve_storage, \
                 patch("backend.api.ai.views._extract_pdf_text", return_value="fixture text"), \
                 patch("backend.api.ai.views.anthropic.Anthropic", new=_mock_anthropic_response(payload)):
                storage.open.return_value = io.BytesIO(b"fixture legacy bytes")
                self.assertEqual(self.client.post(path, {"upload_id": str(upload.id)}, format="json").status_code, expected_status)
                storage.open.assert_called_once_with(upload.storage_key)
                resolve_storage.assert_not_called()

    def test_invalid_upload_ids_are_safe_not_found(self):
        for value in ["invalid", str(uuid.uuid4()), {"id": "invalid"}]:
            for path, _, _ in self.AI_PATHS:
                self.assertEqual(self.client.post(path, {"upload_id": value}, format="json").status_code, 404)
            response = self.client.post(f"/api/contracts/{self.contract.id}/documents/",
                {"upload_id": value, "title": "Fixture"}, format="json")
            self.assertEqual(response.status_code, 404)
