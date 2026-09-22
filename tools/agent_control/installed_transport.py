"""AF_UNIX-only, bounded installed transport primitives. No listeners on import.

Socket creation is explicit. Tests supply temporary AF_UNIX sockets; installed
callers use fixed paths. There is no TCP, environment or adapter-module fallback.
"""
import os
import re
import socket
import stat
import struct
import time
from pathlib import Path
from uuid import uuid4

from .identity import PeerIdentity, ProcessIdentity
from .protocol import bounded_json
from .serialization import canonical_json
from .service_runtime import PeerAuthenticator
from .types import AuthorityError, ValidationError

PATHS = frozenset(('/run/bonup-agent-control/founder.sock',
    '/run/bonup-agent-control/proposals.sock', '/run/bonup-agent-supervisor/control.sock'))
LIMIT = 4096


class SenderSocket:
    """Require kernel credentials on every read, including activated sockets.

    SO_PEERCRED describes the listener creator on the connecting end. It is
    deliberately never consulted here. The one-byte prelude observes the actual
    sender before the enrollment transcript is constructed; it grants nothing.
    """
    def __init__(self, sock, uid, gid):
        self.socket = local_socket(sock)
        self.uid, self.gid, self.sender = uid, gid, None
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)

    def __getattr__(self, name):
        return getattr(self.socket, name)

    def recv(self, size, flags=0):
        import array
        raw, ancillary, status, _ = self.socket.recvmsg(size,
            socket.CMSG_SPACE(12) + socket.CMSG_SPACE(256), flags | socket.MSG_CMSG_CLOEXEC)
        credentials = []
        invalid = bool(status & (socket.MSG_CTRUNC | socket.MSG_TRUNC))
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                pid, uid, gid = struct.unpack('3i', data)
                credentials.append(PeerIdentity(uid, gid, pid))
            else:
                invalid = True
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    fds = array.array('i')
                    fds.frombytes(data[:len(data) - len(data) % fds.itemsize])
                    for fd in fds: os.close(fd)
        if not raw and not ancillary:
            return raw  # EOF is handled as disconnect, never as authentication.
        if invalid or len(credentials) != 1:
            raise AuthorityError('Missing or unexpected kernel sender credentials.')
        peer = credentials[0]
        if ((peer.uid, peer.gid) != (self.uid, self.gid) or
                self.sender is not None and peer != self.sender):
            raise AuthorityError('Operational sender changed.')
        self.sender = peer
        return raw

    def authenticate_sender(self):
        self.socket.settimeout(1)
        # Explicit credentials also cover the race where the other end has not
        # enabled PASSCRED yet. Linux validates these against the sending task.
        own = struct.pack('3i', os.getpid(), os.geteuid(), os.getegid())
        if self.socket.sendmsg([b'K'], [(socket.SOL_SOCKET, socket.SCM_CREDENTIALS, own)]) != 1:
            raise AuthorityError('Incomplete sender prelude.')
        if self.recv(1) != b'K' or self.sender is None:
            raise AuthorityError('Missing actual service sender.')
        return self


class Packet:
    def __init__(self, now, timeout=1, limit=LIMIT):
        if type(limit) is not int or not 1 <= limit <= 65536:
            raise ValidationError('Unix frame bound is invalid.')
        self.deadline = now + timeout
        self.limit = limit
        self.buffer = bytearray()
        self.size = None

    @property
    def wanted(self):
        return (4 if self.size is None else self.size + 4) - len(self.buffer)

    def feed(self, chunk, now):
        if now >= self.deadline or type(chunk) is not bytes or not chunk:
            raise AuthorityError('Unix frame expired/disconnected.')
        if len(chunk) + len(self.buffer) > self.limit + 4:
            raise ValidationError('Unix frame exceeds bound.')
        self.buffer.extend(chunk)
        if len(self.buffer) >= 4:
            self.size = struct.unpack('!I', self.buffer[:4])[0]
            if not 0 < self.size <= self.limit or len(self.buffer) > self.size + 4:
                raise ValidationError('Invalid/pipelined Unix frame.')
            if len(self.buffer) == self.size + 4:
                bounded_json(bytes(self.buffer[4:]))
                return bytes(self.buffer)
        return None


def packet(value, limit=LIMIT):
    raw = canonical_json(value).encode()
    if type(limit) is not int or not 1 <= limit <= 65536 or not 0 < len(raw) <= limit:
        raise ValidationError('Unix message exceeds bound.')
    return struct.pack('!I', len(raw)) + raw


