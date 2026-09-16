"""Fixed service startup contracts and nonblocking authenticated control pump.

No sockets, threads, daemons or privileged backends are created by this module.
Adapters are trusted installation code, never imported or selected from JSON.
Their accept/read/send/submit/take_result/poll methods MUST be nonblocking. Normal
work is queued, not invoked on this pump; an installed executor is a later block.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import stat

from .composition_protocol import FrameReader, frame
from .identity import PeerIdentity, ProcessIdentity
from .protocol import bounded_json, uuid_value
from .schema import valid_format
from .types import AuthorityError, ValidationError


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValidationError('Unexpected service configuration fields.')


def installed_json(path):
    """Read a bounded root-owned immutable config through retained directory FDs."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or str(path) != os.path.normpath(str(path)):
        raise ValidationError('Canonical installed configuration required.')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for i, part in enumerate(path.parts[1:]):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            if i < len(path.parts) - 2:
                flags |= os.O_DIRECTORY
            nxt = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = nxt
            info = os.fstat(fd)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise AuthorityError('Configuration must be root controlled.')
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4096:
            raise ValidationError('Invalid installed configuration file.')
        raw = os.read(fd, 4097)
        if len(raw) > 4096:
            raise ValidationError('Configuration too large.')
        return bounded_json(raw)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class PeerEnrollment:
    endpoint: str
    uid: int
    gid: int
    process: ProcessIdentity
    generation: str
    enrollment_id: str

    @classmethod
    def parse(cls, data, *, component, boot_id):
        keys(data, ('endpoint', 'uid', 'gid', 'pid', 'start_ticks', 'boot_id', 'generation', 'enrollment_id'))
        expected = ('supervisor', 0) if component == 'controller' else ('controller', 3000)
        if (data['endpoint'] != expected[0] or type(data['uid']) is not int or
                type(data['gid']) is not int or (data['uid'], data['gid']) != (expected[1], expected[1]) or
                data['boot_id'] != boot_id or type(data['pid']) is not int or data['pid'] <= 0 or
                type(data['start_ticks']) is not int or data['start_ticks'] < 0):
            raise AuthorityError('Invalid enrolled service peer.')
        uuid_value(data['generation']); uuid_value(data['enrollment_id'])
        return cls(data['endpoint'], data['uid'], data['gid'],
                   ProcessIdentity(boot_id, data['pid'], data['start_ticks']),
                   data['generation'], data['enrollment_id'])


@dataclass(frozen=True)
class ServiceConfig:
    component: str
    generation: str
    boot_id: str
    manifest_digest: str
    peer: PeerEnrollment
    registry_path: str | None

    @classmethod
    def parse(cls, value, *, component, identity, boot_id, manifest_digest):
        if component not in {'controller', 'supervisor'}:
            raise ValidationError('Unknown fixed service component.')
        keys(value, ('version', 'component', 'approved', 'generation', 'boot_id',
                     'manifest_digest', 'peer', 'registry_path'))
        if (type(value['version']) is not int or value['version'] != 1 or
                value['approved'] is not True or value['component'] != component or
                value['boot_id'] != boot_id or not valid_format('sha256', manifest_digest) or
                value['manifest_digest'] != manifest_digest):
            raise AuthorityError('Unapproved or mismatched service configuration.')
        expected = (3000, 3000) if component == 'controller' else (0, 0)
        if type(identity) is not PeerIdentity or (identity.uid, identity.gid) != expected:
            raise AuthorityError('Incorrect service process identity.')
        uuid_value(value['generation']); uuid_value(boot_id)
        registry = value['registry_path']
        if component == 'supervisor':
            if registry is not None:
                raise AuthorityError('Supervisor configuration cannot reference controller SQLite.')
        elif registry != '/var/lib/bonup-agent-control/control.sqlite3':
            raise AuthorityError('Fixed installed registry path required.')
        peer = PeerEnrollment.parse(value['peer'], component=component, boot_id=boot_id)
        return cls(component, value['generation'], boot_id, manifest_digest, peer, registry)


