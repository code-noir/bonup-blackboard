"""Synthetic fixtures only: authorized delivery and HTTP/content boundaries."""
import hashlib
import io
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, SimpleTestCase, RequestFactory, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.contracts.models import LifecycleAgreement, LifecycleItem, LifecycleItemAttachment
from backend.documents.models import ContractDocument
from backend.uploads.models import Upload, UserObjectAccess, VaultShare
from backend.uploads.delivery import deliver_file
from .helpers import make_user, make_contract, make_version
from .test_uploads import _managed_upload
from .test_operator_auth import make_administrator
from backend.operator.services import operator_token_pair

DATA = b'0123456789'


def storage_fixture():
    storage = MagicMock()
    storage.size.return_value = len(DATA)
    storage.open.side_effect = lambda *args: io.BytesIO(DATA)
    storage.url.side_effect = AssertionError('URL generation is prohibited')
    return storage


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuthorizedFileDeliveryTests(TestCase):
    def setUp(self):
        self.owner = make_user('delivery-owner', 'delivery-owner@example.com')
        self.party = make_user('delivery-party', 'delivery-party@example.com')
        self.stranger = make_user('delivery-stranger', 'delivery-stranger@example.com')
        self.client = self.auth(self.owner)
        self.upload = _managed_upload(self.owner, size=len(DATA))
        self.path = f'/api/uploads/{self.upload.pk}/delivery/'
        self.contract = make_contract(self.owner, self.party.email)
        self.doc = ContractDocument.objects.create(contract=self.contract, upload=self.upload,
                                                   attached_by=self.owner, title='Synthetic fixture')
        self.doc_path = f'/api/contracts/{self.contract.pk}/documents/{self.doc.pk}/delivery/'
        self.storage = storage_fixture()
        self.patch = patch('backend.uploads.services.default_storage', self.storage)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    @staticmethod
    def auth(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def body(self, response):
        self.assertEqual(response.status_code, 200)
        result = b''.join(response.streaming_content)
        return result

    def share(self):
        token = 'synthetic-delivery-capability'
        share = VaultShare.objects.create(owner=self.owner, stored_object=self.upload.stored_object,
                                          token_hash=hashlib.sha256(token.encode()).hexdigest())
        return share, f'/api/uploads/shares/{token}/delivery/'

    def test_own_delivery_canonical_identity_and_no_locators(self):
        self.upload.storage_key = 'synthetic-stale-legacy-identity'
        self.upload.save(update_fields=['storage_key'])
        response = self.client.get(self.path)
        self.assertEqual(self.body(response), DATA)
        self.storage.open.assert_called_once_with(self.upload.stored_object.object_key, 'rb')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('Location', response)
        self.storage.url.assert_not_called()

    def test_foreign_hidden_inactive_and_missing_access_fail_before_storage(self):
        self.assertEqual(self.auth(self.stranger).get(self.path).status_code, 404)
        access = UserObjectAccess.objects.get(user=self.owner, stored_object=self.upload.stored_object)
        for active, visible in [(True, False), (False, True), (False, False)]:
            access.is_active, access.is_visible = active, visible
            access.save()
            for method in ['get', 'head']:
                self.assertEqual(getattr(self.client, method)(self.path).status_code, 404)
        access.delete()
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.storage.open.assert_not_called()
        self.storage.size.assert_not_called()

    def test_retained_reference_both_parties_only(self):
        UserObjectAccess.objects.filter(stored_object=self.upload.stored_object).update(is_visible=False)
        for user in [self.owner, self.party]:
            self.assertEqual(self.body(self.auth(user).get(self.doc_path)), DATA)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.assertEqual(self.auth(self.stranger).get(self.doc_path).status_code, 403)
        other = make_contract(self.owner, self.party.email)
        self.assertEqual(self.client.get(self.doc_path.replace(str(self.contract.pk), str(other.pk))).status_code, 404)

    def test_serializers_use_resource_specific_routes_without_storage(self):
        row = self.client.get('/api/uploads/').data[0]
        self.assertEqual(row['file_url'], self.path)
        rows = self.client.get(f'/api/contracts/{self.contract.pk}/documents/').data
        self.assertEqual(rows[0]['file_url'], self.doc_path)
        rows = self.client.get('/api/search/documents/').data
        self.assertEqual(rows[0]['file_url'], self.doc_path)
        for response in [row, rows]:
            self.assertNotIn(self.upload.stored_object.object_key, str(response))
        self.storage.url.assert_not_called()
        self.storage.open.assert_not_called()

    def test_upload_creation_and_duplicate_never_generate_provider_url(self):
        from .test_uploads import _grant_capacity, _pdf
        _grant_capacity(self.owner, 10000)
        self.storage.save.return_value = 'synthetic-created-object'
        response = self.client.post('/api/uploads/', {'file': _pdf(), 'file_type': 'pdf'}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['file_url'], f"/api/uploads/{response.data['id']}/delivery/")
        created = Upload.objects.get(pk=response.data['id'])
        self.assertEqual(created.file_url, '')
        self.storage.save.return_value = 'synthetic-duplicate-object'
        response = self.client.post(f'/api/uploads/{self.upload.pk}/duplicate/', {}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Upload.objects.get(pk=response.data['id']).file_url, '')
        self.storage.url.assert_not_called()

    def test_head_and_ranges_reauthorize(self):
        response = self.client.head(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Length'], '10')
        self.assertEqual(response.content, b'')
        self.storage.open.assert_not_called()
        for value, expected, interval in [('bytes=2-4', b'234', '2-4'), ('bytes=7-', b'789', '7-9'), ('bytes=-2', b'89', '8-9')]:
            response = self.client.get(self.path, HTTP_RANGE=value)
            self.assertEqual(response.status_code, 206)
            self.assertEqual(b''.join(response.streaming_content), expected)
            self.assertEqual(response['Content-Range'], f'bytes {interval}/10')
            self.assertEqual(response['Content-Length'], str(len(expected)))
        for value in ['bytes=10-', 'bytes=4-2', 'bytes=-0', 'bytes=0-1,4-5', 'garbage']:
            self.assertEqual(self.client.get(self.path, HTTP_RANGE=value).status_code, 416)
        self.storage.reset_mock()
        UserObjectAccess.objects.filter(stored_object=self.upload.stored_object).update(is_visible=False)
        self.assertEqual(self.client.get(self.path, HTTP_RANGE='bytes=0-1').status_code, 404)
        self.storage.open.assert_not_called()

    def test_public_delivery_revalidates_get_head_and_range(self):
        share, path = self.share()
        anonymous = APIClient()
        self.assertEqual(self.body(anonymous.get(path)), DATA)
        partial = anonymous.get(path, HTTP_RANGE="bytes=1-2")
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(b"".join(partial.streaming_content), b"12")
        response = anonymous.head(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        for field in ['revoked_at', 'expires_at']:
            setattr(share, field, timezone.now() - timedelta(seconds=1))
            share.save()
            for method, headers in [('get', {}), ('head', {}), ('get', {'HTTP_RANGE': 'bytes=1-2'})]:
                self.assertEqual(getattr(anonymous, method)(path, **headers).status_code, 404)
            setattr(share, field, None)
            share.save()
        self.client.delete(f'/api/uploads/{self.upload.pk}/')
        self.assertEqual(anonymous.get(path).status_code, 404)

    def test_view_as_all_delivery_routes_denied_before_storage(self):
        operator = APIClient()
        operator.credentials(HTTP_AUTHORIZATION='Bearer ' + operator_token_pair(make_administrator())['access'])
        started = operator.post(f'/api/operator/view-as/{self.owner.pk}/', {}, format='json')
        operator.credentials(HTTP_AUTHORIZATION='Bearer ' + started.data['access'])
        _, share_path = self.share()
        for path in [self.path, self.doc_path, share_path, self.lifecycle_attachment()]:
            for method in ['get', 'head']:
                self.assertEqual(getattr(operator, method)(path, HTTP_RANGE='bytes=0-1').status_code, 403)
        self.storage.open.assert_not_called()
        self.storage.size.assert_not_called()
        self.storage.url.assert_not_called()

    def lifecycle_attachment(self):
        version = make_version(self.contract, self.owner)
        agreement = LifecycleAgreement.objects.create(contract=self.contract, signed_version=version, owner=self.owner)
        item = LifecycleItem.objects.create(lifecycle_agreement=agreement, title='Fixture', item_type='payment')
        attachment = LifecycleItemAttachment.objects.create(
            lifecycle_item=item, lifecycle_agreement=agreement, contract=self.contract,
            uploaded_by=self.owner, file='synthetic-lifecycle-key', original_filename='fixture.pdf',
            content_type='application/pdf', file_size=len(DATA))
        return f'/api/lifecycle/items/{item.pk}/attachments/{attachment.pk}/delivery/'

    def test_lifecycle_delivery_and_serialization(self):
        path = self.lifecycle_attachment()
        field = LifecycleItemAttachment._meta.get_field('file')
        with patch.object(field, 'storage', self.storage):
            self.assertEqual(self.body(self.auth(self.party).get(path)), DATA)
            self.assertEqual(self.auth(self.stranger).get(path).status_code, 403)
            listing = self.client.get(path.rsplit('/', 3)[0] + '/').data
            self.assertEqual(listing['results'][0]['file_url'], path)
            self.storage.url.assert_not_called()

    def test_legacy_key_and_url_only(self):
        upload = Upload.objects.create(user=self.owner, file_name='fixture.pdf', file_type='pdf',
                                       file_size=10, storage_key='synthetic-key', file_url='https://example.invalid/unsafe')
        path = f'/api/uploads/{upload.pk}/delivery/'
        with patch('backend.uploads.delivery.default_storage', self.storage):
            self.assertEqual(self.body(self.client.get(path)), DATA)
            upload.storage_key = ''
            upload.save()
            self.storage.reset_mock()
            self.assertEqual(self.client.get(path).status_code, 404)
            self.storage.open.assert_not_called()
            self.storage.url.assert_not_called()


class FileReaderTests(SimpleTestCase):
    def test_active_unknown_types_force_attachment(self):
        for mime in ['text/html', 'image/svg+xml', 'application/xml', 'unknown/example', '']:
            response = deliver_file(RequestFactory().get('/'), storage=storage_fixture(), key='fixture',
                                    filename='fixture.html', content_type=mime)
            self.assertEqual(response['Content-Type'], 'application/octet-stream')
            self.assertTrue(response['Content-Disposition'].startswith('attachment;'))
            response.close()

    def test_cleanup_before_iteration_and_generic_errors(self):
        stream = io.BytesIO(DATA)
        storage = storage_fixture()
        storage.open.side_effect = None
        storage.open.return_value = stream
        response = deliver_file(RequestFactory().get('/'), storage=storage, key='fixture', filename='fixture.pdf')
        response.close()
        self.assertTrue(stream.closed)
        for error, status in [(FileNotFoundError('private locator'), 404), (RuntimeError('private locator'), 503)]:
            storage.size.side_effect = error
            response = deliver_file(RequestFactory().get('/'), storage=storage, key='fixture', filename='fixture.pdf')
            self.assertEqual(response.status_code, status)
            self.assertNotIn(b'private locator', response.content)

    def test_s3_range_is_bounded_and_head_does_not_fetch_body(self):
        from storages.backends.s3 import S3Storage
        storage = MagicMock(spec=S3Storage)
        obj = storage.bucket.Object.return_value
        obj.content_length = 10
        obj.e_tag = 'synthetic-etag'
        obj.get.return_value = {'Body': io.BytesIO(b'234')}
        response = deliver_file(RequestFactory().get('/', HTTP_RANGE='bytes=2-4'),
                                storage=storage, key='fixture', filename='fixture.pdf', content_type='application/pdf')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(b''.join(response.streaming_content), b'234')
        obj.get.assert_called_once_with(Range='bytes=2-4', IfMatch='synthetic-etag')
        storage.open.assert_not_called()
        storage.url.assert_not_called()
        obj.get.reset_mock()
        response = deliver_file(RequestFactory().head('/'), storage=storage, key='fixture', filename='fixture.pdf')
        self.assertEqual(response['Content-Length'], '10')
        self.assertEqual(response.content, b'')
        obj.get.assert_not_called()

    def test_preview_safe_types_and_explicit_download(self):
        for query, disposition in [('?preview=1', 'inline'), ('?download=1', 'attachment')]:
            response = deliver_file(RequestFactory().head('/' + query), storage=storage_fixture(),
                                    key='fixture', filename='fixture.pdf', content_type='application/pdf')
            self.assertTrue(response['Content-Disposition'].startswith(disposition))
            self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_head_ignores_range_and_if_range_without_validator_returns_full_get(self):
        storage = storage_fixture()
        response = deliver_file(RequestFactory().head('/', HTTP_RANGE='bytes=2-4'), storage=storage,
                                key='fixture', filename='fixture.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Length'], '10')
        storage.open.assert_not_called()
        response = deliver_file(RequestFactory().get('/', HTTP_RANGE='bytes=2-4', HTTP_IF_RANGE='stale'),
                                storage=storage, key='fixture', filename='fixture.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), DATA)

    def test_ranges_clip_end_and_reject_empty_object(self):
        storage = storage_fixture()
        response = deliver_file(RequestFactory().get('/', HTTP_RANGE='bytes=8-999'), storage=storage,
                                key='fixture', filename='fixture.pdf')
        self.assertEqual(response['Content-Range'], 'bytes 8-9/10')
        self.assertEqual(b''.join(response.streaming_content), b'89')
        storage.size.return_value = 0
        response = deliver_file(RequestFactory().get('/', HTTP_RANGE='bytes=0-'), storage=storage,
                                key='fixture', filename='fixture.pdf')
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response['Content-Range'], 'bytes */0')

    def test_only_safe_public_pdf_preview_allows_same_origin_framing(self):
        for public, mime, expected in [(True, 'application/pdf', 'SAMEORIGIN'), (False, 'application/pdf', None), (True, 'text/html', None)]:
            response = deliver_file(RequestFactory().head('/?preview=1'), storage=storage_fixture(),
                                    key='fixture', filename='fixture', content_type=mime, public=public)
            self.assertEqual(response.get('X-Frame-Options'), expected)