def local_socket(sock):
    if sock.family != socket.AF_UNIX or sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM:
        raise AuthorityError('AF_UNIX stream required.')
    sock.set_inheritable(False)
    return sock


_PROJECTION_REASON = re.compile(r'^[A-Z0-9_]{1,64}$')


class ProjectionTransportUnavailable(Exception):
    """The configured local Django peer cannot be reached or authenticated."""


class ProjectionTransportRejected(Exception):
    """The peer rejected an invalid or untrusted projection request."""

    def __init__(self, reason):
        if type(reason) is not str or not _PROJECTION_REASON.fullmatch(reason):
            reason = 'TRANSPORT_RESPONSE_INVALID'
        self.reason = reason
        super().__init__(reason)


class ProjectionTransportFailure(Exception):
    """The trusted peer could not commit one projection transaction."""

    def __init__(self, reason):
        if type(reason) is not str or not _PROJECTION_REASON.fullmatch(reason):
            reason = 'CONSUMER_RUNTIME_FAILURE'
        self.reason = reason
        super().__init__(reason)


def _secure_socket_ancestors(path):
    path = Path(path)
    if (not path.is_absolute() or '..' in path.parts or str(path) != os.path.normpath(str(path))
            or '\0' in str(path) or len(str(path).encode()) > 107):
        raise AuthorityError('Canonical projection socket path required.')
    parent = path.parent
    for node in (parent, *parent.parents):
        info = node.lstat()
        if node.is_symlink() or info.st_mode & 0o022:
            raise AuthorityError('Writable projection socket ancestor.')
    return path


def validate_projection_socket(path, *, owner_uid, group_gid, mode):
    """Verify an existing socket and every ancestor before connecting to it."""
    path = _secure_socket_ancestors(path)
    info = path.lstat()
    if (path.is_symlink() or not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != owner_uid or info.st_gid != group_gid
            or stat.S_IMODE(info.st_mode) != mode):
        raise AuthorityError('Projection socket identity or mode mismatch.')
    return path


def projection_peer(sock, *, uid, gid, process_reader=ProcessIdentity.read):
    peer = PeerIdentity.from_socket(sock)
    if (peer.uid, peer.gid) != (uid, gid):
        raise AuthorityError('Unexpected projection peer.')
    process = process_reader(peer.pid)
    process.verify(process_reader)
    return peer, process