class PeerAuthenticator:
    """One enrolled service connection per generation; reconnect needs reenrollment.

    observed_peer comes from kernel credentials (actual-sender SCM_CREDENTIALS
    for activated service channels). Process identity is independently observed
    from the kernel. Neither may be decoded from the handshake.
    Generation/enrollment claims merely select an already trusted enrollment.
    """
    def __init__(self, enrollment):
        if type(enrollment) is not PeerEnrollment:
            raise AuthorityError('Trusted peer enrollment required.')
        self.enrollment, self.used = enrollment, False

    def verify(self, observed_peer, observed_process, handshake, *, consume=False):
        keys(handshake, ('endpoint', 'generation', 'enrollment_id'))
        e = self.enrollment
        if (type(observed_peer) is not PeerIdentity or type(observed_process) is not ProcessIdentity or
                type(observed_process.pid) is not int or type(observed_process.start_ticks) is not int or
                observed_peer != PeerIdentity(e.uid, e.gid, e.process.pid) or observed_process != e.process or
                handshake != dict(endpoint=e.endpoint, generation=e.generation, enrollment_id=e.enrollment_id)):
            raise AuthorityError('Service peer authentication failed.')
        if consume:
            if self.used:
                raise AuthorityError('Enrollment replay; reconnect requires new enrollment.')
            self.used = True


