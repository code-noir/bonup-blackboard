"""Disposable unprivileged children; no worker identities, bwrap or host cgroups."""
from datetime import datetime,timezone,timedelta
import os
import signal
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from uuid import uuid4

from tools.agent_control.exec_start import execute_observed,status_message,ExecStart
from tools.agent_control.identity import PeerIdentity
from tools.agent_control.release_gate import ExpectedRelease,receive_one
from tools.agent_control.types import AuthorityError


class ExecStartTests(unittest.TestCase):
    def expected(self):
        return ExpectedRelease(str(uuid4()),str(uuid4()),'a'*64,str(uuid4()),
            (datetime.now(timezone.utc)+timedelta(seconds=10)).isoformat().replace('+00:00','Z'),
            PeerIdentity.current(),time.clock_gettime_ns(time.CLOCK_BOOTTIME)+10_000_000_000)

    def run_gate(self,mode):
        expected=self.expected()
        parent,gate=socket.socketpair()
        with tempfile.TemporaryDirectory() as directory:
            pid=os.fork()
            if pid==0:
                parent.close()
                try:
                    if mode=='death':os.kill(os.getpid(),signal.SIGKILL)
                    if mode=='rejected':raise AuthorityError('Synthetic gate denial.')
                    payload=SimpleNamespace(argv=('/usr/bin/missing-synthetic-exec' if mode=='exec_failure' else '/usr/bin/true',),
                        environment=(),cwd=directory)
                    def before_exec():
                        if mode=='expired':raise AuthorityError('Synthetic expired authority.')
                    code=execute_observed(payload,expected,gate,before_exec=before_exec)
                    os._exit(code if code>=0 else 125)
                except BaseException:os._exit(125)
            gate.close()
            try:
                if mode=='lost_ack':
                    parent.close()
                elif mode=='success':
                    self.assertEqual(receive_one(parent,timeout=2),status_message(expected,'EXEC_START_CONFIRMED'))
                elif mode in ('expired','exec_failure'):
                    self.assertEqual(receive_one(parent,timeout=2),status_message(expected,'EXEC_FAILED'))
                else:
                    with self.assertRaises(AuthorityError):receive_one(parent,timeout=2)
            finally:
                parent.close()
                _,status=os.waitpid(pid,0)
            if mode=='success':self.assertEqual(status,0)
            if mode=='lost_ack':self.assertNotEqual(status,0)

    def test_successful_kernel_exec_event(self):self.run_gate('success')
    def test_gate_death_is_not_exec(self):self.run_gate('death')
    def test_gate_rejection_is_not_exec(self):self.run_gate('rejected')
    def test_exec_failure_is_not_exec(self):self.run_gate('exec_failure')
    def test_expiry_before_exec_is_not_exec(self):self.run_gate('expired')
    def test_lost_acknowledgement_kills_traced_child(self):self.run_gate('lost_ack')

    def test_linux_backend_requires_bound_status_not_delivery(self):
        from threading import RLock
        from unittest.mock import patch
        from tools.agent_control.exec_start import send_status
        from tools.agent_control.supervisor_linux import LinuxProcessBackend
        for outcome in ('EXEC_START_CONFIRMED','RELEASE_REJECTED','EXEC_FAILED','GATE_FAILED'):
            with self.subTest(outcome=outcome):
                expected=self.expected()
                a,b=socket.socketpair()
                send_status(a,expected,outcome)
                backend=object.__new__(LinuxProcessBackend)
                backend.release_lock=RLock()
                backend.children={expected.launch_id:dict(expected=expected,status_socket=b,stopped=False)}
                launch=dict(launch_id=expected.launch_id,supervisor_generation=expected.supervisor_generation)
                record=SimpleNamespace(authorization_digest=expected.authorization_digest)
                with patch.object(backend,'_release',return_value=None):
                    if outcome=='EXEC_START_CONFIRMED':
                        backend.release(launch,record).verify(launch,record)
                    else:
                        with self.assertRaises(AuthorityError):backend.release(launch,record)
                self.assertEqual(b.fileno(),-1)

    def test_exact_execution_start_binding(self):
        expected=self.expected()
        proof=ExecStart(expected.launch_id,expected.supervisor_generation,expected.authorization_digest)
        launch=dict(launch_id=expected.launch_id,supervisor_generation=expected.supervisor_generation)
        record=SimpleNamespace(authorization_digest=expected.authorization_digest)
        proof.verify(launch,record)
        launch['launch_id']=str(uuid4())
        with self.assertRaises(AuthorityError):proof.verify(launch,record)
