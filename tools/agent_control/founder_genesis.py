"""Offline human Genesis contract, never a runtime enrollment operation.

The offline ceremony adapter and its durable ledger are trust-boundary inputs.
They must not be constructed from an RPC/JSON request. The default adapter is
unavailable: there is no production auto-confirm or software signing fallback.
"""
import base64
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from .founder_crypto import FounderRoot, PURPOSES
from .founder_key_validation import validate_public_key, DEPENDENCY
from .serialization import canonical_json, digest, parse_json
from .schema import valid_format
from .types import AuthorityError, ValidationError

DOMAIN = 'bonup-founder-genesis'
BINDING_PATH = '/etc/bonup-agent-control/founder-root-binding.json'
EVIDENCE_PATH = '/etc/bonup-agent-control/founder-genesis-evidence.json'
PUBLIC_PATH = '/etc/bonup-agent-control/founder-root.json'
PREFLIGHT_MARKERS = (
    'founder_root', 'founder_root_binding', 'founder_genesis_evidence',
    'authority_installation_receipt', 'consumed_ledger_evidence',
)
_LEDGER_SCHEMA = 'CREATE TABLE genesis(domain TEXT PRIMARY KEY,state TEXT NOT NULL,evidence TEXT NOT NULL)'
_LEDGER_STATES = frozenset(('VIRGIN', 'CONSUMED'))


def _authority(message):
    raise AuthorityError(message)


def _repository_roots():
    roots = []
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        current = start
        while True:
            if (current / '.git').exists() and current not in roots:
                roots.append(current)
            if current.parent == current:
                break
            current = current.parent
    return roots


def _under(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _ancestor_is_replaceable(info):
    mode = info.st_mode
    return bool(mode & 0o022) and not bool(mode & stat.S_ISVTX)


def _ledger_path(value, *, exists):
    if not isinstance(value, (str, Path)) or not str(value) or not Path(value).is_absolute():
        _authority('Explicit absolute offline ledger path required.')
    path = Path(value)
    if '..' in path.parts:
        _authority('Offline ledger parent traversal denied.')
    try:
        resolved = path.resolve(strict=False)
    except OSError as error:
        raise AuthorityError('Offline ledger path cannot be resolved safely.') from error
    if any(_under(resolved, root) for root in _repository_roots()):
        _authority('Offline ledger must remain outside the repository checkout.')

    parent = path.parent
    current = Path(path.anchor)
    for part in parent.parts[1:]:
        current /= part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            _authority('Offline ledger parent must already exist.')
        except OSError as error:
            raise AuthorityError('Offline ledger parent cannot be inspected safely.') from error
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or
                _ancestor_is_replaceable(info)):
            _authority('Offline ledger parent must be a real directory.')
    try:
        parent_info = os.stat(parent)
    except OSError as error:
        raise AuthorityError('Offline ledger parent cannot be inspected safely.') from error
    if _ancestor_is_replaceable(parent_info):
        _authority('Offline ledger parent is group/world writable.')
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if exists:
            _authority('Offline ledger does not exist.')
        return path
    except OSError as error:
        raise AuthorityError('Offline ledger target cannot be inspected safely.') from error
    if not exists:
        _authority('Offline ledger target already exists; reset is forbidden.')
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or
            info.st_nlink != 1 or (info.st_mode & 0o077) or
            (info.st_mode & 0o111) or (info.st_mode & 0o600) != 0o600):
        _authority('Offline ledger file safety validation failed.')
    return path


