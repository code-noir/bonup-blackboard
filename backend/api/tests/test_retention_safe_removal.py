"""Retention and reference lifecycle tests. All file identities/bytes are synthetic."""
import hashlib
import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.billing.models import StorageEntitlement
from backend.billing.storage import get_used_storage_bytes, get_user_active_storage_usage_bytes
from backend.contracts.admin import ContractAdmin
from backend.contracts.models import Contract, ContractRoleSwitchRequest
from backend.documents.models import ContractDocument
from backend.documents.services import attach_upload, detach_document
from backend.uploads.models import Upload, StoredObject, UserObjectAccess, VaultFolder, VaultShare
from backend.uploads.retention import remove_from_vault
from backend.uploads.services import get_upload_for_new_reference, grant_user_object_access
from .helpers import make_user, make_contract
from .test_uploads import _managed_upload


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RetentionSafeRemovalTests(TestCase):
    def setUp(self):
        self.owner = make_user('retention-owner', 'retention-owner@example.com')
        self.party = make_user('retention-party', 'retention-party@example.com')
        self.other = make_user('retention-other', 'retention-other@example.com')
        self.client = self.auth(self.owner)
        self.contract = make_contract(self.owner, self.party.email)
        self.storage_patch = patch('backend.uploads.services.default_storage')
        self.storage = self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)
        self.storage.size.return_value = 7
        self.storage.open.side_effect = lambda *args: io.BytesIO(b'fixture')

    @staticmethod
    def auth(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def legacy(self, **kwargs):
        return Upload.objects.create(user=self.owner, file_name='fixture.pdf', file_type='pdf',
                                     file_size=7, storage_key='synthetic-key',
                                     file_url='https://example.invalid/untrusted', **kwargs)

    def canonical(self):
        return _managed_upload(self.owner, size=7)

    def attach(self, upload, contract=None):
        return attach_upload(self.owner, (contract or self.contract).pk, upload.pk, title='Fixture')

    def access(self, upload):
        return UserObjectAccess.objects.get(user=self.owner, stored_object_id=upload.stored_object_id)

    def assert_released(self, upload, removed_at=None):
        access = self.access(upload)
        self.assertFalse(access.is_active)
        self.assertFalse(access.is_visible)
        self.assertFalse(access.counts_toward_quota)
        self.assertIsNotNone(access.removed_at)
        if removed_at is not None:
            self.assertEqual(access.removed_at, removed_at)
        self.assertTrue(StoredObject.objects.filter(pk=upload.stored_object_id).exists())
        self.storage.delete.assert_not_called()

    def test_individual_legacy_remove_retains_row_locator_and_references(self):
        upload = self.legacy()
        document = self.attach(upload)
        original = (upload.storage_key, upload.file_url)
        with patch('backend.api.uploads.views.default_storage') as view_storage:
            response = self.client.delete(f'/api/uploads/{upload.pk}/')
            self.assertEqual(response.status_code, 204)
            view_storage.delete.assert_not_called()
        upload.refresh_from_db()
        self.assertIsNotNone(upload.vault_removed_at)
        self.assertEqual((upload.storage_key, upload.file_url), original)
        self.assertTrue(ContractDocument.objects.filter(pk=document.pk).exists())
        self.storage.delete.assert_not_called()

    def test_bulk_legacy_remove_retains_bytes_and_mixed_results(self):
        first, second = self.legacy(), self.legacy()
        with patch('backend.api.uploads.views.default_storage') as storage:
            response = self.client.post('/api/uploads/bulk-remove/', {'upload_ids': [str(first.pk), str(second.pk)]}, format='json')
            self.assertEqual(response.data['removed_count'], 2)
            storage.delete.assert_not_called()
        self.assertEqual(Upload.objects.filter(vault_removed_at__isnull=False).count(), 2)
        self.storage.delete.assert_not_called()

    def test_removed_legacy_unavailable_for_all_bare_upload_boundaries(self):
        upload = self.legacy()
        remove_from_vault(self.owner, upload.pk)
        self.assertEqual(self.client.get('/api/uploads/').data, [])
        self.assertEqual(self.client.get('/api/search/?q=fixture').data['uploads'], [])
        for method, suffix in [('get', 'delivery/'), ('head', 'delivery/'), ('post', 'shares/'), ('post', 'email/'), ('post', 'duplicate/')]:
            self.assertEqual(getattr(self.client, method)(f'/api/uploads/{upload.pk}/{suffix}').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/uploads/{upload.pk}/', {'file_name': 'renamed.pdf'}, format='json').status_code, 404)
        response = self.client.post(f'/api/contracts/{self.contract.pk}/documents/', {'upload_id': str(upload.pk), 'title': 'Fixture'}, format='json')
        self.assertEqual(response.status_code, 404)
        with self.assertRaises(Upload.DoesNotExist):
            get_upload_for_new_reference(self.owner, upload.pk)
        self.storage.open.assert_not_called()
        self.storage.delete.assert_not_called()

    def test_removed_legacy_rejected_by_all_existing_upload_ai_paths(self):
        from .test_ai_contract_tools import _make_subscription
        _make_subscription(self.owner, ai_tier="full", has_sol=True)
        upload = self.legacy()
        remove_from_vault(self.owner, upload.pk)
        with patch("backend.api.ai.views._extract_pdf_text") as extract, patch("backend.api.ai.views.anthropic.Anthropic") as provider:
            for action in ["analyze-contract", "counter-contract", "import-contract"]:
                response = self.client.post(f"/api/ai/{action}/", {"upload_id": str(upload.pk)}, format="json")
                self.assertEqual(response.status_code, 404)
            extract.assert_not_called()
            provider.assert_not_called()
        self.storage.open.assert_not_called()

    def test_removed_legacy_existing_contract_delivery_and_final_detach(self):
        upload = self.legacy()
        document = self.attach(upload)
        remove_from_vault(self.owner, upload.pk)
        with patch('backend.uploads.delivery.default_storage', self.storage):
            response = self.auth(self.party).get(f'/api/contracts/{self.contract.pk}/documents/{document.pk}/delivery/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'fixture')
        detach_document(self.party, self.contract.pk, document.pk)
        upload.refresh_from_db()
        self.assertIsNotNone(upload.vault_removed_at)
        self.assertTrue(upload.storage_key)
        self.storage.delete.assert_not_called()

    def test_url_only_legacy_remove_is_metadata_only(self):
        upload = self.legacy()
        upload.storage_key = ''
        upload.save()
        remove_from_vault(self.owner, upload.pk)
        upload.refresh_from_db()
        self.assertIsNotNone(upload.vault_removed_at)
        self.storage.open.assert_not_called()
        self.storage.delete.assert_not_called()
        self.storage.url.assert_not_called()
        self.assertEqual(StoredObject.objects.count(), 0)

    def test_removed_legacy_does_not_block_empty_folder_deletion(self):
        folder = VaultFolder.objects.create(user=self.owner, name='Fixture folder')
        upload = self.legacy(vault_folder=folder)
        remove_from_vault(self.owner, upload.pk)
        response = self.client.delete(f'/api/uploads/folders/{folder.pk}/')
        self.assertEqual(response.status_code, 204)
        upload.refresh_from_db()
        self.assertIsNone(upload.vault_folder_id)
        self.assertIsNotNone(upload.vault_removed_at)
        self.storage.delete.assert_not_called()

    def test_canonical_unreferenced_remove_retains_object_and_normalizes_flags(self):
        upload = self.canonical()
        remove_from_vault(self.owner, upload.pk)
        self.assert_released(upload)
        self.assertEqual(get_user_active_storage_usage_bytes(self.owner), 0)

    def test_canonical_referenced_remove_preserves_access_and_delivery(self):
        upload = self.canonical()
        document = self.attach(upload)
        remove_from_vault(self.owner, upload.pk)
        access = self.access(upload)
        self.assertTrue(access.is_active)
        self.assertTrue(access.counts_toward_quota)
        self.assertFalse(access.is_visible)
        self.assertEqual(get_used_storage_bytes(self.owner), 7)
        with self.assertRaises(Upload.DoesNotExist):
            self.attach(upload)
        response = self.auth(self.party).get(f'/api/contracts/{self.contract.pk}/documents/{document.pk}/delivery/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'fixture')
        self.storage.delete.assert_not_called()

    def test_only_last_reference_releases_previously_removed_access(self):
        upload = self.canonical()
        first, second = self.attach(upload), self.attach(upload)
        share = VaultShare.objects.create(owner=self.owner, stored_object=upload.stored_object,
            token_hash=hashlib.sha256(b'fixture').hexdigest())
        remove_from_vault(self.owner, upload.pk)
        removed_at = self.access(upload).removed_at
        detach_document(self.party, self.contract.pk, first.pk)
        self.assertTrue(self.access(upload).is_active)
        self.assertEqual(get_used_storage_bytes(self.owner), 7)
        response = self.auth(self.party).delete(f'/api/contracts/{self.contract.pk}/documents/{second.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assert_released(upload, removed_at)
        share.refresh_from_db()
        self.assertIsNotNone(share.revoked_at)
        self.assertEqual(get_used_storage_bytes(self.owner), 0)

    def test_visible_access_survives_final_reference_detach(self):
        upload = self.canonical()
        document = self.attach(upload)
        detach_document(self.party, self.contract.pk, document.pk)
        access = self.access(upload)
        self.assertTrue(access.is_active and access.is_visible and access.counts_toward_quota)

    def test_hidden_grant_without_removal_timestamp_is_not_reconciled(self):
        upload = self.canonical()
        document = self.attach(upload)
        UserObjectAccess.objects.filter(pk=self.access(upload).pk).update(is_visible=False)
        detach_document(self.party, self.contract.pk, document.pk)
        self.assertTrue(self.access(upload).is_active)
        self.assertTrue(self.access(upload).counts_toward_quota)

    def test_other_upload_same_customer_object_keeps_reference_and_quota(self):
        upload = self.canonical()
        other_upload = self.legacy(stored_object=upload.stored_object)
        other_contract = make_contract(self.owner, self.party.email)
        first, second = self.attach(upload), self.attach(other_upload, other_contract)
        remove_from_vault(self.owner, upload.pk)
        detach_document(self.party, self.contract.pk, first.pk)
        self.assertTrue(self.access(upload).is_active)
        self.assertEqual(get_used_storage_bytes(self.owner), 7)
        detach_document(self.party, other_contract.pk, second.pk)
        self.assert_released(upload)

    def test_remove_observes_reference_through_other_upload(self):
        upload = self.canonical()
        other_upload = self.legacy(stored_object=upload.stored_object)
        self.attach(other_upload)
        remove_from_vault(self.owner, upload.pk)
        self.assertTrue(self.access(upload).is_active)
        self.assertTrue(Upload.objects.filter(pk=upload.pk).exists())

    def test_reconciliation_does_not_change_other_customer_access(self):
        upload = self.canonical()
        document = self.attach(upload)
        other_access = grant_user_object_access(self.other, upload.stored_object)
        remove_from_vault(self.owner, upload.pk)
        detach_document(self.party, self.contract.pk, document.pk)
        self.assert_released(upload)
        other_access.refresh_from_db()
        self.assertTrue(other_access.is_active and other_access.is_visible and other_access.counts_toward_quota)
        self.assertIsNone(other_access.removed_at)

    def removed_reference(self):
        upload = self.canonical()
        self.attach(upload)
        remove_from_vault(self.owner, upload.pk)
        return upload

    def test_contract_delete_reconciles(self):
        upload = self.removed_reference()
        response = self.client.delete(f'/api/contracts/{self.contract.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assert_released(upload)

    def test_role_switch_delete_reconciles(self):
        upload = self.removed_reference()
        ContractRoleSwitchRequest.objects.create(contract=self.contract, requested_by=self.party,
            status='pending', expires_at=timezone.now() + timedelta(days=1))
        response = self.client.post(f'/api/contracts/{self.contract.pk}/confirm-role-switch/')
        self.assertEqual(response.status_code, 201)
        self.assert_released(upload)

    def test_admin_contract_delete_reconciles(self):
        upload = self.removed_reference()
        ContractAdmin(Contract, AdminSite()).delete_model(None, self.contract)
        self.assert_released(upload)

    def test_admin_bulk_contract_delete_reconciles_multiple_contracts(self):
        upload = self.canonical()
        other_contract = make_contract(self.owner, self.party.email)
        self.attach(upload)
        self.attach(upload, other_contract)
        remove_from_vault(self.owner, upload.pk)
        ContractAdmin(Contract, AdminSite()).delete_queryset(None, Contract.objects.filter(pk__in=[self.contract.pk, other_contract.pk]))
        self.assert_released(upload)

    def test_last_archive_does_not_resurrect_legacy_aggregate(self):
        StorageEntitlement.objects.create(user=self.owner, capacity_bytes=1000, usage_bytes=500)
        upload = self.canonical()
        document = self.attach(upload)
        remove_from_vault(self.owner, upload.pk)
        detach_document(self.party, self.contract.pk, document.pk)
        self.assertEqual(get_used_storage_bytes(self.owner), 0)

    def test_unreferenced_archive_does_not_resurrect_legacy_aggregate(self):
        StorageEntitlement.objects.create(user=self.owner, capacity_bytes=1000, usage_bytes=500)
        upload = self.canonical()
        remove_from_vault(self.owner, upload.pk)
        self.assertEqual(get_used_storage_bytes(self.owner), 0)

    def test_genuine_legacy_aggregate_is_preserved(self):
        StorageEntitlement.objects.create(user=self.owner, capacity_bytes=1000, usage_bytes=500)
        self.assertEqual(get_used_storage_bytes(self.owner), 500)

    def test_noncounting_grant_alone_does_not_override_legacy_aggregate(self):
        StorageEntitlement.objects.create(user=self.owner, capacity_bytes=1000, usage_bytes=500)
        upload = self.canonical()
        UserObjectAccess.objects.filter(pk=self.access(upload).pk).update(counts_toward_quota=False)
        self.assertEqual(get_used_storage_bytes(self.owner), 500)
