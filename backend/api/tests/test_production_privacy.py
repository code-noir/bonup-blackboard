"""Synthetic fixtures only: production posture, privacy boundaries, and abuse controls."""
import io
import logging
from unittest.mock import patch
from uuid import uuid4

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import SimpleTestCase, TestCase, RequestFactory, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from backend.core.security import security_settings
from backend.core.privacy_logging import PrivacyFormatter, safe_event
from backend.core.middleware import PrivacyRequestMiddleware
from backend.core.throttling import DEFAULT_RATES, client_ip
from backend.core.email_backends import PrivacyConsoleEmailBackend
from backend.api.sessions.consumers import SessionConsumer
from backend.operator.models import OperatorAuditEvent
from backend.operator.services import create_view_as_session, impersonation_access_token, operator_token_pair
from .helpers import make_user
from .test_operator_auth import make_administrator
from .test_uploads import _managed_upload


class ProductionSettingsTests(SimpleTestCase):
    def production(self, **changes):
        env = dict(BONUP_ENV="production", DJANGO_DEBUG="False", SECRET_KEY="synthetic-secret-only-" * 4,
                   DJANGO_ALLOWED_HOSTS="app.example.invalid", FRONTEND_URL="https://app.example.invalid",
                   EMAIL_BACKEND="backend.core.email_backends.ResendEmailBackend", DEFAULT_FROM_EMAIL="fixture@example.invalid",
                   RESEND_API_KEY="synthetic", BONUP_EMAIL_FROM="fixture@example.invalid")
        env.update(changes)
        return security_settings(env)

    def test_production_https_and_cookie_defaults(self):
        config = self.production()
        for name in ["SECURE_SSL_REDIRECT", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SESSION_COOKIE_HTTPONLY", "BONUP_THROTTLE_ENABLED"]:
            self.assertTrue(config[name])
        self.assertFalse(config['DEBUG'])
        self.assertIsNone(config['SECURE_PROXY_SSL_HEADER'])
        self.assertEqual(config['SECURE_HSTS_SECONDS'], 0)
        self.assertFalse(config['SECURE_HSTS_PRELOAD'])

    def test_production_rejects_unsafe_configuration(self):
        for changes in [dict(DJANGO_DEBUG="True"), dict(SECRET_KEY="short"), dict(DJANGO_ALLOWED_HOSTS="*"), dict(DJANGO_ALLOWED_HOSTS=".example.invalid"),
                        dict(FRONTEND_URL="http://app.example.invalid"), dict(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"),
                        dict(RESEND_API_KEY=""), dict(BONUP_EMAIL_FROM=""), dict(DJANGO_CSRF_TRUSTED_ORIGINS="http://example.invalid")]:
            with self.subTest(changes=list(changes)), self.assertRaises(ImproperlyConfigured):
                self.production(**changes)

    def test_development_remains_http_and_preserves_hosts(self):
        config = security_settings({'DJANGO_DEBUG': 'True'}, development_hosts=['local.example.invalid'])
        with override_settings(**config):
            response = SecurityMiddleware(lambda request: HttpResponse('ok'))(RequestFactory().get('/'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(config['SESSION_COOKIE_SECURE'])
        self.assertEqual(config['ALLOWED_HOSTS'], ['local.example.invalid'])
        self.assertTrue(config['EMAIL_BACKEND'].endswith('PrivacyConsoleEmailBackend'))

    def test_untrusted_forwarded_proto_cannot_disable_https_redirect(self):
        with override_settings(**self.production()):
            response = SecurityMiddleware(lambda request: HttpResponse('ok'))(RequestFactory().get('/', HTTP_HOST='app.example.invalid', HTTP_X_FORWARDED_PROTO='https'))
        self.assertEqual(response.status_code, 301)

    def test_explicit_trusted_proxy_recognizes_https(self):
        with override_settings(**self.production(BONUP_TRUST_PROXY='True')):
            response = SecurityMiddleware(lambda request: HttpResponse('ok'))(RequestFactory().get('/', HTTP_HOST='app.example.invalid', HTTP_X_FORWARDED_PROTO='https'))
        self.assertEqual(response.status_code, 200)

    def test_bad_mode_and_boolean_fail_without_echoing_values(self):
        for env in [{'BONUP_ENV':'synthetic-private-value'}, {'DJANGO_DEBUG':'synthetic-private-value'}]:
            with self.assertRaises(ImproperlyConfigured) as error:
                security_settings(env)
            self.assertNotIn('synthetic-private-value', str(error.exception))

    def test_production_cannot_disable_throttles(self):
        self.assertTrue(self.production(BONUP_THROTTLE_ENABLED='False')['BONUP_THROTTLE_ENABLED'])

    def test_smtp_boolean_representations_match_effective_backend(self):
        from django.core.mail.backends.smtp import EmailBackend
        for enabled in ['True', 'true', 'TRUE', '1', ' true ']:
            for disabled in ['False', 'false', 'FALSE', '0', ' false ']:
                for tls in [True, False]:
                    with self.subTest(enabled=enabled, disabled=disabled, tls=tls):
                        config = self.production(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                            EMAIL_HOST='smtp.example.invalid', EMAIL_USE_TLS=enabled if tls else disabled,
                            EMAIL_USE_SSL=disabled if tls else enabled)
                        with override_settings(**config):
                            backend = EmailBackend()
                            self.assertEqual(backend.use_tls, tls)
                            self.assertEqual(backend.use_ssl, not tls)

    def test_smtp_rejects_ambiguous_or_disabled_production_transport(self):
        for tls, ssl in [('true','1'), ('false','0'), ('invalid','false')]:
            with self.subTest(tls=tls, ssl=ssl), self.assertRaises(ImproperlyConfigured):
                self.production(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                    EMAIL_HOST='smtp.example.invalid', EMAIL_USE_TLS=tls, EMAIL_USE_SSL=ssl)

    def test_development_smtp_flags_share_parser_and_allow_plain_local_transport(self):
        self.assertFalse(security_settings({})['EMAIL_USE_TLS'])
        self.assertFalse(security_settings({})['EMAIL_USE_SSL'])
        self.assertTrue(security_settings({'EMAIL_USE_TLS':'1'})['EMAIL_USE_TLS'])
        with self.assertRaises(ImproperlyConfigured):
            security_settings({'EMAIL_USE_TLS':'True','EMAIL_USE_SSL':'true'})


class LoggingPrivacyTests(SimpleTestCase):
    def test_formatter_never_renders_raw_values_or_traceback(self):
        private = 'synthetic-private-content-token-locator'
        try:
            raise RuntimeError(private)
        except RuntimeError:
            import sys
            record = logging.LogRecord('django.server', logging.ERROR, '', 1,
                '/share/%s?token=%s', (private, private), sys.exc_info())
        record.request = {'Authorization': private, 'file': private}
        record.privacy_event = {'untrusted': private}
        record.status_code = 500
        output = PrivacyFormatter().format(record)
        self.assertNotIn(private, output)
        self.assertNotIn('Traceback', output)
        self.assertIn('500', output)

    def test_formatter_does_not_stringify_arbitrary_objects(self):
        class Private:
            def __str__(self):
                raise AssertionError('Must not stringify')
        record = logging.LogRecord('provider', logging.ERROR, '', 1, Private(), (), None)
        self.assertIn('application_error', PrivacyFormatter().format(record))

    def test_development_email_never_prints_body_token_or_attachment(self):
        message = EmailMessage('synthetic-private-subject', 'synthetic-private-body', 'sender@example.invalid', ['recipient@example.invalid'])
        message.attach('synthetic-private-attachment', b'synthetic-private-bytes')
        with patch('sys.stdout', new_callable=io.StringIO) as stdout, self.assertLogs('bonup.security') as logs:
            self.assertEqual(PrivacyConsoleEmailBackend().send_messages([message]), 0)
        combined = stdout.getvalue() + '\n'.join(logs.output)
        self.assertNotIn('synthetic-private', combined)

    def test_request_id_is_generated_not_copied_from_header(self):
        request = RequestFactory().get('/?token=synthetic-private', HTTP_X_REQUEST_ID='synthetic-private')
        response = PrivacyRequestMiddleware(lambda request: HttpResponse('ok'))(request)
        self.assertEqual(response['X-Request-ID'], request.request_id)
        self.assertNotIn('synthetic-private', response['X-Request-ID'])

    def test_log_event_requires_allowlisted_event(self):
        with self.assertRaises(ValueError):
            safe_event('synthetic-private-content')

    @override_settings(BONUP_TRUST_PROXY=False)
    def test_untrusted_forwarded_ip_is_ignored(self):
        request = RequestFactory().get('/', REMOTE_ADDR='192.0.2.1', HTTP_X_FORWARDED_FOR='192.0.2.2')
        self.assertEqual(client_ip(request), '192.0.2.1')


@override_settings(BONUP_THROTTLE_ENABLED=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()
        self.user = make_user('throttle-fixture', 'throttle@example.invalid')

    def limited(self, scope):
        return override_settings(BONUP_THROTTLE_RATES={**DEFAULT_RATES, scope:'1/min'})

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_customer_login_aliases_share_limit(self):
        with self.limited('login'):
            self.assertEqual(self.client.post('/api/auth/token/', {'username':'missing','password':'synthetic'}).status_code, 401)
            self.assertEqual(self.client.post('/api/users/login/', {'username':'missing','password':'synthetic'}).status_code, 429)

    def test_admin_session_login_throttled(self):
        with self.limited('operator_login'):
            for expected in [200,429]:
                self.assertEqual(self.client.post('/admin/login/', {'username':'missing','password':'synthetic'}).status_code,expected)

    def test_recovery_throttled_without_existence_disclosure(self):
        with self.limited('recovery'):
            for expected in [200,429]:
                self.assertEqual(self.client.post('/api/users/password-reset/', {'email':'missing@example.invalid'}).status_code,expected)

    def test_upload_limit_rejects_before_storage(self):
        self.authenticate()
        with self.limited('upload'):
            for expected in [400,429]:
                self.assertEqual(self.client.post('/api/uploads/',{}).status_code,expected)

    def test_operator_login_throttled(self):
        with self.limited('operator_login'):
            for expected in [401,429]:
                self.assertEqual(self.client.post('/api/operator/auth/token/', {'email':'missing','password':'synthetic'}).status_code, expected)

    def test_refresh_throttled(self):
        with self.limited('refresh'):
            for expected in [401,429]:
                self.assertEqual(self.client.post('/api/auth/token/refresh/', {'refresh':'synthetic'}).status_code, expected)

    def test_public_share_metadata_and_delivery_throttle_token_guessing(self):
        for suffix,scope in [('', 'share_metadata'), ('delivery/', 'share_delivery')]:
            with self.limited(scope):
                self.assertEqual(self.client.get(f'/api/uploads/shares/synthetic-a/{suffix}').status_code,404)
                result = self.client.head(f'/api/uploads/shares/synthetic-b/{suffix}', HTTP_RANGE='bytes=0-1')
                self.assertEqual(result.status_code,429)
                self.assertIn('Retry-After', result)
                self.assertIn('no-store', result['Cache-Control'])

    def test_spoofed_forwarded_ip_does_not_bypass_login_limit(self):
        with self.limited('login'):
            for ip,expected in [('192.0.2.1',401),('192.0.2.2',429)]:
                self.assertEqual(self.client.post('/api/auth/token/', {'username':'missing','password':'synthetic'},HTTP_X_FORWARDED_FOR=ip).status_code,expected)

    def test_email_action_throttled_before_storage(self):
        self.authenticate()
        upload = _managed_upload(self.user,size=7)
        with self.limited('email'), patch('backend.uploads.services.default_storage') as storage:
            for expected in [400,429]:
                self.assertEqual(self.client.post(f'/api/uploads/{upload.pk}/email/',{}).status_code,expected)
            storage.open.assert_not_called()

    def test_search_and_ai_throttled(self):
        self.authenticate()
        for path,scope in [('/api/users/search/?q=fixture','search'),('/api/ai/analyze-contract/','ai')]:
            with self.limited(scope):
                method = self.client.get if scope=='search' else self.client.post
                self.assertNotEqual(method(path).status_code,429)
                self.assertEqual(method(path).status_code,429)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ErrorAndLogoutTests(TestCase):
    def setUp(self):
        self.user = make_user('privacy-fixture', 'privacy@example.invalid')
        self.client = APIClient()
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')

    def test_malformed_private_ids_are_not_server_errors(self):
        for path in ['/api/uploads/not-a-uuid/delivery/','/api/uploads/folders/not-a-uuid/']:
            method = self.client.get if 'delivery' in path else self.client.delete
            self.assertEqual(method(path).status_code,404)
        self.assertEqual(self.client.get('/api/uploads/?contract_id=not-a-uuid').status_code,400)

    def test_unknown_storage_failure_is_sanitized(self):
        upload = _managed_upload(self.user,size=7)
        with patch('backend.uploads.services.default_storage') as storage:
            storage.open.side_effect = RuntimeError('synthetic-private-provider-detail')
            response = self.client.get(f'/api/uploads/{upload.pk}/delivery/')
        self.assertGreaterEqual(response.status_code,400)
        self.assertNotIn(b'synthetic-private',response.content)

    def test_unhandled_api_error_is_sanitized_even_with_debug(self):
        with override_settings(DEBUG=True), patch('backend.api.uploads.views._active_uploads_for_user', side_effect=RuntimeError('synthetic-private-detail')):
            response = self.client.get('/api/uploads/')
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.data,{'detail':'Request could not be completed.'})
        self.assertIn('X-Request-ID',response)

    def test_customer_logout_blacklists_refresh_but_not_existing_access(self):
        self.assertEqual(self.client.post('/api/users/logout/',{'refresh':str(self.refresh)}).status_code,204)
        self.assertEqual(APIClient().post('/api/auth/token/refresh/',{'refresh':str(self.refresh)}).status_code,401)
        self.assertEqual(self.client.get('/api/uploads/').status_code,200)

    def test_refresh_for_missing_customer_returns_auth_error(self):
        self.refresh['user_id'] = 987654321
        self.assertEqual(APIClient().post('/api/auth/token/refresh/',{'refresh':str(self.refresh)}).status_code,401)

    def test_password_reset_enforces_password_policy(self):
        from django.contrib.auth.tokens import PasswordResetTokenGenerator
        from django.utils.http import urlsafe_base64_encode
        uid = urlsafe_base64_encode(str(self.user.pk).encode())
        token = PasswordResetTokenGenerator().make_token(self.user)
        response = APIClient().post('/api/users/password-reset/confirm/', {'uid':uid, 'token':token, 'new_password':'123'})
        self.assertEqual(response.status_code,400)

    def test_customer_cannot_blacklist_other_customer_refresh(self):
        other = make_user('privacy-other','privacy-other@example.invalid')
        refresh = RefreshToken.for_user(other)
        self.assertEqual(self.client.post('/api/users/logout/',{'refresh':str(refresh)}).status_code,400)
        self.assertEqual(APIClient().post('/api/auth/token/refresh/',{'refresh':str(refresh)}).status_code,200)

    def test_operator_logout_revokes_refresh_and_ends_view_as_with_audit(self):
        admin = make_administrator()
        tokens = operator_token_pair(admin)
        session = create_view_as_session(administrator=admin,target_user=self.user,request=RequestFactory().get('/'))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        response = self.client.post('/api/operator/auth/logout/',{'refresh':tokens['refresh']})
        self.assertEqual(response.status_code,204)
        self.assertEqual(APIClient().post('/api/operator/auth/token/refresh/',{'refresh':tokens['refresh']}).status_code,401)
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)
        self.assertTrue(OperatorAuditEvent.objects.filter(view_as_session=session,action=OperatorAuditEvent.ACTION_VIEW_AS_ENDED).exists())

    def test_websocket_rejects_view_as_without_reading_customer(self):
        token = AccessToken.for_user(self.user)
        token['auth_context']='impersonation'
        consumer = SessionConsumer()
        consumer.scope={'query_string':f'token={token}'.encode()}
        self.assertIsNone(async_to_sync(consumer._authenticate)())

    def test_websocket_preserves_normal_customer_auth(self):
        consumer = SessionConsumer()
        consumer.scope={'query_string':f'token={AccessToken.for_user(self.user)}'.encode()}
        self.assertEqual(async_to_sync(consumer._authenticate)().pk,self.user.pk)

    def test_operator_logout_rejects_other_identity_and_customer_refresh(self):
        administrator = make_administrator()
        other = make_administrator(email='other-operator@example.invalid')
        own = operator_token_pair(administrator)
        other_tokens = operator_token_pair(other)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {own["access"]}')
        for refresh in [other_tokens['refresh'], str(self.refresh)]:
            response = self.client.post('/api/operator/auth/logout/', {'refresh':refresh})
            self.assertEqual(response.status_code,400)
            self.assertNotIn(refresh.encode(), response.content)
        public = APIClient()
        self.assertEqual(public.post('/api/operator/auth/token/refresh/', {'refresh':other_tokens['refresh']}).status_code,200)
        self.assertEqual(public.post('/api/auth/token/refresh/', {'refresh':str(self.refresh)}).status_code,200)

    def test_view_as_exit_preserves_both_underlying_refresh_tokens(self):
        administrator = make_administrator()
        tokens = operator_token_pair(administrator)
        session = create_view_as_session(administrator=administrator,target_user=self.user,request=RequestFactory().get('/'))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {impersonation_access_token(session)}')
        self.assertEqual(self.client.post('/api/operator/auth/logout/', {'refresh':tokens['refresh']}).status_code,403)
        self.assertEqual(self.client.post('/api/users/logout/', {'refresh':str(self.refresh)}).status_code,403)
        self.assertEqual(self.client.post('/api/operator/view-as/exit/',{}).status_code,200)
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)
        self.assertTrue(OperatorAuditEvent.objects.filter(view_as_session=session,action=OperatorAuditEvent.ACTION_VIEW_AS_ENDED).exists())
        public = APIClient()
        self.assertEqual(public.post('/api/operator/auth/token/refresh/', {'refresh':tokens['refresh']}).status_code,200)
        self.assertEqual(public.post('/api/auth/token/refresh/', {'refresh':str(self.refresh)}).status_code,200)