class ServiceLoop:
    """One authenticated connection, one queued job, independent maintenance lanes.

    Transport.poll returns at most four events: ('data', bytes), ('end', b'') for
    frame end, or ('disconnect', b''). Frame end is distinct from loss of the
    enrolled connection. An eventual Unix adapter must preserve that distinction.
    Work.submit queues one request and take_result returns immediately with None
    while it is pending. It must never execute a blocking handler on this pump.
    """
    def __init__(self, config, transport, work, *, now, deadlines, control, heartbeat,
                 disconnect, notifier, peer_alive=lambda: None, ready_evidence=None):
        self.config, self.transport, self.work = config, transport, work
        self.now, self.deadlines, self.control = now, deadlines, control
        self.heartbeat, self.disconnect, self.notifier = heartbeat, disconnect, notifier
        self.peer_alive = peer_alive
        self.ready_evidence = ready_evidence or (lambda: self.ready)
        self.auth = PeerAuthenticator(config.peer)
        self.ready = False
        self.stopped = False
        self.connected = False
        self.reader = None
        self.pending = None
        self.seen = set()
        self.last_peer = now()
        self.last_watchdog = now()

    def activate(self):
        if self.ready or self.stopped:
            raise AuthorityError('Invalid service activation.')
        self.deadlines()  # Must be armed/serviced before readiness, even without traffic.
        self.control()
        self.ready = True
        self.notifier('READY=1')

    def shutdown(self):
        if self.stopped:
            return
        self.stopped = True
        self.ready = False
        try:
            self.notifier('STOPPING=1')
        finally:
            try:
                self.work.cancel()
            finally:
                try:
                    self.disconnect()
                finally:
                    self.transport.close()

    def step(self):
        if not self.ready or self.stopped:
            raise AuthorityError('Service is not ready.')
        try:
            # These run even with incomplete input or a pending normal request.
            self.deadlines()
            self.control()
            self.heartbeat()
            now = self.now()
            if not self.connected:
                accepted = self.transport.accept()  # Nonblocking; returns kernel observations + handshake.
                if accepted is not None:
                    self.auth.verify(*accepted, consume=True)
                    self.connected = True
                    self.last_peer = now
            if self.connected:
                # Revalidate PID/start/boot on every iteration, not just initial acceptance.
                self.auth.verify(*self.transport.identity())
                events = self.transport.poll(4)
                if type(events) is not list or len(events) > 4:
                    raise AuthorityError('Transport exceeded bounded event contract.')
                for kind, payload in events:
                    if kind == 'disconnect':
                        raise AuthorityError('Enrolled peer disconnected.')
                    if kind not in {'data', 'end'} or type(payload) is not bytes or (kind == 'end' and payload):
                        raise ValidationError('Invalid transport event.')
                    if self.reader is None:
                        self.reader = FrameReader(now=now)
                    request = self.reader.feed(payload, now=now, eof=kind == 'end')
                    if request is None:
                        continue
                    self.reader = None
                    expected_generation = (self.config.generation if self.config.component == 'supervisor'
                                           else self.config.peer.generation)
                    if request['boot_id'] != self.config.boot_id or request['generation'] != expected_generation:
                        raise AuthorityError('Stale wire generation/boot.')
                    if request['request_id'] in self.seen or len(self.seen) >= 4096:
                        raise AuthorityError('Message replay or generation capacity reached.')
                    self.seen.add(request['request_id'])
                    self.last_peer = now
                    self.peer_alive()
                    if request['action'] == 'HEARTBEAT':
                        if not request['data']['ready']:
                            raise AuthorityError('Peer stopped admission.')
                        if self.config.component == 'supervisor':
                            ready = self.ready_evidence()
                            if type(ready) is not bool:
                                raise AuthorityError('Unknown admission evidence.')
                            self.transport.send(frame(dict(request, data=dict(ready=ready))))
                        continue
                    allowed = ({'PREPARE_LAUNCH', 'RELEASE_LAUNCH', 'STOP_LAUNCH', 'RECONCILE', 'STATUS_LAUNCH', 'OPEN_ADMISSION',
                                'OPEN_HOST_TEST_ADMISSION','CLOSE_HOST_TEST_ADMISSION'}
                               if self.config.component == 'supervisor' else
                               {'PREPARED_EVIDENCE', 'RUNNING_EVIDENCE', 'CLEANUP_EVIDENCE', 'STATUS_EVIDENCE'})
                    if request['action'] not in allowed or self.pending is not None:
                        raise AuthorityError('Unexpected direction or concurrent work.')
                    self.pending = request
                    self.work.submit(request)
                if self.reader is not None:
                    self.reader.feed(b'', now=now)  # Expire stalled partial frame without waiting.
                if now - self.last_peer >= 2:
                    raise AuthorityError('Peer heartbeat expired.')
            if self.pending is not None:
                result = self.work.take_result()  # Nonblocking; pending jobs cannot delay maintenance.
                if result is not None:
                    if self.config.component == 'controller':
                        # Evidence consumption produces no execution-bearing response.
                        keys(result, ('consumed_request_id',))
                        if result['consumed_request_id'] != self.pending['request_id']:
                            raise AuthorityError('Uncorrelated evidence consumption.')
                        self.pending = None
                        result = None
                if result is not None:
                    raw = frame(result)
                    if any(result[k] != self.pending[k] for k in ('request_id', 'launch_id', 'generation', 'boot_id')):
                        raise AuthorityError('Uncorrelated work result.')
                    expected = {'PREPARE_LAUNCH':'PREPARED_EVIDENCE', 'RELEASE_LAUNCH':'RUNNING_EVIDENCE',
                                'STOP_LAUNCH':'CLEANUP_EVIDENCE', 'RECONCILE':'CLEANUP_EVIDENCE',
                                'STATUS_LAUNCH':'STATUS_EVIDENCE', 'OPEN_ADMISSION':'ADMISSION_EVIDENCE',
                                'OPEN_HOST_TEST_ADMISSION':'HOST_TEST_ADMISSION_EVIDENCE',
                                'CLOSE_HOST_TEST_ADMISSION':'HOST_TEST_ADMISSION_EVIDENCE'}
                    if result['action'] != expected[self.pending['action']]:
                        raise AuthorityError('Unexpected response action.')
                    self.transport.send(raw)  # Bounded nonblocking enqueue; backpressure must raise.
                    self.pending = None
            if now - self.last_watchdog >= .25:
                self.notifier('WATCHDOG=1')
                self.last_watchdog = now
        except BaseException:
            self.shutdown()
            raise

    def run(self, shutdown_requested, wait):
        """wait is an injected bounded readiness wait, never a request handler."""
        try:
            while not shutdown_requested():
                self.step()
                wait(.05)
        finally:
            self.shutdown()
