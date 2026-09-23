"""Bounded founder intake on an already verified activated AF_UNIX listener.

Kernel credentials constrain a participant; only the external signature grants
authority. No filesystem listener is created by this module.
"""
import socket

from .identity import PeerIdentity, ProcessIdentity
from .installed_transport import SenderSocket, Packet, local_socket, packet
from .protocol import bounded_json
from .types import AuthorityError


class FounderTransport:
    def __init__(self, listener, intake_factory, *, now, process_reader=ProcessIdentity.read):
        self.listener = local_socket(listener)
        self.listener.setblocking(False)
        self.factory, self.now, self.process_reader = intake_factory, now, process_reader
        self.conn = self.intake = self.reader = self.process = None
        self.outgoing = b''
        self.deadline = 0
        self.dispatching = False

    def observe(self):
        if self.conn is None or self.conn.sender is None:
            raise AuthorityError('Kernel founder sender is not established.')
        peer = self.conn.sender
        process = self.process_reader(peer.pid)
        if (peer.uid, peer.gid) != (1000, 1000) or process != self.process:
            raise AuthorityError('Founder process changed.')
        return peer, process

    def poll(self):
        # Supervisor RPC maintenance may call poll on the same controller
        # thread. A completed frame must not be read or dispatched twice.
        if self.dispatching:
            return
        if self.conn is None:
            try:
                raw, _ = self.listener.accept()
            except BlockingIOError:
                return
            try:
                peer = PeerIdentity.from_socket(raw)
                if (peer.uid, peer.gid) != (1000, 1000):
                    raise AuthorityError('Founder transport UID/GID mismatch.')
                self.process = self.process_reader(peer.pid)
                self.conn = SenderSocket(raw, 1000, 1000)
                self.conn.setblocking(False)
                self.reader = Packet(self.now())
            except BaseException:
                raw.close()
                raise
        try:
            if self.outgoing:
                if self.now() >= self.deadline:
                    raise AuthorityError('Founder response deadline.')
                try:
                    sent = self.conn.send(self.outgoing)
                except BlockingIOError:
                    return
                if sent <= 0:
                    raise AuthorityError('Founder response disconnected.')
                self.outgoing = self.outgoing[sent:]
                if not self.outgoing:
                    self.reader = Packet(self.now(), timeout=60)
                return
            if self.now() >= self.reader.deadline:
                raise AuthorityError('Founder request deadline.')
            try:
                chunk = self.conn.recv(self.reader.wanted)
            except BlockingIOError:
                return
            if not chunk:
                self.disconnect()
                return
            self.observe()
            data = self.reader.feed(chunk, self.now())
            if data is not None:
                if self.intake is None:
                    self.intake = self.factory(self.observe)
                self.dispatching = True
                try:
                    result = self.intake.request(bounded_json(data[4:]))
                finally:
                    self.dispatching = False
                self.outgoing = packet(result)
                self.deadline = self.now() + 1
        except BaseException:
            self.disconnect()
            raise

    def disconnect(self):
        try:
            if self.intake is not None:
                self.intake.close()
        finally:
            if self.conn is not None:
                self.conn.close()
            self.conn = self.intake = self.reader = self.process = None
            self.outgoing = b''

    def close(self):
        try:
            self.disconnect()
        finally:
            self.listener.close()