class DjangoProjectionClient:
    """One bounded request to the root-configured Django projection socket."""

    def __init__(self, config, *, process_reader=ProcessIdentity.read, now=time.monotonic):
        required = ('socket_path', 'socket_mode', 'agent_control_uid', 'agent_control_gid',
                    'django_uid', 'django_gid', 'timeout_ms', 'max_message_bytes')
        if any(getattr(config, field, None) is None for field in required):
            raise ValidationError('Complete projection transport configuration required.')
        if (os.geteuid(), os.getegid()) != (
                config.agent_control_uid, config.agent_control_gid):
            raise AuthorityError('Agent Control process identity mismatch.')
        self.config = config
        self.process_reader = process_reader
        self.now = now

    def _receive(self, sock):
        timeout = self.config.timeout_ms / 1000
        reader = Packet(self.now(), timeout=timeout, limit=self.config.max_message_bytes)
        while True:
            remaining = reader.deadline - self.now()
            if remaining <= 0:
                raise ProjectionTransportUnavailable()
            sock.settimeout(remaining)
            try:
                chunk = sock.recv(reader.wanted)
            except (socket.timeout, TimeoutError, ConnectionError, OSError):
                raise ProjectionTransportUnavailable() from None
            if not chunk:
                raise ProjectionTransportUnavailable()
            complete = reader.feed(chunk, self.now())
            if complete is not None:
                try:
                    return bounded_json(complete[4:])
                except ValidationError:
                    raise ProjectionTransportRejected('TRANSPORT_RESPONSE_INVALID') from None

    def deliver(self, event, consumer_name, proposal_projection=None):
        from .records import PRODUCT_REVIEW_EVENT_CONSUMERS, ProductReviewCompletedEvent

        if (type(event) is not ProductReviewCompletedEvent
                or not getattr(event, '_trusted', False)
                or consumer_name not in PRODUCT_REVIEW_EVENT_CONSUMERS):
            raise ProjectionTransportRejected('EVENT_INTEGRITY_FAILURE')
        payload = event.to_dict()
        request_id = str(uuid4())
        request = {
            'version': 1,
            'request_id': request_id,
            'consumer_name': consumer_name,
            'event_id': payload['event_id'],
            'event_digest': payload['event_digest'],
            'event_type': payload['event_type'],
            'event_version': payload['event_version'],
            'proposal_projection': proposal_projection,
            'event': payload,
        }
        sock = None
        try:
            validate_projection_socket(
                self.config.socket_path,
                owner_uid=self.config.django_uid,
                group_gid=self.config.agent_control_gid,
                mode=self.config.socket_mode,
            )
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
            sock.settimeout(self.config.timeout_ms / 1000)
            sock.connect(self.config.socket_path)
        except (AuthorityError, OSError, socket.timeout, TimeoutError):
            if sock is not None:
                sock.close()
            raise ProjectionTransportUnavailable() from None
        try:
            projection_peer(
                sock, uid=self.config.django_uid, gid=self.config.django_gid,
                process_reader=self.process_reader,
            )
            try:
                raw = packet(request, limit=self.config.max_message_bytes)
            except ValidationError:
                raise ProjectionTransportRejected('EVENT_TOO_LARGE') from None
            sock.sendall(raw)
            response = self._receive(sock)
            projection_peer(
                sock, uid=self.config.django_uid, gid=self.config.django_gid,
                process_reader=self.process_reader,
            )
        except ProjectionTransportRejected:
            raise
        except ProjectionTransportUnavailable:
            raise
        except (AuthorityError, OSError, socket.timeout, TimeoutError, ValidationError):
            raise ProjectionTransportUnavailable() from None
        finally:
            sock.close()
        if (type(response) is not dict or set(response) != {
                'version', 'request_id', 'status', 'reason'}
                or response['version'] != 1 or response['request_id'] != request_id
                or response['status'] not in {'ACKNOWLEDGED', 'RETRY', 'REJECTED'}
                or (response['reason'] is not None
                    and (type(response['reason']) is not str
                         or not _PROJECTION_REASON.fullmatch(response['reason'])))):
            raise ProjectionTransportRejected('TRANSPORT_RESPONSE_INVALID')
        if response['status'] == 'ACKNOWLEDGED' and response['reason'] is not None:
            raise ProjectionTransportRejected('TRANSPORT_RESPONSE_INVALID')
        if response['status'] == 'RETRY':
            raise ProjectionTransportFailure(response['reason'] or 'CONSUMER_RUNTIME_FAILURE')
        if response['status'] == 'REJECTED':
            raise ProjectionTransportRejected(response['reason'] or 'TRANSPORT_RESPONSE_INVALID')
        return {'status': 'ACKNOWLEDGED', 'event_id': payload['event_id']}


def transport_peer(sock):
    if isinstance(sock, SenderSocket):
        if sock.sender is None:
            raise AuthorityError('Kernel sender evidence required.')
        return sock.sender
    return PeerIdentity.from_socket(sock)


