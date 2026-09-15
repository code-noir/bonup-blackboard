"""Actual sender credentials, independent of an inherited listener's creator."""
import os
import socket
import struct
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tools.agent_control.identity import PeerIdentity,ProcessIdentity
from tools.agent_control.installed_runtime import KernelIO
from tools.agent_control.installed_transport import SenderSocket
from tools.agent_control.types import AuthorityError


class SenderCredentialsTests(unittest.TestCase):
    def test_listener_creator_outside_service_cannot_enroll(self):
        io=KernelIO()
        observed=ProcessIdentity('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',1,10)
        with patch.object(io,'process',return_value=observed),patch('pathlib.Path.read_text',return_value='0::/init.scope\n'):
            with self.assertRaises(AuthorityError):
                io.observe_service(PeerIdentity(0,0,1),SimpleNamespace(service='bonup-agent-supervisor.service'))

    def test_actual_service_process_start_is_rechecked(self):
        io=KernelIO()
        current=ProcessIdentity('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',123,10)
        reused=ProcessIdentity(current.boot_id,123,11)
        with patch.object(io,'process',side_effect=[current,reused]),patch('pathlib.Path.read_text',
                return_value='0::/system.slice/bonup-agent-supervisor.service\n'):
            with self.assertRaises(AuthorityError):
                io.observe_service(PeerIdentity(0,0,123),SimpleNamespace(service='bonup-agent-supervisor.service'))

    def test_actual_service_process_observed(self):
        io=KernelIO()
        current=ProcessIdentity('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',123,10)
        with patch.object(io,'process',return_value=current),patch('pathlib.Path.read_text',
                return_value='0::/system.slice/bonup-agent-supervisor.service\n'):
            observed=io.observe_service(PeerIdentity(0,0,123),SimpleNamespace(service='bonup-agent-supervisor.service'))
            self.assertEqual(observed.process,current)

    def test_inherited_listener_authenticates_accepting_child(self):
        with tempfile.TemporaryDirectory() as directory:
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.addCleanup(listener.close)
            path = directory + '/socket'
            listener.bind(path)
            listener.listen(1)
            child = os.fork()
            if child == 0:
                try:
                    conn, _ = listener.accept()
                    conn = SenderSocket(conn, os.getuid(), os.getgid()).authenticate_sender()
                    conn.sendall(b'proof')
                    conn.close()
                    os._exit(0)
                except BaseException:
                    os._exit(1)
            try:
                conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.addCleanup(conn.close)
                conn.connect(path)
                self.assertEqual(PeerIdentity.from_socket(conn).pid, os.getpid())
                actual = SenderSocket(conn, os.getuid(), os.getgid()).authenticate_sender()
                self.assertEqual(KernelIO.peer(actual).pid, child)
                self.assertEqual(actual.recv(5), b'proof')
            finally:
                _, status = os.waitpid(child, 0)
            self.assertEqual(status, 0)

    def test_wrong_uid_rejected(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        receiver = SenderSocket(b, os.getuid() + 1, os.getgid())
        a.sendall(b'x')
        with self.assertRaises(AuthorityError): receiver.recv(1)

    def test_sender_change_rejected_even_with_same_uid(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        receiver = SenderSocket(b, os.getuid(), os.getgid())
        receiver.sender = PeerIdentity(os.getuid(), os.getgid(), os.getpid() + 1)
        a.sendall(b'x')
        with self.assertRaises(AuthorityError): receiver.recv(1)

    def test_missing_credentials_rejected(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        receiver = SenderSocket(b, os.getuid(), os.getgid())
        b.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 0)
        a.sendall(b'x')
        with self.assertRaises(AuthorityError): receiver.recv(1)

    def test_json_identity_never_overrides_sender(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        receiver = SenderSocket(b, os.getuid(), os.getgid())
        a.sendall(b'{"pid":1,"uid":0}')
        receiver.recv(128)
        self.assertEqual(receiver.sender, PeerIdentity.current())

    def test_forwarded_descriptor_rejected_and_closed(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        receiver = SenderSocket(b, os.getuid(), os.getgid())
        fd = os.open('/dev/null', os.O_RDONLY)
        try:
            before = set(os.listdir('/proc/self/fd'))
            a.sendmsg([b'x'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack('i', fd))])
            with self.assertRaises(AuthorityError): receiver.recv(1)
            self.assertEqual(set(os.listdir('/proc/self/fd')), before)
        finally:
            os.close(fd)
