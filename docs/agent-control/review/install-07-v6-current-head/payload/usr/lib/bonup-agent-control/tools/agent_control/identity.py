"""Kernel identity primitives; no enrollment daemon, environment identity or UID switching."""
from dataclasses import dataclass
import os
from pathlib import Path
import socket
import struct

from .authority import AuthenticatedContext, actor_role
from .types import AuthorityError, Role


@dataclass(frozen=True)
class PeerIdentity:
    uid: int
    gid: int
    pid: int

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in (self.uid, self.gid)) or type(self.pid) is not int or self.pid <= 0:
            raise AuthorityError('Invalid kernel identity.')

    @classmethod
    def from_socket(cls, sock):
        pid, uid, gid = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
        return cls(uid, gid, pid)

    @classmethod
    def current(cls):
        return cls(os.geteuid(), os.getegid(), os.getpid())


@dataclass(frozen=True)
class ProcessIdentity:
    boot_id: str
    pid: int
    start_ticks: int

    @classmethod
    def read(cls, pid):
        if type(pid) is not int or pid <= 0:
            raise AuthorityError('Invalid process ID.')
        try:
            # comm can contain spaces and closing parentheses; fields after the last ) are stable.
            stat = Path(f'/proc/{pid}/stat').read_text()
            ticks = int(stat[stat.rfind(')') + 2:].split()[19])
            return cls(Path('/proc/sys/kernel/random/boot_id').read_text().strip(), pid, ticks)
        except (OSError, ValueError, IndexError):
            raise AuthorityError('Process identity unavailable.') from None

    def verify(self, reader=None):
        if (reader or self.read)(self.pid) != self:
            raise AuthorityError('Stale process identity.')


@dataclass(frozen=True)
class WorkerIdentity:
    agent_id: str
    role: Role
    username: str
    uid: int
    gid: int

    def __post_init__(self):
        if type(self.role) is not Role or self.role == Role.FOUNDER or actor_role(self.agent_id) != self.role:
            raise AuthorityError('Worker role mismatch.')
        if any(type(v) is not int or v <= 0 for v in (self.uid, self.gid)):
            raise AuthorityError('Privileged worker identity rejected.')
        if type(self.username) is not str or not self.username or '/' in self.username:
            raise AuthorityError('Invalid worker username.')

    def matches(self, peer):
        return type(peer) is PeerIdentity and (peer.uid, peer.gid) == (self.uid, self.gid)


def validate_identity_map(workers, founder_uid):
    if type(founder_uid) is not int or founder_uid <= 0:
        raise AuthorityError('Invalid founder UID.')
    for field in ('agent_id', 'username', 'uid', 'gid'):
        values = [getattr(w, field) for w in workers]
        if len(values) != len(set(values)):
            raise AuthorityError('Identity mapping collision.')
    if any(w.uid == founder_uid for w in workers):
        raise AuthorityError('Workers cannot share founder UID.')


def founder_context(peer, *, founder_uid, enrolled_process, reader=None):
    """Only for the separately enrolled founder endpoint, never proposal intake.

    Enrollment must be controller-owned. SO_PEERCRED alone cannot distinguish a
    model process sharing the founder UID from an approved human session.
    """
    if type(peer) is not PeerIdentity or type(enrolled_process) is not ProcessIdentity:
        raise AuthorityError('Verified founder enrollment required.')
    if type(founder_uid) is not int or founder_uid <= 0 or peer.uid != founder_uid or peer.uid == 0:
        raise AuthorityError('Founder identity rejected.')
    if peer.pid != enrolled_process.pid:
        raise AuthorityError('Founder process not enrolled.')
    enrolled_process.verify(reader)
    return AuthenticatedContext('FOUNDER', Role.FOUNDER, peer.uid)