class UnixTransport:
    """ServiceLoop adapter: one enrolled connection and one bounded output slot.

    Handshake selects installed enrollment; kernel credentials establish identity.
    No SCM_RIGHTS receive/send or descriptor forwarding is supported.
    """
    def __init__(self, listener, enrollment, *, now=time.monotonic, process_reader=ProcessIdentity.read, peer_reader=transport_peer):
        self.listener = local_socket(listener)
        self.listener.setblocking(False)
        self.auth = PeerAuthenticator(enrollment)
        self.enrollment, self.now, self.process_reader = enrollment, now, process_reader
        self.peer_reader = peer_reader
        self.conn = None
        self.handshake = None
        self.reader = None
        self.outgoing = b''
        self.closed = False

    @classmethod
    def bind_installed(cls, path, enrollment):
        if path not in PATHS:
            raise AuthorityError('Unknown installed Unix endpoint.')
        parent = Path(path).parent
        for node in (parent, *parent.parents):
            info = node.lstat()
            if node.is_symlink() or info.st_mode & 0o022:
                raise AuthorityError('Writable Unix endpoint ancestor.')
        if os.path.lexists(path):
            raise AuthorityError('Existing endpoint requires receipt-based reconciliation.')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        try:
            sock.bind(path)
            os.chmod(path, 0o600)
            sock.listen(1)
            return cls(sock, enrollment)
        except BaseException:
            sock.close()
            raise

    def ready(self):
        return not self.closed and self.listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 1

    def identity(self):
        if hasattr(self, 'operational_session'):
            self.operational_session.verify()
        if self.conn is None or self.handshake is None:
            raise AuthorityError('No enrolled Unix peer.')
        peer = self.peer_reader(self.conn)
        return peer, self.process_reader(peer.pid), dict(self.handshake)

    def accept(self):
        if self.closed: raise AuthorityError('Closed transport.')
        if self.handshake is not None:
            if getattr(self, 'enrollment_pending', False):
                self.enrollment_pending = False
                return self.identity()
            return None
        if self.conn is None:
            try: self.conn, _ = self.listener.accept()
            except BlockingIOError: return None
            local_socket(self.conn).setblocking(False)
            self.reader = Packet(self.now())
        if self.now() >= self.reader.deadline:
            raise AuthorityError('Handshake timeout.')
        try: raw = self.conn.recv(self.reader.wanted)
        except BlockingIOError: return None
        frame = self.reader.feed(raw, self.now())
        if frame is None: return None
        self.handshake = bounded_json(frame[4:])
        observed = self.identity()
        self.auth.verify(*observed, consume=True)
        self.reader = None
        self.outgoing = packet({'accepted': True})
        return observed

    def poll(self, limit):
        if type(limit) is not int or not 1 <= limit <= 4:
            raise ValidationError('Bounded event poll required.')
        if self.closed or self.handshake is None:
            raise AuthorityError('No active Unix connection.')
        self.auth.verify(*self.identity())
        if self.outgoing:
            try: sent = self.conn.send(self.outgoing)
            except BlockingIOError: sent = 0
            self.outgoing = self.outgoing[sent:]
        if self.reader is not None and self.now() >= self.reader.deadline:
            raise AuthorityError('Partial Unix frame timed out.')
        if self.reader is None:
            # Do not arm an idle-connection frame timeout until bytes arrive.
            try: first = self.conn.recv(4, socket.MSG_PEEK)
            except BlockingIOError: return []
            except ConnectionResetError: return [('disconnect', b'')]
            if not first: return [('disconnect', b'')]
            self.reader = Packet(self.now())
        try: chunk = self.conn.recv(self.reader.wanted)
        except BlockingIOError: return []
        except ConnectionResetError: return [('disconnect', b'')]
        if not chunk: return [('disconnect', b'')]
        if self.reader is None: self.reader = Packet(self.now())
        raw = self.reader.feed(chunk, self.now())
        if raw is None: return []
        self.reader = None
        if limit < 2: raise ValidationError('Frame requires two bounded events.')
        return [('data', raw), ('end', b'')]

    def send(self, raw):
        if type(raw) is not bytes or len(raw) > LIMIT + 4 or len(self.outgoing)+len(raw)>2*(LIMIT+4):
            raise AuthorityError('Unix output backpressure/size limit.')
        if Packet(self.now()).feed(raw, self.now()) is None:
            raise ValidationError('Incomplete outgoing frame.')
        self.outgoing += raw

    def close(self):
        if not self.closed:
            self.closed = True
            if hasattr(self, 'operational_session'):
                self.operational_session.disconnect()
            if self.conn is not None: self.conn.close()
            self.listener.close()


class UnixRPCClient:
    """Bounded authenticated RPC. A lost response closes the channel; no retry."""
    def __init__(self, sock, enrollment, handshake, *, process_reader=ProcessIdentity.read,
                 now=time.monotonic, peer_reader=transport_peer):
        self.peer_reader=peer_reader
        self.sock=local_socket(sock)
        self.enrollment,self.handshake,self.process_reader,self.now=enrollment,dict(handshake),process_reader,now
        self.auth=PeerAuthenticator(enrollment)
        self.closed=False
        self.sock.settimeout(1)
        self.verify()
        self.sock.sendall(packet(handshake))
        if self.receive() != {'accepted':True}:
            self.close()
            raise AuthorityError('Unix enrollment not acknowledged.')

    @classmethod
    def connect_installed(cls, path, enrollment, handshake):
        if path != '/run/bonup-agent-supervisor/control.sock':
            raise AuthorityError('Fixed supervisor endpoint required.')
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM|socket.SOCK_CLOEXEC)
        try:
            sock.settimeout(1);sock.connect(path)
            return cls(sock,enrollment,handshake)
        except BaseException:
            sock.close()
            raise

    def verify(self):
        if hasattr(self, 'operational_session'):
            self.operational_session.verify()
        peer=self.peer_reader(self.sock)
        e=self.enrollment
        self.auth.verify(peer,self.process_reader(peer.pid),
            dict(endpoint=e.endpoint,generation=e.generation,enrollment_id=e.enrollment_id))

    def receive(self):
        reader=Packet(self.now())
        while True:
            left=reader.deadline-self.now()
            if left<=0: raise AuthorityError('Unix response timeout.')
            self.sock.settimeout(left)
            complete=reader.feed(self.sock.recv(reader.wanted),self.now())
            if complete is not None:return bounded_json(complete[4:])

    def exchange(self, request):
        from .composition_protocol import frame,validate
        if self.closed:raise AuthorityError('No reconnect/release replay.')
        try:
            self.verify()
            self.sock.settimeout(1);self.sock.sendall(frame(request))
            response=validate(self.receive())
            self.verify()
            if any(response[k]!=request[k] for k in ('request_id','launch_id','generation','boot_id','version')):
                raise AuthorityError('Uncorrelated Unix response.')
            return response
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self.closed:
            self.closed=True
            if hasattr(self, 'operational_session'):
                self.operational_session.disconnect()
            self.sock.close()


