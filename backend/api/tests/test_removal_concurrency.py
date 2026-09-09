"""Real PostgreSQL row-lock races, using separate committed connections."""
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from unittest.mock import patch

from django.apps import apps

from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from backend.documents.models import ContractDocument
from backend.documents.services import attach_upload
from backend.uploads.models import Upload, StoredObject, UserObjectAccess, VaultShare
from backend.uploads.retention import create_vault_share, remove_from_vault
from .helpers import make_user, make_contract
from .test_uploads import _managed_upload


@skipUnless(connection.vendor == 'postgresql', 'Requires real PostgreSQL row locks')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RemovalConcurrencyTests(TransactionTestCase):
    # Include every installed app and allow Django's test-only cascading flush:
    # historical migrations retain users_contact although its model was removed.
    available_apps = [config.name for config in apps.get_app_configs()]

    def setUp(self):
        deletion = patch('django.core.files.storage.default_storage.delete', side_effect=AssertionError('Physical deletion is prohibited'))
        deletion.start()
        self.addCleanup(deletion.stop)
        self.user = make_user('race-owner', 'race-owner@example.com')
        self.contract = make_contract(self.user, 'race-party@example.com')
        self.upload = _managed_upload(self.user, size=7)

    def attach(self, upload=None):
        return attach_upload(self.user, self.contract.pk, (upload or self.upload).pk, title='Fixture').pk

    def remove(self):
        remove_from_vault(self.user, self.upload.pk)
        return 'removed'

    def share(self):
        return create_vault_share(self.user, self.upload.pk, token_hash='synthetic-race-hash', expires_at=None).pk

    def race(self, winner, waiter):
        ready, release = threading.Event(), threading.Event()
        pids = queue.Queue()

        def first():
            try:
                with transaction.atomic():
                    result = winner()
                    ready.set()
                    if not release.wait(10):
                        raise TimeoutError('Winner release timed out')
                return result
            finally:
                connections.close_all()

        def second():
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout TO '8s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    pids.put(cursor.fetchone()[0])
                try:
                    return waiter()
                except Upload.DoesNotExist:
                    return 'denied'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first)
            try:
                self.assertTrue(ready.wait(5), 'Winner did not reach its locked transaction')
                second_future = pool.submit(second)
                pid = pids.get(timeout=5)
                deadline = time.monotonic() + 5
                blocked = False
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT cardinality(pg_blocking_pids(%s)) > 0', [pid])
                        blocked = cursor.fetchone()[0]
                    if blocked:
                        break
                    if second_future.done():
                        self.fail(f'Waiter completed without blocking: {second_future.result()}')
                    time.sleep(0.01)
                self.assertTrue(blocked, 'PostgreSQL did not observe a lock wait')
            finally:
                release.set()
            return first_future.result(timeout=10), second_future.result(timeout=10)

    def assert_retained(self):
        access = UserObjectAccess.objects.get(user=self.user, stored_object=self.upload.stored_object)
        self.assertTrue(access.is_active and access.counts_toward_quota)
        self.assertFalse(access.is_visible)
        self.assertEqual(ContractDocument.objects.count(), 1)
        self.assertTrue(StoredObject.objects.filter(pk=self.upload.stored_object_id).exists())

    def test_attachment_wins_remove_waits_and_retains(self):
        self.race(self.attach, self.remove)
        self.assert_retained()

    def test_remove_wins_attachment_waits_and_rejects(self):
        _, result = self.race(self.remove, self.attach)
        self.assertEqual(result, 'denied')
        self.assertEqual(ContractDocument.objects.count(), 0)
        access = UserObjectAccess.objects.get(user=self.user, stored_object=self.upload.stored_object)
        self.assertFalse(access.is_active or access.counts_toward_quota)
        self.assertTrue(StoredObject.objects.filter(pk=self.upload.stored_object_id).exists())

    def test_referenced_remove_wins_new_attachment_rechecks_hidden_access(self):
        self.attach()
        _, result = self.race(self.remove, self.attach)
        self.assertEqual(result, 'denied')
        self.assert_retained()

    def test_share_wins_remove_waits_then_revokes(self):
        share_id, _ = self.race(self.share, self.remove)
        self.assertIsNotNone(VaultShare.objects.get(pk=share_id).revoked_at)

    def test_remove_wins_share_waits_and_rejects(self):
        _, result = self.race(self.remove, self.share)
        self.assertEqual(result, 'denied')
        self.assertEqual(VaultShare.objects.count(), 0)

    def legacy(self):
        return Upload.objects.create(user=self.user, file_name='fixture.pdf', file_size=7,
                                     file_type='pdf', storage_key='synthetic-legacy-key')

    def test_legacy_attachment_wins_remove_retains_reference(self):
        self.upload = self.legacy()
        self.race(self.attach, self.remove)
        self.upload.refresh_from_db()
        self.assertIsNotNone(self.upload.vault_removed_at)
        self.assertEqual(ContractDocument.objects.filter(upload=self.upload).count(), 1)

    def test_legacy_remove_wins_attachment_rechecks_marker(self):
        self.upload = self.legacy()
        _, result = self.race(self.remove, self.attach)
        self.assertEqual(result, 'denied')
        self.upload.refresh_from_db()
        self.assertIsNotNone(self.upload.vault_removed_at)
        self.assertEqual(ContractDocument.objects.count(), 0)

    def test_other_upload_same_object_waits_on_customer_access_lock(self):
        other = Upload.objects.create(user=self.user, stored_object=self.upload.stored_object,
                                      file_name='fixture.pdf', file_type='pdf', file_size=7)
        _, result = self.race(self.remove, lambda: self.attach(other))
        self.assertEqual(result, 'denied')
        self.assertEqual(ContractDocument.objects.count(), 0)
