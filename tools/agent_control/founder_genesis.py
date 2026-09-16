"""Offline human Genesis contract, never a runtime enrollment operation.

The offline ceremony adapter and its durable ledger are trust-boundary inputs.
They must not be constructed from an RPC/JSON request. The default adapter is
unavailable: there is no production auto-confirm or software signing fallback.
"""
import base64
import hashlib
import secrets
import time
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from .founder_crypto import FounderRoot, PURPOSES
from .serialization import canonical_json, digest, parse_json
from .schema import valid_format
from .types import AuthorityError, ValidationError

DOMAIN = 'bonup-founder-genesis'
BINDING_PATH = '/etc/bonup-agent-control/founder-root-binding.json'
EVIDENCE_PATH = '/etc/bonup-agent-control/founder-genesis-evidence.json'
PUBLIC_PATH = '/etc/bonup-agent-control/founder-root.json'


def policy():
    return dict(version=1, enabled=True, algorithm='Ed25519',
        verifier='/usr/bin/openssl', operation='VERIFY_ONLY', roots=1, root_generation=1,
        purposes=list(PURPOSES), encoding='RFC4648_BASE64_RAW_32_BYTES',
        key_id='SHA256_RAW_PUBLIC_KEY_HEX', private_key='EXTERNAL_ONLY',
        genesis='OFFLINE_HUMAN_CEREMONY_REQUIRED', rotation=False,
        binding='REQUIRED_BEFORE_INSTALLATION_APPROVAL',
        session_seconds=60, genesis_seconds=300, replay='ONE_USE_BOOT_PROCESS_PURPOSE_BOUND',
        activation=False)


