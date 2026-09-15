"""Admission-closed per-start enrollment, separate from installed authority.

Only a transport's kernel observation callback supplies process identity. Wire
nonces prove freshness on that channel, not possession of a secret or a grant.
"""
from dataclasses import asdict, dataclass
from enum import Enum
from threading import RLock
from uuid import uuid4

from .identity import PeerIdentity, ProcessIdentity
from .protocol import bounded_json, uuid_value
from .schema import valid_format
from .serialization import canonical_json, digest
from .types import AuthorityError, ValidationError


def closed(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValidationError('Unexpected enrollment fields.')


@dataclass(frozen=True)
class InstallationIdentity:
    component: str
    uid: int
    gid: int
    provisioning_generation: int
    bundle_digest: str
    configuration_digest: str
    endpoint: str
    service: str
    capabilities: tuple

    @classmethod
    def parse(cls, value):
        closed(value, cls.__dataclass_fields__)
        component = value['component']
        policy = {
            'controller': (3000, '/run/bonup-agent-supervisor/control.sock', 'bonup-agent-controller.service', ()),
            'supervisor': (0, '/run/bonup-agent-supervisor/control.sock',
                'bonup-agent-supervisor.service',
                ('CAP_SETUID', 'CAP_SETGID', 'CAP_KILL', 'CAP_DAC_READ_SEARCH')),
        }
        if type(component) is not str or component not in policy:
            raise AuthorityError('Unknown service installation identity.')
        uid, endpoint, service, capabilities = policy[component]
        if (any(type(value[k]) is not int for k in ('uid', 'gid', 'provisioning_generation')) or
                value['uid'] != uid or value['gid'] != uid or value['provisioning_generation'] != 1 or
                value['endpoint'] != endpoint or value['service'] != service or
                type(value['capabilities']) is not list or value['capabilities'] != list(capabilities) or
                any(not valid_format('sha256', value[k]) for k in ('bundle_digest', 'configuration_digest'))):
            raise AuthorityError('Invalid immutable service identity.')
        return cls(**dict(value, capabilities=capabilities))

    @property
    def identity_digest(self):
        return digest(dict(asdict(self), capabilities=list(self.capabilities)))


@dataclass(frozen=True)
class Observation:
    peer: PeerIdentity
    process: ProcessIdentity
    service: str

    def validate(self, installation, boot_id):
        p = self.process
        if (type(self.peer) is not PeerIdentity or type(p) is not ProcessIdentity or
                (self.peer.uid, self.peer.gid) != (installation.uid, installation.gid) or
                self.peer.pid != p.pid or p.boot_id != boot_id or
                type(p.start_ticks) is not int or p.start_ticks < 0 or
                self.service != installation.service):
            raise AuthorityError('Kernel service observation mismatch.')
        uuid_value(p.boot_id)


class AdmissionState(str, Enum):
    STARTING = 'STARTING'
    ENROLLMENT_CLOSED = 'ENROLLMENT_CLOSED'
    RECONCILING = 'RECONCILING'
    READY_CLOSED = 'READY_CLOSED'
    ADMISSION_OPEN = 'ADMISSION_OPEN'
    STOPPING = 'STOPPING'


class Admission:
    """One per-start session. STOPPING is irreversible; reconnect needs a new one.

    The same lock serializes close versus the final release call. This is a
    local release linearization point, not a claim of zero-latency termination.
    """
    def __init__(self):
        self.state = AdmissionState.STARTING
        self.session = None
        self.lock = RLock()
        self.verify = None

    def starting(self):
        with self.lock:
            if self.state != AdmissionState.STARTING:
                raise AuthorityError('Enrollment already started.')
            self.state = AdmissionState.ENROLLMENT_CLOSED

    def enrolled(self, session, verify):
        with self.lock:
            if self.state != AdmissionState.ENROLLMENT_CLOSED or not valid_format('sha256', session):
                raise AuthorityError('Fresh enrollment required.')
            verify()
            self.session, self.verify = session, verify
            self.state = AdmissionState.RECONCILING

    def reconciled(self):
        with self.lock:
            if self.state != AdmissionState.RECONCILING:
                raise AuthorityError('Reconciliation out of order.')
            self.verify()
            self.state = AdmissionState.READY_CLOSED

    def open(self, session):
        with self.lock:
            if self.state != AdmissionState.READY_CLOSED or session != self.session:
                raise AuthorityError('Admission requires current reconciled session.')
            self.verify()
            self.state = AdmissionState.ADMISSION_OPEN

    def require_open(self):
        if self.state != AdmissionState.ADMISSION_OPEN:
            raise AuthorityError('Execution admission closed.')
        try:
            self.verify()
        except BaseException:
            self.close()
            raise

    def run(self, operation, *args, **kwargs):
        with self.lock:
            self.require_open()
            return operation(*args, **kwargs)

    def close(self):
        with self.lock:
            self.state = AdmissionState.STOPPING


class Enrollment:
    """Strict four-message challenge/proof; one instance owns one transport.

    observe/local_observe must read kernel state each time. Tests substitute only
    those observations and a BOOTTIME clock; neither comes from received JSON.
    """
    def __init__(self, local, remote, *, local_observe, observe, now):
        if (type(local) is not InstallationIdentity or type(remote) is not InstallationIdentity or
                local.component == remote.component or local.bundle_digest != remote.bundle_digest or
                local.provisioning_generation != remote.provisioning_generation):
            raise AuthorityError('Trusted installation pair required.')
        self.local, self.remote = local, remote
        self.local_observe, self.observe, self.now = local_observe, observe, now
        self.own = local_observe()
        self.boot_id = self.own.process.boot_id
        self.own.validate(local, self.boot_id)
        self.peer = observe()
        self.peer.validate(remote, self.boot_id)
        self.generation = str(uuid4())
        self.nonce = str(uuid4())
        self.deadline = now() + 1
        self.phase, self.transcript = 'NEW', None
        self.admission = Admission()
        self.admission.starting()

    def verify(self):
        if self.admission.state == AdmissionState.STOPPING:
            raise AuthorityError('Disconnected enrollment.')
        current, own = self.observe(), self.local_observe()
        current.validate(self.remote, self.boot_id)
        own.validate(self.local, self.boot_id)
        if current != self.peer or own != self.own:
            raise AuthorityError('Service process/boot replaced.')

    def _guard(self):
        self.verify()
        if self.now() >= self.deadline:
            raise AuthorityError('Enrollment timeout.')

    def _message(self, action, data):
        value = dict(version=1, action=action, data=data)
        if len(canonical_json(value).encode()) > 4096:
            raise ValidationError('Enrollment frame bound exceeded.')
        return value

    def begin(self):
        if self.local.component != 'controller' or self.phase != 'NEW':
            self.disconnect()
            raise AuthorityError('Enrollment begin replay.')
        self._guard()
        self.phase = 'BEGIN'
        return self._message('ENROLL_BEGIN', dict(installation=self.local.identity_digest,
            expected=self.remote.identity_digest, nonce=self.nonce, generation=self.generation))

    def receive(self, raw):
        try:
            self._guard()
            if type(raw) is not bytes or len(raw) > 4096:
                raise ValidationError('Bounded enrollment JSON required.')
            value = bounded_json(raw)
            closed(value, ('version', 'action', 'data'))
            if type(value['version']) is not int or value['version'] != 1:
                raise ValidationError('Unsupported enrollment version.')
            action, data = value['action'], value['data']
            if self.local.component == 'supervisor' and self.phase == 'NEW':
                closed(data, ('installation', 'expected', 'nonce', 'generation'))
                if (action != 'ENROLL_BEGIN' or data['installation'] != self.remote.identity_digest or
                        data['expected'] != self.local.identity_digest):
                    raise AuthorityError('Installed peer mismatch.')
                uuid_value(data['nonce']); uuid_value(data['generation'])
                self.transcript = dict(controller=data, supervisor=dict(
                    installation=self.local.identity_digest, expected=self.remote.identity_digest,
                    nonce=self.nonce, generation=self.generation))
                self.phase = 'CHALLENGE'
                return self._message('ENROLL_CHALLENGE', self.transcript)
            if self.local.component == 'controller' and self.phase == 'BEGIN':
                closed(data, ('controller', 'supervisor'))
                expected = dict(installation=self.local.identity_digest, expected=self.remote.identity_digest,
                                nonce=self.nonce, generation=self.generation)
                closed(data['supervisor'], ('installation', 'expected', 'nonce', 'generation'))
                peer = data['supervisor']
                if (action != 'ENROLL_CHALLENGE' or data['controller'] != expected or
                        peer['installation'] != self.remote.identity_digest or peer['expected'] != self.local.identity_digest):
                    raise AuthorityError('Challenge binding mismatch.')
                uuid_value(peer['nonce']); uuid_value(peer['generation'])
                self.transcript = data
                self.phase = 'PROOF'
                return self._message('ENROLL_PROOF', dict(session=self.session))
            closed(data, ('session',))
            if data['session'] != self.session:
                raise AuthorityError('Stale enrollment session.')
            if self.local.component == 'supervisor' and self.phase == 'CHALLENGE' and action == 'ENROLL_PROOF':
                self.phase = 'ACCEPTED'
                self.admission.enrolled(self.session, self.verify)
                return self._message('ENROLL_ACCEPTED', dict(session=self.session))
            if self.local.component == 'controller' and self.phase == 'PROOF' and action == 'ENROLL_ACCEPTED':
                self.phase = 'ACCEPTED'
                self.admission.enrolled(self.session, self.verify)
                return None
            raise AuthorityError('Enrollment replay or unexpected message.')
        except BaseException:
            self.disconnect()
            raise

    @property
    def session(self):
        if self.transcript is None:
            raise AuthorityError('No enrollment transcript.')
        observations = {self.local.component: asdict(self.own), self.remote.component: asdict(self.peer)}
        return digest(dict(transcript=self.transcript, observations=observations))

    def peer_enrollment(self):
        from .service_runtime import PeerEnrollment
        if self.phase != 'ACCEPTED':
            raise AuthorityError('Enrollment incomplete.')
        self.verify()
        return PeerEnrollment(self.remote.component, self.peer.peer.uid, self.peer.peer.gid,
            self.peer.process, self.transcript[self.remote.component]['generation'],
            self.transcript[self.remote.component]['nonce'])

    def disconnect(self):
        self.admission.close()


def installation_spec(component):
    """Resolved static policy; deliberately contains no process, boot or session."""
    if component not in ('controller', 'supervisor'):
        raise ValidationError('Unknown service.')
    controller = component == 'controller'
    return dict(component=component, uid=3000 if controller else 0, gid=3000 if controller else 0,
        provisioning_generation=1, endpoint='/run/bonup-agent-supervisor/control.sock', service='bonup-agent-'+component+'.service',
        capabilities=[] if controller else ['CAP_SETUID','CAP_SETGID','CAP_KILL','CAP_DAC_READ_SEARCH'])


def installation_pair(configuration, manifest, component):
    """Component digests bind full immutable config without circular self-hashes."""
    peer = 'supervisor' if component == 'controller' else 'controller'
    expected = installation_spec(component)
    if canonical_json(configuration['service']) != canonical_json(expected):
        raise AuthorityError('Installation configuration includes unknown or operational identity.')
    return tuple(InstallationIdentity.parse(dict(installation_spec(name),
        bundle_digest=manifest['bundle_digest'], configuration_digest=manifest['configuration_digests'][name]))
        for name in (component, peer))
