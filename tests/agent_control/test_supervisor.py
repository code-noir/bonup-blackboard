"""Disposable registry and Linux-child tests. No installed services or live cgroups."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import socket
import sqlite3
import struct
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fixtures import ARCH, FE, FOUNDER, blank, approval_data, U
from tools.agent_control.confinement import ConfinementProfile, TaskRoot, PinnedMounts
from tools.agent_control.execution import CommandPolicy, LaunchRecord
from tools.agent_control.identity import WorkerIdentity, PeerIdentity, ProcessIdentity
from tools.agent_control.protocol import Operation
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2, check_version, DDL_V2
from tools.agent_control.runtime import RuntimeRegistry, STATES
from tools.agent_control.release_gate import ExpectedRelease, FixedPayload, ReleaseGate, release_frame
from tools.agent_control.serialization import canonical_json
from tools.agent_control.storage import RegistryBlocked
from tools.agent_control.supervisor import (Supervisor, SyntheticProcessBackend, ExecutionDeadline,
    ControllerEnrollment, SupervisorProtocol, supervisor_frame)
from tools.agent_control.supervisor_linux import (close_worker_fds,verify_worker_fds,close_except,
    secure_open,open_fds,CgroupV2,InstalledArtifacts,drop_worker_identity)
from tools.agent_control.types import AuthorityError, ValidationError, Role


def uid():return str(uuid4())
NOW=datetime(2026,9,14,tzinfo=timezone.utc)
EXPIRY='2026-09-15T00:00:00Z'


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'state.sqlite3'
        self.registry=Registry.initialize(self.path,Path(self.temp.name)/'history.git',operation_id=uid())
        self.addCleanup(self.registry.close)

    def test_additive_migration_preserves_all_existing_rows(self):
        db=self.registry.db
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='schema_versions'")]
        before={t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in tables}
        migrate_v2(self.registry)
        self.assertEqual(check_version(db),2)
        for t,rows in before.items():self.assertEqual(rows,[tuple(r) for r in db.execute('SELECT * FROM '+t)])
        self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        with Registry(self.path) as reopened:self.assertNotEqual(reopened.verify()['status'],'BLOCKED')
        self.assertEqual(db.execute('SELECT count(*) FROM execution_runtime').fetchone()[0],0)

    def test_migration_failure_rolls_back(self):
        with patch('tools.agent_control.runtime_schema.DDL_V2',DDL_V2+('INVALID SQL',)):
            with self.assertRaises(sqlite3.DatabaseError):migrate_v2(self.registry)
        self.assertEqual(check_version(self.registry.db),1)

    def test_partial_migration_rejected(self):
        self.registry.db.execute(DDL_V2[0])
        with self.assertRaises(RegistryBlocked):migrate_v2(self.registry)
        with self.assertRaises(RegistryBlocked):Registry(self.path)

    def test_failure_after_schema_creation_rolls_back(self):
        original = check_version
        calls = 0
        def check(db):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RegistryBlocked('Injected post-DDL failure')
            return original(db)
        with patch('tools.agent_control.runtime_schema.check_version',side_effect=check):
            with self.assertRaises(RegistryBlocked):migrate_v2(self.registry)
        self.assertEqual(check_version(self.registry.db),1)

    def test_unsupported_version_and_repeat_rejected(self):
        migrate_v2(self.registry)
        with self.assertRaises(RegistryBlocked):migrate_v2(self.registry)
        self.registry.db.execute('INSERT INTO schema_versions VALUES (3,?)',(EXPIRY,))
        with self.assertRaises(RegistryBlocked):Registry(self.path)

    def test_v2_missing_index_rejected(self):
        migrate_v2(self.registry)
        self.registry.db.execute('DROP INDEX one_live_launch')
        with self.assertRaises(RegistryBlocked):Registry(self.path)

    def test_foreign_keys_enforced(self):
        migrate_v2(self.registry)
        with self.assertRaises(sqlite3.IntegrityError):
            self.registry.db.execute('INSERT INTO execution_runtime VALUES (?,?,?,0,0,1)',(uid(),uid(),'a'*64))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.registry=Registry.initialize(base/'state.sqlite3',base/'history.git',operation_id=uid())
        self.addCleanup(self.registry.close)
        r=self.registry
        p={'title':'Synthetic supervisor','objective':'Validate durable execution','source_base_commit':'a'*40,
           'allowed_write_paths':[{'kind':'FILE','path':'frontend/example.ts'}]}
        t=r.create_task(p,operation_id=uid(),context=ARCH);tid=t['task_id']
        r.assign_metadata(tid,[{'owner_agent':'FE-01','workstream':'frontend',
            'allowed_write_paths':[{'kind':'FILE','path':'frontend/example.ts'}],
            'branch':'agent/ATS-0001/frontend','worktree':'/synthetic/work'}],operation_id=uid(),context=ARCH)
        r.transition(tid,'INSPECTING',operation_id=uid(),context=ARCH)
        t=r.freeze_spec(tid,operation_id=uid(),context=ARCH)
        ad=approval_data(t);ad['approval_id']=uid()
        approval=r.put_metadata('Approval',ad,operation_id=uid(),context=FOUNDER)
        r.transition(tid,'FOUNDER_APPROVED',operation_id=uid(),context=FOUNDER,approval_id=approval['approval_id'])
        r.transition(tid,'ASSIGNED',operation_id=uid(),context=ARCH,approval_id=approval['approval_id'])
        t=r.transition(tid,'IN_PROGRESS',operation_id=uid(),context=FE)
        grant=blank('ExecutionGrant');self.execution_id=uid()
        grant.update(execution_id=self.execution_id,agent_id='FE-01',role=Role.FRONTEND_ENGINEERING.value,
                     task_id=tid,spec_version=t['spec_version'],spec_digest=t['spec_digest'],expires_at=EXPIRY,fencing_epoch=1,
                     process_scope='pid:42000',process_start_identity='123',boot_id=U)
        r.put_metadata('ExecutionGrant',grant,operation_id=uid(),context=ARCH)
        migrate_v2(r)
        self.runtime=RuntimeRegistry(r,founder_uid=1000,now=lambda:NOW)
        self.worker=WorkerIdentity('FE-01',Role.FRONTEND_ENGINEERING,'bonup-fe01',3001,3001)
        self.enrollment=self.runtime.enroll(self.worker,1,'a'*64,context=FOUNDER)
        self.profile=ConfinementProfile()
        self.profile_id=self.runtime.put_profile(self.profile,(CommandPolicy('true',Operation.RUN_TEST,('/usr/bin/true',)),),context=FOUNDER)
        self.runtime.bind_execution(self.execution_id,self.enrollment,self.profile_id,context=FOUNDER)
        self.generation,self.boot=uid(),U
        self.launch_id=self.runtime.register_launch(self.execution_id,uid(),'b'*64,self.generation,self.boot,
            {'workspace':[1,2,3001,3001],'repository':None,'profile_digest':self.profile_id})
        self.now=NOW;self.elapsed=0
        self.record=LaunchRecord(Operation.RUN_TEST,('/usr/bin/true',),'/work',self.profile.environment(),30,65536,
            self.profile.profile_digest,self.worker,'{}','b'*64,EXPIRY)
        self.backend=SyntheticProcessBackend(ProcessIdentity(self.boot,42000,123))
        self.supervisor=Supervisor(self.runtime,self.backend,generation=self.generation,boot_id=self.boot,
            authorize=lambda *_:self.record,now=lambda:self.now,elapsed=lambda:self.elapsed)

    def test_enrollment_collision_and_forgery(self):
        for worker in [replace(self.worker,agent_id='BE-01',role=Role.BACKEND_ENGINEERING),
                       replace(self.worker,agent_id='BE-01',role=Role.BACKEND_ENGINEERING,username='other')]:
            with self.assertRaises(sqlite3.IntegrityError):self.runtime.enroll(worker,1,'a'*64,context=FOUNDER)
        for ctx in (ARCH,{'founder':True},replace(FOUNDER,authenticated_unix_uid=0)):
            with self.assertRaises(AuthorityError):self.runtime.enroll(self.worker,2,'a'*64,context=ctx)
        with self.assertRaises(AuthorityError):self.runtime.enroll(replace(self.worker,uid=1000),2,'a'*64,context=FOUNDER)

    def test_stale_generation_and_active_rebind(self):
        for generation in (1,3):
            with self.assertRaises(AuthorityError):self.runtime.enroll(self.worker,generation,'a'*64,context=FOUNDER)
        with self.assertRaises(AuthorityError):self.runtime.enroll(replace(self.worker,uid=4001,gid=4001,username='new'),2,'a'*64,context=FOUNDER)

    def test_rebind_requires_cleanup_and_new_generation(self):
        self.runtime.revoke(self.execution_id,0,context=FOUNDER)
        self.supervisor.stop(self.launch_id,'REVOKED')
        key=self.runtime.enroll(replace(self.worker,uid=4001,gid=4001,username='new'),2,'a'*64,context=FOUNDER)
        self.assertEqual(self.runtime.enrollment(key).uid,4001)
        with self.assertRaises(AuthorityError):self.runtime.enrollment(self.enrollment)

    def test_immutable_enrollment_and_profile(self):
        for table in ('identity_enrollments','execution_profiles'):
            with self.assertRaises(sqlite3.IntegrityError):self.runtime.db.execute('DELETE FROM '+table)
        self.assertEqual(self.runtime.profile(self.profile_id)[0],self.profile)

    def test_revoke_cas(self):
        self.runtime.revoke(self.execution_id,0,context=FOUNDER)
        self.assertEqual(self.runtime.runtime(self.execution_id)['authority_revision'],1)
        with self.assertRaises(AuthorityError):self.runtime.revoke(self.execution_id,0,context=FOUNDER)

    def test_durable_replay_and_one_live_attempt(self):
        launch=self.runtime.launch(self.launch_id)
        self.supervisor.stop(self.launch_id,'CANCELLED')
        with self.assertRaises(sqlite3.IntegrityError):self.runtime.register_launch(self.execution_id,launch['request_id'],'b'*64,
            self.generation,self.boot,{'workspace':[1,2,3001,3001],'repository':None,'profile_digest':self.profile_id})

    def test_all_state_edges_and_invalid_cas(self):
        for source,targets in STATES.items():
            for target in STATES:
                with self.subTest(source=source,target=target):
                    self.runtime.db.execute('UPDATE launch_attempts SET state=?,revision=0,reason=? WHERE launch_id=?',
                        (source,'CANCELLED' if source=='STOPPING' else None,self.launch_id))
                    kwargs={'reason':'CANCELLED'} if target=='STOPPING' else {'cleanup':True} if target=='TERMINAL' else {}
                    if target in targets:
                        self.assertEqual(self.runtime.transition(self.launch_id,0,target,**kwargs)['state'],target)
                    else:
                        with self.assertRaises(AuthorityError):self.runtime.transition(self.launch_id,0,target,**kwargs)
        with self.assertRaises(AuthorityError):self.runtime.transition(self.launch_id,999,'PREPARING')

    def test_terminal_requires_cleanup(self):
        row=self.runtime.transition(self.launch_id,0,'STOPPING',reason='CANCELLED')
        with self.assertRaises(AuthorityError):self.runtime.transition(self.launch_id,row['revision'],'TERMINAL')

    def test_prepare_release_success(self):
        self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.backend.releases,[])
        self.supervisor.release(self.launch_id)
        self.assertEqual(self.runtime.launch(self.launch_id)['state'],'RUNNING')
        self.assertEqual(self.backend.releases,[self.launch_id])

    def test_setup_failure_no_release(self):
        self.backend.fail_setup=True
        with self.assertRaises(AuthorityError):self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.backend.releases,[])
        self.assertEqual(self.runtime.launch(self.launch_id)['state'],'TERMINAL')

    def test_authority_replaced_during_prepare(self):
        self.backend.before_ready=lambda:setattr(self,'record',replace(self.record,authorization_digest='c'*64))
        with self.assertRaises(AuthorityError):self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.backend.releases,[])

    def test_revocation_between_prepare_release(self):
        self.supervisor.prepare(self.launch_id)
        self.runtime.revoke(self.execution_id,0,context=FOUNDER)
        with self.assertRaises(AuthorityError):self.supervisor.release(self.launch_id)
        self.assertEqual(self.backend.releases,[])

    def test_cancelled_launch_row_cannot_release_with_unchanged_grant(self):
        self.supervisor.prepare(self.launch_id)
        prior=self.runtime.launch(self.launch_id)
        self.runtime.transition(self.launch_id,prior['revision'],'STOPPING',reason='CANCELLED')
        with self.assertRaises(AuthorityError):self.supervisor._validate(prior)
        self.assertEqual(self.backend.releases,[])

    def test_running_timeout_and_cleanup(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.elapsed=31
        row=self.supervisor.poll(self.launch_id)
        self.assertEqual((row['state'],row['reason']),('TERMINAL','TIMEOUT'))

    def test_running_authority_replacement(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.record=replace(self.record,authorization_digest='c'*64)
        self.assertEqual(self.supervisor.poll(self.launch_id)['reason'],'REVOKED')

    def test_kernel_deadline_backend_independent_of_controller_requests(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.backend.service_deadlines(now=self.now,elapsed=31)
        self.assertNotIn(self.launch_id,self.backend.children)

    def test_leases_retained_until_cleanup(self):
        key=uid()
        self.runtime.db.execute('INSERT INTO resource_leases VALUES (?,?,?,?,1,1,0,?,?)',
                               (key,self.execution_id,1,EXPIRY,'{}','a'*64))
        self.supervisor.prepare(self.launch_id)
        self.backend.cleanup_known=False
        self.supervisor.stop(self.launch_id,'REVOKED')
        self.assertEqual(self.runtime.db.execute('SELECT held FROM resource_leases').fetchone()[0],1)
        self.backend.cleanup_known=True
        self.supervisor.stop(self.launch_id,'REVOKED')
        self.assertEqual(self.runtime.db.execute('SELECT held FROM resource_leases').fetchone()[0],0)

    def test_lease_scope_and_expiry_denied(self):
        with self.assertRaises(AuthorityError):self.runtime.acquire_lease(self.execution_id,uid(),1,EXPIRY,NOW)
        with self.assertRaises(AuthorityError):self.runtime.acquire_lease(self.execution_id,uid(),1,EXPIRY,NOW+timedelta(days=1))

    def test_authority_revision_database_guard(self):
        with self.assertRaises(sqlite3.IntegrityError):self.runtime.db.execute('UPDATE execution_runtime SET revoked=1')

    def test_task_mutation_advances_authority_revision(self):
        grant=self.registry.load('ExecutionGrant',self.execution_id)
        self.registry.transition(grant['task_id'],'CONTRACT_CONFLICT',operation_id=uid(),context=FE,reason='Synthetic changed scope')
        self.assertEqual(self.runtime.runtime(self.execution_id)['authority_revision'],1)

    def test_running_revocation(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.runtime.revoke(self.execution_id,0,context=FOUNDER)
        row=self.supervisor.poll(self.launch_id)
        self.assertEqual(row['reason'],'REVOKED')

    def test_cancellation_waits_for_descendants(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.backend.cleanup_known=False
        row=self.supervisor.poll(self.launch_id,cancelled=True)
        self.assertEqual(row['state'],'STOPPING')
        with self.assertRaises(AuthorityError):self.runtime.register_launch(self.execution_id,uid(),'b'*64,self.generation,self.boot,
            {'workspace':[1,2,3001,3001],'repository':None,'profile_digest':self.profile_id})
        self.backend.cleanup_known=True
        self.assertEqual(self.supervisor.poll(self.launch_id)['state'],'TERMINAL')

    def test_lost_ack_never_replayed(self):
        self.supervisor.prepare(self.launch_id)
        self.backend.acknowledge=False
        with self.assertRaises(AuthorityError):self.supervisor.release(self.launch_id)
        self.supervisor.reconcile()
        self.assertEqual(len(self.backend.releases),1)

    def test_controller_disappears(self):
        self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.supervisor.poll(self.launch_id,controller_alive=False)['reason'],'INTERRUPTED')

    def test_recovery_all_uncertain_states(self):
        for state in ('REGISTERED','PREPARING','PREPARED','RELEASE_PENDING','RUNNING','STOPPING'):
            with self.subTest(state=state):
                self.runtime.db.execute('UPDATE launch_attempts SET state=?,revision=0,reason=? WHERE launch_id=?',
                    (state,'INTERRUPTED' if state=='STOPPING' else None,self.launch_id))
                self.supervisor.generation=uid();self.supervisor.boot_id=uid()
                self.supervisor.reconcile()
                self.assertEqual(self.runtime.launch(self.launch_id)['state'],'TERMINAL')
                self.assertEqual(self.backend.releases,[])

    def test_unknown_survivors_block_recovery(self):
        self.backend.cleanup_known=False
        with self.assertRaises(AuthorityError):self.supervisor.reconcile()
        self.assertEqual(self.runtime.launch(self.launch_id)['state'],'STOPPING')

    def test_elapsed_deadline_survives_wall_clock_rollback(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.now-=timedelta(days=1);self.elapsed=31
        self.assertEqual(self.supervisor.poll(self.launch_id)['reason'],'TIMEOUT')

    def test_ipc_peer_schema_replay(self):
        process=ProcessIdentity.read(os.getpid())
        peer=PeerIdentity.current()
        protocol=SupervisorProtocol(ControllerEnrollment(peer,process,self.generation),self.runtime)
        request=supervisor_frame(uid(),self.launch_id,self.generation,'STATUS')
        def receive(raw):
            a,b=socket.socketpair()
            try:a.sendall(raw);a.shutdown(socket.SHUT_WR);return protocol.receive(b)
            finally:a.close();b.close()
        self.assertEqual(receive(request)['action'],'STATUS')
        with self.assertRaises(sqlite3.IntegrityError):receive(request)
        for raw in (struct.pack('!I',4097),b'\0\0\0\x02{}',supervisor_frame(uid(),self.launch_id,uid(),'STATUS')):
            with self.assertRaises((AuthorityError,ValidationError)):receive(raw)
        protocol.enrollment=replace(protocol.enrollment,peer=replace(peer,uid=peer.uid+1))
        with self.assertRaises(AuthorityError):receive(request)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.expected=ExpectedRelease(uid(),uid(),'a'*64,uid(),EXPIRY,PeerIdentity.current(),
                                      time.clock_gettime_ns(time.CLOCK_BOOTTIME)+86_400_000_000_000)
        self.payload=FixedPayload(('/usr/bin/true',),ConfinementProfile().environment())

    def channel(self,raw):
        a,b=socket.socketpair();a.sendall(raw);a.shutdown(socket.SHUT_WR)
        self.addCleanup(a.close);self.addCleanup(b.close)
        return b

    def test_valid_fixed_payload_release_and_fd_closed(self):
        gate=ReleaseGate(self.expected,self.payload)
        sock=self.channel(release_frame(self.expected));fd=sock.fileno()
        self.assertIs(gate.authorize(sock,now=lambda:NOW),self.payload)
        with self.assertRaises(OSError):os.fstat(fd)
        with self.assertRaises(AuthorityError):gate.authorize(sock,now=lambda:NOW)

    def test_inherited_channel_binding_does_not_trust_translated_peer(self):
        sock=self.channel(release_frame(self.expected));info=os.fstat(sock.fileno())
        expected=replace(self.expected,channel_identity=(info.st_dev,info.st_ino))
        with patch.object(PeerIdentity,'from_socket',side_effect=AuthorityError('namespace translation')):
            self.assertIs(ReleaseGate(expected,self.payload).authorize(sock,now=lambda:NOW),self.payload)

    def test_inherited_channel_substitution_rejected(self):
        expected=replace(self.expected,channel_identity=(0,0))
        with self.assertRaises(AuthorityError):ReleaseGate(expected,self.payload).authorize(
            self.channel(release_frame(expected)),now=lambda:NOW)

    def test_eof_malformed_extra_duplicate(self):
        valid=release_frame(self.expected)
        for raw in (b'',valid[:5],valid+b'x',valid+valid,struct.pack('!I',2)+b'{}',
                    struct.pack('!I',13)+b'{"x":1,"x":2}',struct.pack('!I',2049)):
            with self.subTest(raw=raw[:4]):
                with self.assertRaises((AuthorityError,ValidationError)):
                    ReleaseGate(self.expected,self.payload).authorize(self.channel(raw),now=lambda:NOW)

    def test_wrong_binding_and_expired(self):
        for expected in (replace(self.expected,launch_id=uid()),replace(self.expected,supervisor_generation=uid()),
                         replace(self.expected,authorization_digest='b'*64),replace(self.expected,nonce=uid())):
            with self.assertRaises(AuthorityError):ReleaseGate(self.expected,self.payload).authorize(
                self.channel(release_frame(expected)),now=lambda:NOW)
        with self.assertRaises(AuthorityError):ReleaseGate(self.expected,self.payload).authorize(
            self.channel(release_frame(self.expected)),now=lambda:NOW+timedelta(days=1))

    def test_timeout_without_sleep(self):
        a,b=socket.socketpair()
        try:
            times=iter((0,10))
            with self.assertRaises(AuthorityError):ReleaseGate(self.expected,self.payload).authorize(b,now=lambda:NOW,monotonic=lambda:next(times))
        finally:a.close();b.close()

    def test_real_exec_child_closes_secret_and_release_fds(self):
        with tempfile.TemporaryFile() as secret:
            channel=self.channel(release_frame(self.expected))
            payload=FixedPayload(('/usr/bin/python3','-I','-c',
                "import os; f=os.listdir('/proc/self/fd'); assert not any(int(x)>2 and os.path.exists('/proc/self/fd/'+x) for x in f)"),
                ConfinementProfile().environment())
            pid=os.fork()
            if pid==0:
                try:
                    with patch('os.chdir'):
                        ReleaseGate(self.expected,payload).execute(channel,now=lambda:NOW)
                    os._exit(99)
                except BaseException:os._exit(77)
            self.assertEqual(os.waitpid(pid,0)[1],0)

    def test_expiry_after_gate_authorize_prevents_exec(self):
        channel=self.channel(release_frame(self.expected))
        pid=os.fork()
        if pid==0:
            try:
                times=iter((NOW,NOW+timedelta(days=1)))
                with patch('os.chdir'):
                    ReleaseGate(self.expected,self.payload).execute(channel,now=lambda:next(times))
                os._exit(99)
            except AuthorityError:os._exit(77)
            except BaseException:os._exit(88)
        self.assertEqual(os.waitpid(pid,0)[1],77<<8)

    def test_elapsed_gate_deadline_rejects_wall_clock_rollback(self):
        with self.assertRaises(AuthorityError):ReleaseGate(self.expected,self.payload).authorize(
            self.channel(release_frame(self.expected)),now=lambda:NOW-timedelta(days=1),
            elapsed_ns=lambda:self.expected.elapsed_deadline_ns)

    def test_release_cannot_supply_payload_fields(self):
        for field in ('argv','uid','environment','mounts','founder','role','grant'):
            data=self.expected.message();data[field]='forged'
            raw=canonical_json(data).encode()
            with self.assertRaises(AuthorityError):ReleaseGate(self.expected,self.payload).authorize(
                self.channel(struct.pack('!I',len(raw))+raw),now=lambda:NOW)


class LinuxPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name);(self.path/'source').mkdir();(self.path/'source/file').write_text('synthetic')
        self.root=TaskRoot(self.path);self.addCleanup(self.root.close)
        self.profile=ConfinementProfile(readable_paths=('source',))

    def test_pinned_mount_argv_and_allowed_read(self):
        mounts=PinnedMounts(self.root,self.profile,expected_identity=self.root.identity)
        self.addCleanup(mounts.close)
        argv=mounts.argv(FixedPayload(('/usr/bin/true',),self.profile.environment()))
        self.assertIn('--ro-bind-fd',argv);self.assertNotIn(str(self.path),argv)
        fd=secure_open(self.root.fd,'source/file')
        try:self.assertEqual(os.read(fd,30),b'synthetic')
        finally:os.close(fd)

    def test_root_identity_and_substitution(self):
        with self.assertRaises(ValidationError):PinnedMounts(self.root,self.profile,expected_identity=(1,2,3,4))
        old=self.path/'source';old.rename(self.path/'old');old.symlink_to('/tmp',target_is_directory=True)
        with self.assertRaises((OSError,ValidationError)):PinnedMounts(self.root,self.profile,expected_identity=self.root.identity)

    def test_special_hardlink_and_git(self):
        (self.path/'source/fifo').touch();(self.path/'source/fifo').unlink();os.mkfifo(self.path/'source/fifo')
        with self.assertRaises(AuthorityError):PinnedMounts(self.root,self.profile,expected_identity=self.root.identity)
        (self.path/'source/fifo').unlink();os.link(self.path/'source/file',self.path/'source/link')
        with self.assertRaises(AuthorityError):PinnedMounts(self.root,self.profile,expected_identity=self.root.identity)
        with self.assertRaises(ValidationError):PinnedMounts(self.root,replace(self.profile,git_metadata='commit'),expected_identity=self.root.identity)

    def test_unexpected_mount_error_fails_closed(self):
        import errno
        with patch('tools.agent_control.supervisor_linux.secure_open',side_effect=OSError(errno.EXDEV,'synthetic crossing')):
            with self.assertRaises(OSError):PinnedMounts(self.root,self.profile,expected_identity=self.root.identity)

    def test_pinned_root_rename_rejected(self):
        mounts=PinnedMounts(self.root,self.profile,expected_identity=self.root.identity)
        self.addCleanup(mounts.close)
        moved=self.path.with_name(self.path.name+'-moved')
        self.path.rename(moved);self.path.mkdir()
        try:
            with self.assertRaises(ValidationError):mounts.argv(FixedPayload(('/usr/bin/true',),self.profile.environment()))
        finally:self.path.rmdir();moved.rename(self.path)

    def test_cgroup_configuration_with_fake_kernel_files(self):
        cg=CgroupV2.__new__(CgroupV2);cg.root_fd=os.dup(self.root.fd);cg.children={}
        self.addCleanup(cg.close)
        settings={}
        with patch.object(cg,'_write',side_effect=lambda name,key,value:settings.update({key:value})):
            cg.create(uid(),cpu_percent=50,memory_bytes=1024,pids=4)
        self.assertEqual(settings,{'cpu.max':'50000 100000','memory.max':'1024',
                                  'memory.swap.max':'0','pids.max':'4','memory.oom.group':'1'})

    def test_no_live_cgroup_or_checkout_artifacts(self):
        with self.assertRaises(AuthorityError):CgroupV2(self.root.fd)
        with self.assertRaises(AuthorityError):InstalledArtifacts({str(self.path/'source/file'):'a'*64})
        worker=WorkerIdentity('FE-01',Role.FRONTEND_ENGINEERING,'no-live-user',3001,3001)
        with self.assertRaises(AuthorityError):drop_worker_identity(worker,allowed_fds=(0,1,2))

    def test_production_backend_cannot_skip_startup_reconciliation(self):
        from tools.agent_control.supervisor_linux import LinuxProcessBackend
        backend=LinuxProcessBackend.__new__(LinuxProcessBackend);backend.reconciled=False
        with self.assertRaises(AuthorityError):backend.prepare({},None)

    def test_pre_fork_failure_closes_parent_resources_after_cleanup(self):
        from dataclasses import asdict
        from types import SimpleNamespace
        from tools.agent_control.supervisor_linux import LinuxProcessBackend
        before=open_fds()
        backend=LinuxProcessBackend.__new__(LinuxProcessBackend)
        backend.reconciled=True;backend.children={};backend.anchor=ProcessIdentity.read(os.getpid())
        launch_id=uid()
        backend.plans={launch_id:(self.root,self.profile,self.root.identity)}
        deadline=ExecutionDeadline.arm(EXPIRY,now=NOW,elapsed=time.clock_gettime(time.CLOCK_BOOTTIME),timeout_seconds=30)
        backend.armed={launch_id:(deadline,os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC))}
        backend.cgroups=SimpleNamespace(create=lambda *a,**k:'launch-'+launch_id,
            kill=lambda *a:None,empty=lambda *a:True,remove_empty=lambda *a:None)
        launch={'launch_id':launch_id,'supervisor_generation':uid(),'deadline':EXPIRY,
            'binding':canonical_json({'supervisor_anchor':asdict(backend.anchor),'workspace':list(self.root.identity)})}
        worker=WorkerIdentity('FE-01',Role.FRONTEND_ENGINEERING,'synthetic',3001,3001)
        record=LaunchRecord(Operation.RUN_TEST,('/usr/bin/true',),'/work',self.profile.environment(),30,65536,
            self.profile.profile_digest,worker,'{}','a'*64,EXPIRY)
        with patch('os.fork',side_effect=OSError('Synthetic fork failure')):
            with self.assertRaises(OSError):backend.prepare(launch,record)
        backend.kill(launch)
        self.assertTrue(backend.empty(launch))
        backend.finish(launch)
        self.assertEqual(open_fds(),before)

    def test_unexpected_fd_rejected(self):
        fd=os.open(self.path/'source/file',os.O_RDONLY)
        try:
            with self.assertRaises(AuthorityError):verify_worker_fds()
        finally:os.close(fd)

    def test_child_descriptor_closure_secret_and_sockets(self):
        secret=os.open(self.path/'source/file',os.O_RDONLY)
        a,b=socket.socketpair()
        pid=os.fork()
        if pid==0:
            try:
                close_worker_fds();verify_worker_fds()
                os._exit(0 if open_fds()=={0,1,2} else 1)
            except BaseException:os._exit(2)
        try:self.assertEqual(os.waitpid(pid,0)[1],0)
        finally:os.close(secret);a.close();b.close()

    def test_allowlisted_bootstrap_fd_survives(self):
        fd=os.open(self.path/'source/file',os.O_RDONLY)
        pid=os.fork()
        if pid==0:
            try:
                close_except((0,1,2,fd));os._exit(0 if os.read(fd,20)==b'synthetic' else 1)
            except BaseException:os._exit(2)
        try:self.assertEqual(os.waitpid(pid,0)[1],0)
        finally:os.close(fd)


class ProvisioningTests(unittest.TestCase):
    def test_manifest_is_unapproved_and_hashed(self):
        from tools.agent_control.provisioning import review_manifest,validate_approved_manifest
        manifest=review_manifest(Path(__file__).resolve().parents[2])
        self.assertFalse(manifest['approved']);self.assertFalse(manifest['activation'])
        self.assertEqual(len(manifest['accounts']),5)
        self.assertTrue(all(a['uid'] is None and not a['supplementary_groups'] for a in manifest['accounts']))
        self.assertTrue(all(len(f['sha256'])==64 and f['owner']=='root' for f in manifest['files']))
        with self.assertRaises(ValidationError):validate_approved_manifest(manifest)