class _OwnedSQLiteConnection(sqlite3.Connection):
    """SQLite connection retaining the exact exclusive-open file descriptor."""
    def __init__(self, *args, ledger_fd=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._ledger_fd = ledger_fd

    def close(self):
        fd, self._ledger_fd = self._ledger_fd, None
        try:
            return super().close()
        finally:
            if fd is not None:
                os.close(fd)


def _sqlite_fd_path(fd):
    return f'/proc/self/fd/{fd}'


def _connect_exact_fd(fd):
    return sqlite3.connect(_sqlite_fd_path(fd),
        factory=lambda *args, **kwargs: _OwnedSQLiteConnection(
            *args, ledger_fd=fd, **kwargs))


def _file_identity(info):
    return info.st_dev, info.st_ino


def _path_matches(path, identity):
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise AuthorityError('Offline ledger pathname cannot be verified.') from error
    return stat.S_ISREG(info.st_mode) and _file_identity(info) == identity


def _remove_created(path, identity):
    """Remove only the file created by this attempt, never a replacement."""
    try:
        info = os.stat(path, follow_symlinks=False)
        if (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                _file_identity(info) == identity):
            os.unlink(path)
    except OSError:
        pass


def _invalidate_created(fd):
    """Destroy any partially initialized state before releasing a created inode."""
    try:
        os.ftruncate(fd, 0)
        os.fsync(fd)
    except OSError:
        pass


def _normal_sql(value):
    return re.sub(r'\s+', '', value).lower()


def _clean_preflight(markers):
    if type(markers) is not dict or set(markers) != set(PREFLIGHT_MARKERS):
        _authority('Complete prior-Genesis preflight evidence required.')
    if any(markers[name] is not None for name in PREFLIGHT_MARKERS):
        _authority('Prior Founder Genesis evidence denies initialization.')


def _ledger_identity(binding):
    identity = {
        key: binding.get(key) for key in (
            'source_commit', 'candidate_manifest_digest',
            'candidate_bundle_digest', 'provisioning_generation',
            'founder_root_policy_digest',
        )
    }
    if (not valid_format('git-oid', identity['source_commit']) or
            any(not valid_format('sha256', identity[key]) for key in (
                'candidate_manifest_digest', 'candidate_bundle_digest',
                'founder_root_policy_digest')) or
            identity['founder_root_policy_digest'] != digest(policy()) or
            type(identity['provisioning_generation']) is not int or
            identity['provisioning_generation'] != 2):
        _authority('Genesis binding candidate identity invalid.')
    return identity


def _validate_ledger_binding(binding):
    if type(binding) is not dict:
        _authority('Closed Genesis binding required.')
    identity = _ledger_identity(binding)
    validate_binding(binding, identity)
    encoded = canonical_json(binding)
    if len(encoded.encode('utf-8')) > 65536:
        _authority('Genesis binding exceeds the bounded evidence size.')
    return deepcopy(binding)


def policy():
    return dict(version=1, enabled=True, algorithm='Ed25519',
        verifier='/usr/bin/openssl', operation='VERIFY_ONLY', roots=1, root_generation=1,
        purposes=list(PURPOSES), encoding='RFC4648_BASE64_RAW_32_BYTES',
        key_id='SHA256_RAW_PUBLIC_KEY_HEX', private_key='EXTERNAL_ONLY',
        genesis='OFFLINE_HUMAN_CEREMONY_REQUIRED', rotation=False,
        binding='REQUIRED_BEFORE_INSTALLATION_APPROVAL',
        session_seconds=60, genesis_seconds=300, replay='ONE_USE_BOOT_PROCESS_PURPOSE_BOUND',
        activation=False, public_key_validation=dict(DEPENDENCY))


def public_root(encoded):
    if type(encoded) is not str or len(encoded) != 44:
        raise ValidationError('One canonical Ed25519 public key required.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise ValidationError('Malformed Ed25519 public key.') from error
    if len(raw) != 32 or base64.b64encode(raw).decode() != encoded:
        raise ValidationError('Noncanonical Ed25519 public key.')
    validate_public_key(raw)
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
    """Bounded SQLite contract for the one-time offline trust domain.

    Required table: genesis(domain TEXT PRIMARY KEY, state TEXT NOT NULL,
    evidence TEXT NOT NULL). Initialization requires an explicit clean
    prior-Genesis preflight and never resets an existing target. Missing,
    deleted, corrupt, or noncanonical state denies Genesis. SQLite transaction
    serialization consumes before publishing the binding.
    """
    def __init__(self, db):
        self.db = db
        self._filesystem_identity = None

    @classmethod
    def initialize_virgin(cls, path, *, preflight):
        """Create one new offline ledger; never open or reset an existing one."""
        _clean_preflight(preflight)
        path = _ledger_path(path, exists=False)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except (FileExistsError, OSError) as error:
            raise AuthorityError('Offline ledger target cannot be created safely.') from error
        db = None
        identity = _file_identity(os.fstat(fd))
        try:
            db = _connect_exact_fd(fd)
            _ledger_path(path, exists=True)
            if not _path_matches(path, identity):
                _authority('Offline ledger path changed during creation.')
            with db:
                db.execute('PRAGMA journal_mode=DELETE')
                db.execute('PRAGMA synchronous=FULL')
                db.execute(_LEDGER_SCHEMA)
                db.execute('INSERT INTO genesis VALUES (?,?,?)', (DOMAIN, 'VIRGIN', '{}'))
            _ledger_path(path, exists=True)
            if not _path_matches(path, identity):
                _authority('Offline ledger path changed during initialization.')
            ledger = cls(db)
            ledger._filesystem_identity = identity
            ledger._verify_database()
            ledger.require_virgin()
            return ledger
        except BaseException as error:
            if db is not None:
                _invalidate_created(fd)
                db.close()
            else:
                os.close(fd)
            _remove_created(path, identity)
            if isinstance(error, AuthorityError):
                raise
            if isinstance(error, (sqlite3.DatabaseError, OSError, ValidationError)):
                raise AuthorityError('Offline ledger initialization failed closed.') from error
            raise

    @classmethod
    def open_and_verify(cls, path):
        """Open an existing ledger without creating, repairing, or resetting it."""
        path = _ledger_path(path, exists=True)
        db = None
        fd = None
        try:
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            identity = _file_identity(os.fstat(fd))
            db = _connect_exact_fd(fd)
            _ledger_path(path, exists=True)
            if not _path_matches(path, identity):
                _authority('Offline ledger identity changed while opening.')
            ledger = cls(db)
            ledger._filesystem_identity = identity
            ledger._verify_database()
            return ledger
        except BaseException as error:
            if db is not None:
                db.close()
            elif fd is not None:
                os.close(fd)
            if isinstance(error, AuthorityError):
                raise
            if isinstance(error, (sqlite3.DatabaseError, OSError, ValidationError)):
                raise AuthorityError('Offline ledger open or verification failed.') from error
            raise

    def _verify_schema(self):
        objects = self.db.execute(
            "SELECT type,name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
        if len(objects) != 1 or objects[0][0] != 'table' or objects[0][1] != 'genesis':
            _authority('Offline ledger schema is not exact.')
        if _normal_sql(objects[0][2]) != _normal_sql(_LEDGER_SCHEMA):
            _authority('Offline ledger schema is not exact.')
        columns = self.db.execute('PRAGMA table_info(genesis)').fetchall()
        if columns != [
                (0, 'domain', 'TEXT', 0, None, 1),
                (1, 'state', 'TEXT', 1, None, 0),
                (2, 'evidence', 'TEXT', 1, None, 0)]:
            _authority('Offline ledger columns are not exact.')

    def _verify_database(self):
        try:
            if self.db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                _authority('Offline ledger integrity check failed.')
            self._verify_schema()
            rows = self.db.execute(
                'SELECT domain,state,evidence FROM genesis ORDER BY domain'
            ).fetchall()
        except sqlite3.DatabaseError as error:
            raise AuthorityError('Offline ledger verification failed.') from error
        if len(rows) != 1 or rows[0][0] != DOMAIN or rows[0][1] not in _LEDGER_STATES:
            _authority('Offline ledger row is invalid.')
        state, evidence = rows[0][1], rows[0][2]
        if state == 'VIRGIN':
            if evidence != '{}':
                _authority('VIRGIN ledger evidence must be empty.')
            return state, None
        if type(evidence) is not str or len(evidence.encode('utf-8')) > 65536:
            _authority('CONSUMED ledger evidence exceeds the bounded size.')
        try:
            parsed = parse_json(evidence)
        except ValidationError as error:
            raise AuthorityError('CONSUMED ledger evidence is not canonical JSON.') from error
        if canonical_json(parsed) != evidence:
            _authority('CONSUMED ledger evidence is not canonical JSON.')
        try:
            binding = _validate_ledger_binding(parsed)
        except (AuthorityError, ValidationError) as error:
            raise AuthorityError('CONSUMED ledger binding is invalid.') from error
        return state, binding

    def require_virgin(self):
        state, _ = self._verify_database()
        if state != 'VIRGIN':
            raise AuthorityError('Genesis unavailable: absent or previously consumed trust domain.')

    def consume(self, evidence):
        binding = _validate_ledger_binding(evidence)
        self._verify_database()
        with self.db:
            result = self.db.execute('UPDATE genesis SET state=?,evidence=? '
                'WHERE domain=? AND state=? AND evidence=?',
                ('CONSUMED', canonical_json(binding), DOMAIN, 'VIRGIN', '{}'))
            if result.rowcount != 1:
                raise AuthorityError('Genesis already consumed or state unavailable.')

    def recover_consumed_evidence(self):
        state, binding = self._verify_database()
        if state != 'CONSUMED' or binding is None:
            raise AuthorityError('Consumed Genesis evidence required.')
        return deepcopy(binding)


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
            self.audit('GENESIS_KEY_DENIED', {'reason':'INVALID_FOUNDER_ROOT_KEY'})
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
