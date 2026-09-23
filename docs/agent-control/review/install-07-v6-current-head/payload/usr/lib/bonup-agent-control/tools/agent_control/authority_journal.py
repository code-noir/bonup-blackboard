"""Controller-owned authority evidence using the existing audit chain/outbox."""
from uuid import NAMESPACE_URL, uuid4, uuid5

from .execution import RoutingEvent
from .serialization import canonical_json, digest, parse_json
from .types import AuthorityError, ValidationError

EVENTS = (
    'FOUNDER_CHALLENGE_ISSUED', 'FOUNDER_SIGNATURE_ACCEPTED', 'FOUNDER_SIGNATURE_DENIED',
    'FOUNDER_SESSION_CREATED', 'FOUNDER_SESSION_EXPIRED', 'INSTALLATION_APPROVAL_ISSUED',
    'INSTALLATION_APPROVAL_DENIED', 'HOST_TEST_AUTHORIZATION_ACCEPTED',
    'HOST_TEST_AUTHORIZATION_DENIED', 'HOST_TEST_SESSION_BEGUN', 'HOST_TEST_SESSION_ENDED',
    'HOST_TEST_CASE_ENROLLED', 'HOST_TEST_CASE_STARTED', 'HOST_TEST_CASE_PASSED',
    'HOST_TEST_CASE_FAILED', 'HOST_TEST_COMPLETION_ACCEPTED', 'HOST_TEST_COMPLETION_DENIED',
    'HOST_TEST_REBOOT_PENDING',
    'HOST_TEST_REQUEST_RECEIVED', 'HOST_TEST_AUTHORIZED',
    'HOST_TEST_CLOSURE_REQUESTED','HOST_TEST_SUPERVISOR_CLOSED',
    'HOST_TEST_CLOSURE_UNCERTAIN','HOST_TEST_AUTHORITY_CONSUMED',
)


class AuthorityJournal:
    def __init__(self, registry):
        self.registry = registry

    def __call__(self, kind, correlation):
        return self.record(kind, correlation, {})

    def record(self, kind, correlation, evidence):
        if kind not in EVENTS or type(correlation) is not str or len(correlation) > 128:
            raise ValidationError('Closed authority audit event required.')
        raw = canonical_json(evidence)
        if len(raw.encode()) > 32768:
            raise ValidationError('Authority evidence exceeds bound.')
        key = 'authority-evidence:' + str(uuid5(NAMESPACE_URL, correlation))
        from .schema import valid_format
        request=correlation if valid_format('uuid',correlation) else str(uuid5(NAMESPACE_URL,correlation))
        reason='INVALID_PROPOSAL' if kind.endswith('DENIED') else 'RECEIVED' if kind.endswith('RECEIVED') else 'AUTHORIZED'
        reason={'HOST_TEST_CLOSURE_REQUESTED':'RECEIVED','HOST_TEST_CLOSURE_UNCERTAIN':'SETUP_FAILED',
                'HOST_TEST_AUTHORITY_CONSUMED':'REVOKED','HOST_TEST_SUPERVISOR_CLOSED':'CANCELLED'}.get(kind,reason)
        event = RoutingEvent(kind, request, reason)
        def action(now, changed):
            row = dict(event=kind, evidence=evidence, digest=digest(evidence), timestamp=now)
            self.registry.db.execute('INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) '
                                     'DO UPDATE SET value=excluded.value', (key, canonical_json(row)))
            # Publish only a digest; full bounded evidence remains controller-local.
            changed.append(('AuthorityEvidence', key, 'authority/' + key.split(':')[1] + '/' + str(uuid4()) + '.json',
                            dict(event=kind, evidence_digest=row['digest'])))
            return {'status': 'RECORDED'}, None
        return self.registry._operation(str(uuid4()), 'authority-evidence',
            dict(kind=kind, correlation=correlation, evidence_digest=digest(evidence)),
            None, action, kind, routing=event)

    def load(self, correlation):
        key = 'authority-evidence:' + str(uuid5(NAMESPACE_URL, correlation))
        row = self.registry.db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        if row is None:
            raise AuthorityError('Missing durable authority evidence.')
        value = parse_json(row[0])
        if value['digest'] != digest(value['evidence']):
            raise AuthorityError('Corrupt durable authority evidence.')
        return value
