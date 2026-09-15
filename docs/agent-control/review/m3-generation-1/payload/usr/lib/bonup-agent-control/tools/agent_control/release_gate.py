"""One-shot post-confinement release gate. Never accepts payload parameters on wire.

The trusted bootstrap supplies ExpectedRelease and FixedPayload over its installed
configuration path. The inherited socket is dedicated to this one launch; the
sender MUST shutdown its write half after one frame. EOF before a complete frame
is denial; EOF after exactly one frame proves there is no extra queued message.
"""
from dataclasses import dataclass
import os
import socket
import struct
import time

from .identity import PeerIdentity
from .protocol import bounded_json, uuid_value
from .schema import timestamp, valid_format
from .serialization import canonical_json
from .types import AuthorityError, ValidationError

MAX_RELEASE = 2048


@dataclass(frozen=True)
class ExpectedRelease:
    launch_id: str
    supervisor_generation: str
    authorization_digest: str
    nonce: str
    expires_at: str
    peer: PeerIdentity
    elapsed_deadline_ns: int
    channel_identity: tuple | None = None

    def __post_init__(self):
        for value in (self.launch_id,self.supervisor_generation,self.nonce):
            uuid_value(value)
        if not valid_format('sha256',self.authorization_digest) or type(self.peer) is not PeerIdentity:
            raise ValidationError('Invalid release binding.')
        timestamp(self.expires_at)
        if type(self.elapsed_deadline_ns) is not int or self.elapsed_deadline_ns<=0:
            raise ValidationError('Absolute boot-time deadline required.')
        if self.channel_identity is not None and (type(self.channel_identity) is not tuple or
                len(self.channel_identity)!=2 or any(type(v) is not int or v<0 for v in self.channel_identity)):
            raise ValidationError('Invalid inherited channel identity.')

    def message(self):
        return dict(version=1, launch_id=self.launch_id, supervisor_generation=self.supervisor_generation,
                    authorization_digest=self.authorization_digest, nonce=self.nonce, expires_at=self.expires_at, elapsed_deadline_ns=self.elapsed_deadline_ns)


@dataclass(frozen=True)
class FixedPayload:
    argv: tuple
    environment: tuple
    cwd: str = '/work'

    def __post_init__(self):
        from .confinement import ConfinementProfile
        if type(self.argv) is not tuple or not self.argv or any(type(x) is not str or not x or '\0' in x for x in self.argv):
            raise ValidationError('Fixed argv required.')
        if not self.argv[0].startswith('/usr/bin/') or '/' in self.argv[0][len('/usr/bin/'):]:
            raise ValidationError('Invalid fixed executable.')
        if self.environment != ConfinementProfile().environment() or self.cwd != '/work':
            raise ValidationError('Invalid worker environment/cwd.')


def release_frame(expected):
    raw = canonical_json(expected.message()).encode('utf-8')
    return struct.pack('!I',len(raw)) + raw


def receive_one(sock, *, limit=MAX_RELEASE, timeout=5, monotonic=time.monotonic):
    """Read exactly one framed JSON record AND end-of-write, within a total deadline."""
    if type(timeout) not in (float,int) or not 0 < timeout <= 30:
        raise ValidationError('Invalid IPC timeout.')
    deadline = monotonic() + timeout
    old = sock.gettimeout()
    def read(count):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise AuthorityError('IPC timeout.')
        sock.settimeout(remaining)
        return sock.recv(count)
    def exact(count):
        data = bytearray()
        while len(data)<count:
            chunk = read(count-len(data))
            if not chunk:
                raise AuthorityError('Incomplete release/EOF.')
            data.extend(chunk)
        return bytes(data)
    try:
        size = struct.unpack('!I',exact(4))[0]
        if not 1 <= size <= limit:
            raise ValidationError('IPC size limit.')
        data = bounded_json(exact(size))
        if read(1):
            raise AuthorityError('Extra release message.')
        return data
    except (OSError,TimeoutError):
        raise AuthorityError('Release transport failed.') from None
    finally:
        sock.settimeout(old)


class ReleaseGate:
    def __init__(self, expected, payload):
        if type(expected) is not ExpectedRelease or type(payload) is not FixedPayload:
            raise ValidationError('Trusted gate configuration required.')
        self.expected, self.payload, self.used = expected, payload, False

    def authorize(self, sock, *, now, monotonic=time.monotonic, timeout=5,
                  elapsed_ns=lambda:time.clock_gettime_ns(time.CLOCK_BOOTTIME)):
        if self.used:
            raise AuthorityError('Release already consumed.')
        self.used = True  # Failures consume this gate too.
        try:
            if self.expected.channel_identity is None:
                if PeerIdentity.from_socket(sock) != self.expected.peer:
                    raise AuthorityError('Release channel peer mismatch.')
            else:
                # SO_PEERCRED is translated across user/PID namespaces. The trusted
                # bootstrap authenticates it BEFORE unshare and seals the identity
                # of this exclusively inherited endpoint into the gate configuration.
                info = os.fstat(sock.fileno())
                if ((info.st_dev,info.st_ino)!=self.expected.channel_identity or
                        sock.family!=socket.AF_UNIX or sock.type!=socket.SOCK_STREAM):
                    raise AuthorityError('Inherited release channel substituted.')
            data = receive_one(sock,timeout=timeout,monotonic=monotonic)
            if type(data) is not dict or data != self.expected.message() or type(data.get('version')) is not int:
                raise AuthorityError('Release binding mismatch.')
            if now() >= timestamp(self.expected.expires_at) or elapsed_ns() >= self.expected.elapsed_deadline_ns:
                raise AuthorityError('Release expired.')
            return self.payload
        finally:
            sock.close()

    def execute(self, sock, *, now, monotonic=time.monotonic,
                elapsed_ns=lambda:time.clock_gettime_ns(time.CLOCK_BOOTTIME)):
        """Called only by an installed trusted bootstrap INSIDE verified confinement.

        This is a real exec primitive, not the synthetic supervisor. Tests call it
        only in disposable child processes. There is no CLI accepting payload JSON.
        """
        from .supervisor_linux import close_worker_fds, verify_worker_fds
        payload = self.authorize(sock,now=now,monotonic=monotonic,elapsed_ns=elapsed_ns)
        close_worker_fds()
        verify_worker_fds()
        os.chdir(payload.cwd)
        if now() >= timestamp(self.expected.expires_at) or elapsed_ns() >= self.expected.elapsed_deadline_ns:
            raise AuthorityError('Release expired before exec.')
        os.execve(payload.argv[0],payload.argv,dict(payload.environment))