class SystemdNotifier:
    """Only this explicit adapter reads NOTIFY_SOCKET; it never grants authority."""
    def __init__(self, path):
        if type(path) is not str or not path or '\0' in path or len(path.encode()) > 107:
            raise ValidationError('Invalid systemd notification endpoint.')
        if path.startswith('@'):
            if not path.startswith('@systemd/notify'):
                raise ValidationError('Unapproved abstract notification endpoint.')
            self.address = '\0' + path[1:]
        elif path.startswith('/run/systemd/notify') and '..' not in Path(path).parts:
            self.address = path
        else:
            raise ValidationError('Notification endpoint outside systemd runtime.')

    @classmethod
    def installed(cls):
        return cls(os.environ.get('NOTIFY_SOCKET'))

    def __call__(self, value):
        if value not in ('READY=1', 'WATCHDOG=1', 'STOPPING=1'):
            raise ValidationError('Unknown notification.')
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC) as sock:
            sock.settimeout(.1)
            sock.connect(self.address)
            if sock.send(value.encode()) != len(value):
                raise AuthorityError('Incomplete systemd notification.')


class DuplexClient:
    """One kernel-authenticated connection, independent bounded heartbeat lane.

    At most one operation and one heartbeat can be outstanding. Responses are
    correlated before delivery. Loss closes admission; releases are never retried.
    SQLite remains on the caller's controller thread. No executor runs model code.
    """
    def __init__(self, rpc, generation, boot_id):
        import threading
        self.rpc, self.generation, self.boot_id = rpc, generation, boot_id
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.pending = {}
        self.stopped = threading.Event()
        self.failure = None
        self.maintenance = None
        self.last_heartbeat = rpc.now()
        self.heartbeat_evidence = None
        self.reader = threading.Thread(target=self._read, name='agent-response', daemon=True)
        self.timer = threading.Thread(target=self._heartbeats, name='agent-heartbeat', daemon=True)
        self.reader.start()
        self.timer.start()

    def _fail(self, error):
        self.failure = error
        self.stopped.set()
        self.rpc.close()
        with self.lock:
            for item in self.pending.values(): item[1].set()

    def _read(self):
        from .composition_protocol import validate
        try:
            while not self.stopped.is_set():
                response = validate(self.rpc.receive())
                self.rpc.verify()
                with self.lock:
                    item = self.pending.get(response['request_id'])
                    if item is None or item[2] is not None:
                        raise AuthorityError('Unsolicited/replayed supervisor response.')
                    if any(response[k] != item[0][k] for k in ('version','launch_id','generation','boot_id')):
                        raise AuthorityError('Wrong supervisor response context.')
                    item[2] = response
                    item[1].set()
        except BaseException as error:
            self._fail(error)

    def exchange(self, request):
        import threading
        from .composition_protocol import frame
        raw = frame(request)
        heartbeat = request['action'] == 'HEARTBEAT'
        event = threading.Event()
        with self.lock:
            if self.stopped.is_set() or request['request_id'] in self.pending or any(
                    (v[0]['action']=='HEARTBEAT') == heartbeat for v in self.pending.values()):
                raise AuthorityError('Disconnected, replayed or concurrent RPC.')
            self.pending[request['request_id']] = [request, event, None]
        try:
            with self.write_lock:
                self.rpc.sock.sendall(raw)
            deadline=time.monotonic()+1
            while not event.wait(.01):
                if time.monotonic()>=deadline:
                    raise AuthorityError('Supervisor response deadline.')
                if not heartbeat and self.maintenance is not None:
                    self.maintenance()
            with self.lock:
                response = self.pending[request['request_id']][2]
            if response is None or self.stopped.is_set():
                raise AuthorityError('Supervisor connection lost.')
            return response
        except BaseException as error:
            self._fail(error)
            raise
        finally:
            with self.lock: self.pending.pop(request['request_id'], None)

    def _heartbeats(self):
        from .composition import message
        from uuid import uuid4
        try:
            while not self.stopped.wait(.25):
                result = self.exchange(message('HEARTBEAT', str(uuid4()), self.generation,
                    self.boot_id, dict(ready=True)))
                if result['action'] != 'HEARTBEAT' or result['data']['ready'] is not True:
                    raise AuthorityError('Supervisor heartbeat declined.')
                self.last_heartbeat = self.rpc.now()
                self.heartbeat_evidence = result
        except BaseException as error:
            self._fail(error)

    def check(self):
        if self.stopped.is_set() or self.rpc.now()-self.last_heartbeat >= 2:
            raise AuthorityError('Supervisor liveness lost.') from self.failure

    def close(self):
        self._fail(AuthorityError('Controller shutdown.'))
        import threading
        for thread in (self.reader, self.timer):
            if thread is not threading.current_thread(): thread.join(1.1)