def public_root(encoded):
    if type(encoded) is not str or len(encoded) != 44:
        raise ValidationError('One canonical Ed25519 public key required.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise ValidationError('Malformed Ed25519 public key.') from error
    if len(raw) != 32 or base64.b64encode(raw).decode() != encoded:
        raise ValidationError('Noncanonical Ed25519 public key.')
    # Canonical compressed Edwards encoding. Signature validity is checked only
    # by the reviewed OpenSSL adapter; this is not a signature implementation.
    if int.from_bytes(raw, 'little') & ((1 << 255)-1) >= (1 << 255)-19:
        raise ValidationError('Noncanonical Ed25519 point encoding.')
    if raw in (bytes(32), b'\x01' + bytes(31)):
        raise ValidationError('Degenerate public key.')
    return FounderRoot(hashlib.sha256(raw).hexdigest(), raw, 1)


def public_artifact(root):
    return dict(key_id=root.key_id, algorithm='Ed25519',
        public_key=base64.b64encode(root.public_key).decode(), generation=1,
        purposes=list(PURPOSES))


def candidate_identity(raw, validate_complete):
    """Generator-owned structural validator must precede Genesis eligibility.

    No supplied 'complete' flag is authority. The future Generation-2 generator
    supplies its strict validator; there is deliberately no permissive default.
    """
    if type(raw) is not bytes or len(raw) > 65536:
        raise ValidationError('Bounded candidate bytes required.')
    value = parse_json(raw)
    if type(value) is not dict:
        raise ValidationError('Candidate object required.')
    validate_complete(value)
    if (type(raw) is not bytes or len(raw) > 65536 or
            value.get('provisioning_generation') != 2 or
            type(value.get('provisioning_generation')) is not int or
            value.get('approved') is not False or value.get('activation') is not False or
            value.get('integration_services_approved') is not False or
            canonical_json(value.get('founder_root_policy')) != canonical_json(policy()) or
            value.get('bundle_digest') != digest({k:v for k,v in value.items() if k!='bundle_digest'}) or
            not valid_format('git-oid', value.get('source_commit'))):
        raise AuthorityError('Complete unapproved Generation-2 candidate required.')
    return dict(source_commit=value['source_commit'], candidate_manifest_digest=hashlib.sha256(raw).hexdigest(),
        candidate_bundle_digest=value['bundle_digest'], provisioning_generation=2,
        founder_root_policy_digest=digest(policy()))


class OfflineCeremony:
    """Future independently reviewed offline UI; unavailable in M3 production.

    confirm must display ALL challenge fields, require independent comparison,
    then deliberate entry of the full digest and the human comparison code.
    Neither stdin/RPC JSON nor root privilege may implement this boundary.
    """
    def confirm(self, challenge, full_digest, comparison_code):
        raise AuthorityError('Reviewed offline human ceremony adapter required.')


class GenesisLedger:
    """Already established offline trust-domain database; never auto-initialized.

    Required table: genesis(domain TEXT PRIMARY KEY, state TEXT NOT NULL,
    evidence TEXT NOT NULL). A trusted offline initialization ceremony creates
    exactly one VIRGIN row with evidence '{}', only after excluding prior root
    and installation evidence. Missing/deleted/corrupt state denies Genesis.
    SQLite transaction serialization consumes before publishing the binding.
    """
    def __init__(self, db):
        self.db = db

    def require_virgin(self):
        rows = self.db.execute('SELECT state,evidence FROM genesis WHERE domain=?', (DOMAIN,)).fetchall()
        if rows != [('VIRGIN', '{}')]:
            raise AuthorityError('Genesis unavailable: absent or previously consumed trust domain.')

    def consume(self, evidence):
        with self.db:
            result = self.db.execute('UPDATE genesis SET state=?,evidence=? '
                'WHERE domain=? AND state=? AND evidence=?',
                ('CONSUMED', canonical_json(evidence), DOMAIN, 'VIRGIN', '{}'))
            if result.rowcount != 1:
                raise AuthorityError('Genesis already consumed or state unavailable.')


class Genesis:
    def __init__(self, ledger, *, validate_complete, ceremony=None, audit,
                 clock=lambda: datetime.now(timezone.utc), elapsed=time.monotonic):
        self.ledger, self.validate_complete = ledger, validate_complete
        self.ceremony = ceremony if ceremony is not None else OfflineCeremony()
        if not isinstance(self.ceremony, OfflineCeremony):
            raise AuthorityError('Trusted offline ceremony adapter required, not request data.')
        self.audit, self.clock = audit, clock
        self.elapsed = elapsed
        self.pending = None

    def propose(self, candidate, encoded_key):
        try:
            self.ledger.require_virgin()
        except BaseException:
            self.audit('GENESIS_DUPLICATE_DENIED', {})
            raise
        identity = candidate_identity(candidate, self.validate_complete)
        try:
            root = public_root(encoded_key)
        except BaseException:
            self.audit('GENESIS_KEY_DENIED', {})
            raise
        now = self.clock()
        challenge = dict(version=1, protocol='bonup-founder-genesis-v1', purpose='FOUNDER_ROOT_GENESIS',
            **identity, algorithm='Ed25519', public_key_digest=root.key_id, key_id=root.key_id,
            root_generation=1, nonce=secrets.token_hex(32), issued_at=now.isoformat(),
            expires_at=(now+timedelta(seconds=300)).isoformat())
        self.pending = (deepcopy(challenge), encoded_key, self.elapsed()+300)
        self.audit('GENESIS_PROPOSAL_CREATED', {'challenge_digest':digest(challenge)})
        return deepcopy(challenge)

    def finish(self, candidate):
        pending, self.pending = self.pending, None
        if pending is None:
            raise AuthorityError('Fresh Genesis proposal required.')
        challenge, encoded_key, deadline = pending
        self.ledger.require_virgin()
        identity = candidate_identity(candidate, self.validate_complete)
        if any(challenge[k] != v for k,v in identity.items()):
            self.audit('GENESIS_CANDIDATE_DENIED', {})
            raise AuthorityError('Genesis candidate changed.')
        now = self.clock()
        if (self.elapsed() >= deadline or
                not datetime.fromisoformat(challenge['issued_at']) <= now < datetime.fromisoformat(challenge['expires_at'])):
            raise AuthorityError('Expired Genesis proposal.')
        full = digest(challenge)
        # Short code is display-only. Adapter must return the FULL challenge
        # digest after deliberate human confirmation, never just the short code.
        confirmed = self.ceremony.confirm(deepcopy(challenge), full, full[:16])
        if type(confirmed) is not str or confirmed != full:
            raise AuthorityError('Exact human confirmation missing.')
        if (self.elapsed() >= deadline or
                not datetime.fromisoformat(challenge['issued_at']) <= self.clock() < datetime.fromisoformat(challenge['expires_at'])):
            raise AuthorityError('Genesis confirmation expired.')
        root = public_root(encoded_key)
        binding = dict(version=1, **identity, algorithm='Ed25519', public_key=encoded_key,
            key_id=root.key_id, root_generation=1, challenge=challenge,
            genesis_challenge_digest=full, ceremony_id=str(uuid4()),
            ceremony='OFFLINE_HUMAN_GENESIS', approved=False, activation=False)
        binding['binding_digest'] = digest(binding)
        self.ledger.consume(binding)
        self.audit('GENESIS_CEREMONY_CONFIRMED', {'challenge_digest':full})
        self.audit('GENESIS_BINDING_CREATED', {'binding_digest':binding['binding_digest']})
        return binding


def validate_binding(binding, identity):
    fields = {'version', *identity, 'algorithm','public_key','key_id','root_generation',
        'challenge','genesis_challenge_digest','ceremony_id','ceremony','approved','activation','binding_digest'}
    if type(binding) is not dict or set(binding) != fields:
        raise AuthorityError('Closed Genesis binding required.')
    root = public_root(binding['public_key'])
    if (type(binding['version']) is not int or binding['version'] != 1 or
            any(binding[k]!=v for k,v in identity.items()) or
            binding['algorithm'] != 'Ed25519' or binding['key_id'] != root.key_id or
            type(binding['root_generation']) is not int or binding['root_generation'] != 1 or
            binding['approved'] is not False or binding['activation'] is not False or
            binding['ceremony'] != 'OFFLINE_HUMAN_GENESIS' or
            not valid_format('uuid',binding['ceremony_id']) or
            binding['genesis_challenge_digest'] != digest(binding['challenge']) or
            binding['binding_digest'] != digest({k:v for k,v in binding.items() if k!='binding_digest'})):
        raise AuthorityError('Genesis binding mismatch.')
    challenge=binding['challenge']
    expected = dict(version=1,protocol='bonup-founder-genesis-v1',purpose='FOUNDER_ROOT_GENESIS',
        **identity,algorithm='Ed25519',public_key_digest=root.key_id,key_id=root.key_id,root_generation=1)
    if (type(challenge) is not dict or set(challenge)!=set(expected)|{'nonce','issued_at','expires_at'} or
            any(challenge[k]!=v for k,v in expected.items()) or not valid_format('sha256',challenge['nonce'])):
        raise AuthorityError('Genesis challenge binding mismatch.')
    issued,expires=(datetime.fromisoformat(challenge[k]) for k in ('issued_at','expires_at'))
    if issued.tzinfo is None or expires-issued != timedelta(seconds=300):
        raise AuthorityError('Invalid Genesis lifetime.')
    return root


def receipt_projection(binding):
    root=public_root(binding['public_key'])
    return dict(founder_root_binding_digest=binding['binding_digest'],
        founder_root_policy_digest=binding['founder_root_policy_digest'],
        genesis_challenge_digest=binding['genesis_challenge_digest'], key_id=root.key_id,
        root_generation=1,public_key_artifact_sha256=hashlib.sha256(
            canonical_json(public_artifact(root)).encode()).hexdigest())


def state(candidate, validate_complete, *, binding=None):
    identity=candidate_identity(candidate,validate_complete)
    if binding is None:
        return 'COMPLETE_BUT_ROOT_UNBOUND'
    validate_binding(binding,identity)
    return 'ROOT_BOUND_BUT_UNAPPROVED'


def proposed_approval(candidate, validate_complete, binding):
    """Non-authoritative representation, following the separate binding stage.

    A signed installation decision is still mandatory. No API here installs,
    starts a service or marks installation approval as actually issued.
    """
    identity=candidate_identity(candidate,validate_complete)
    validate_binding(binding,identity)
    value=parse_json(candidate)
    value['founder_root_binding_digest']=binding['binding_digest']
    value['approved']=True
    value['bundle_digest']=digest({k:v for k,v in value.items() if k!='bundle_digest'})
    return dict(state='PROPOSED_APPROVAL_STAGE',installation_manifest=value)