class OperationalChannel:
    """Bounded first-start handshake on one kernel-authenticated AF_UNIX channel.

    No registry or launch operation runs here. Failure closes the channel. The
    caller subsequently transfers this same socket to the normal strict protocol.
    """
    def __init__(self, sock, local, remote, *, local_observe, observe, now):
        from .operational_enrollment import Enrollment
        self.sock = local_socket(sock)
        self.closed = False
        self.session = Enrollment(local, remote, local_observe=local_observe,
            observe=observe, now=now)
        self.now = now

    def _remaining(self):
        remaining = self.session.deadline - self.now()
        if remaining <= 0:
            raise AuthorityError('Enrollment deadline expired.')
        return remaining

    def send(self, value):
        self.session._guard()
        self.sock.settimeout(self._remaining())
        self.sock.sendall(packet(value))

    def receive(self):
        reader = Packet(self.now())
        reader.deadline = self.session.deadline
        while True:
            self.session._guard()
            self.sock.settimeout(self._remaining())
            raw = reader.feed(self.sock.recv(reader.wanted), self.now())
            if raw is not None:
                return self.session.receive(raw[4:])

    def enroll(self):
        try:
            if self.session.local.component == 'controller':
                self.send(self.session.begin())
                self.send(self.receive())
                if self.receive() is not None:
                    raise AuthorityError('Unexpected enrollment response.')
            else:
                self.send(self.receive())
                self.send(self.receive())
            self.session.verify()
            self.sock.setblocking(False)
            return self.session
        except BaseException:
            self.close()
            raise

    def close(self):
        self.closed = True
        self.session.disconnect()
        self.sock.close()


def enrolled_rpc(channel, *, process_reader, peer_reader=transport_peer):
    """Adopt exactly the freshly enrolled socket, without reconnect/handshake replay."""
    session = channel.session
    e = session.peer_enrollment()
    rpc = object.__new__(UnixRPCClient)
    rpc.sock, rpc.enrollment = channel.sock, e
    rpc.handshake = dict(endpoint=session.local.component, generation=session.generation,
                         enrollment_id=session.nonce)
    rpc.process_reader, rpc.peer_reader, rpc.now = process_reader, peer_reader, channel.now
    rpc.auth, rpc.closed = PeerAuthenticator(e), False
    rpc.sock.settimeout(1)
    rpc.operational_session = session
    rpc.verify()
    return rpc


def enrolled_transport(channel, listener, *, process_reader, peer_reader=transport_peer):
    session = channel.session
    e = session.peer_enrollment()
    transport = UnixTransport(listener, e, now=channel.now,
                              process_reader=process_reader, peer_reader=peer_reader)
    transport.conn = channel.sock
    transport.conn.setblocking(False)
    transport.handshake = dict(endpoint=e.endpoint, generation=e.generation, enrollment_id=e.enrollment_id)
    # ServiceLoop still consumes its own observation once; no second wire handshake.
    transport.auth.verify(*transport.identity(), consume=True)
    transport.operational_session = session
    transport.enrollment_pending = True
    return transport
