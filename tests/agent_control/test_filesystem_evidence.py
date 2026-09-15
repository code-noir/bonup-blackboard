"""Block 2 synthetic filesystem/evidence tests. No mount, UID or service changes."""
from dataclasses import replace
import errno
import os
from pathlib import Path
import socket
import tempfile
from datetime import datetime,timezone
import unittest
from unittest.mock import patch
from uuid import uuid4
from types import SimpleNamespace

from tools.agent_control.filesystem_evidence import (Export, RootMapping, StoragePolicy,
    FilesystemInspector, mount_id, ExpectedFilesystem)
from tools.agent_control.confinement import TaskRoot, ConfinementProfile
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.release_gate import FixedPayload
from tools.agent_control.supervisor_linux import secure_open, open_fds, close_worker_fds
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control.composition import (ApprovedPlan, SupervisorEndpoint, RemoteProcessBackend, OfflineTransport, ControllerRuntime, message)
from tools.agent_control.execution import LaunchRecord
from tools.agent_control.identity import WorkerIdentity, ProcessIdentity
from tools.agent_control.protocol import Operation
from tools.agent_control.types import Role
from tools.agent_control.supervisor import SyntheticProcessBackend, ExecutionDeadline
from tools.agent_control.composition_protocol import frame
from tools.agent_control.paths import PathRule


def uid(): return str(uuid4())


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'workspace'
        self.path.mkdir(mode=0o700)
        (self.path/'source').mkdir()
        (self.path/'source/file').write_text('synthetic A')
        info=TaskRoot._identity(self.path.stat())
        fd=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY)
        try: storage=StoragePolicy(mount_id(fd))
        finally: os.close(fd)
        self.profile=ConfinementProfile(writable_paths=('source',))
        self.mapping=RootMapping(uid(),str(self.path),info,1,
            (Export(uid(),'source',TaskRoot._identity((self.path/'source').stat()),'DIRECTORY',True),),
            self.profile,storage)
        self.inspector=FilesystemInspector((self.mapping,),storage_probe=lambda fd,policy:policy.data())
        self.addCleanup(self.inspector.disconnect)
        self.launch,self.generation=uid(),uid()
        self.payload=FixedPayload(('/usr/bin/true',),self.profile.environment())

    def pin(self):
        return self.inspector.prepare(self.mapping.logical_id,self.mapping.expectation().policy_digest,
                                      self.launch,self.generation)

    def test_valid_mapping_pins_exact_descriptor_and_no_paths_in_evidence(self):
        handle=self.pin()
        evidence=handle.evidence()
        self.mapping.expectation().accept(evidence,self.launch,self.generation)
        self.assertNotIn(str(self.path),canonical_json(evidence))
        self.assertNotIn('fd',evidence)
        argv=handle.argv(self.launch,self.payload)
        self.assertNotIn(str(self.path),argv)
        self.assertIn('--bind-fd',argv)
        self.assertEqual(os.fstat(handle.pass_fds[0]).st_ino,self.mapping.exports[0].object_identity[1])

    def test_unknown_id_arbitrary_path_and_stale_generation_rejected(self):
        for root in (str(self.path),uid()):
            with self.assertRaises((AuthorityError,ValidationError)):
                self.inspector.prepare(root,self.mapping.expectation().policy_digest,self.launch,self.generation)
        newer=replace(self.mapping,generation=2)
        with self.assertRaises(AuthorityError):
            self.inspector.prepare(self.mapping.logical_id,newer.expectation().policy_digest,self.launch,self.generation)

    def test_immutable_mapping_and_registry(self):
        with self.assertRaises(Exception):self.mapping.generation=9
        with self.assertRaises(TypeError):self.inspector.mappings[self.mapping.logical_id]=replace(self.mapping,generation=2)

    def test_wrong_owner_device_inode_rejected_without_leak(self):
        for index in range(4):
            value=list(self.mapping.object_identity);value[index]+=1
            mapping=replace(self.mapping,object_identity=tuple(value))
            inspector=FilesystemInspector((mapping,),storage_probe=lambda fd,p:p.data())
            before=open_fds()
            with self.assertRaises((AuthorityError,ValidationError)):
                inspector.prepare(mapping.logical_id,mapping.expectation().policy_digest,uid(),self.generation)
            self.assertEqual(open_fds(),before)

    def test_symlink_and_magic_link_root_rejected(self):
        original=self.path.with_name('original')
        self.path.rename(original)
        for target in (str(original),'/proc/self/fd/0'):
            self.path.symlink_to(target)
            with self.assertRaises((OSError,ValidationError,AuthorityError)):self.pin()
            self.path.unlink()
            self.launch=uid()

    def test_parent_root_substitution_rejected(self):
        handle=self.pin()
        self.path.rename(self.path.with_name('old'))
        self.path.mkdir()
        with self.assertRaises((AuthorityError,ValidationError)):handle.argv(self.launch,self.payload)

    def test_export_swap_after_open_keeps_inspected_object(self):
        original=secure_open
        def swap(fd,path,**kw):
            result=original(fd,path,**kw)
            if path=='source':
                (self.path/'source').rename(self.path/'old-source')
                (self.path/'source').mkdir()
                (self.path/'source/other').write_text('synthetic B')
            return result
        with patch('tools.agent_control.supervisor_linux.secure_open',side_effect=swap):
            handle=self.pin()
        self.assertEqual(os.listdir(handle.pass_fds[0]),['file'])
        self.assertEqual(handle.argv(self.launch,self.payload)[-1],'/usr/bin/true')

    def test_export_rename_retains_same_object(self):
        handle=self.pin();inode=os.fstat(handle.pass_fds[0]).st_ino
        (self.path/'source').rename(self.path/'renamed')
        self.assertEqual(os.fstat(handle.pass_fds[0]).st_ino,inode)
        self.assertIn(str(handle.pass_fds[0]),handle.argv(self.launch,self.payload))

    def test_export_replaced_before_pin_rejected(self):
        (self.path/'source').rename(self.path/'old-source')
        (self.path/'source').mkdir()
        with self.assertRaises(AuthorityError):self.pin()

    def test_fifo_socket_hardlink_exports_rejected(self):
        fifo=self.path/'source/pipe';os.mkfifo(fifo)
        with self.assertRaises((OSError,AuthorityError,ValidationError)):self.pin()
        fifo.unlink();self.launch=uid()
        sock=socket.socket(socket.AF_UNIX);self.addCleanup(sock.close)
        sock.bind(str(self.path/'source/socket'))
        with self.assertRaises((OSError,AuthorityError,ValidationError)):self.pin()
        (self.path/'source/socket').unlink();self.launch=uid()
        os.link(self.path/'source/file',self.path/'source/link')
        with self.assertRaises((OSError,AuthorityError,ValidationError)):self.pin()

    def test_nested_mount_crossing_rejected(self):
        before=open_fds()
        original=secure_open
        def cross(fd,path,**kw):
            if path=='source':raise OSError(errno.EXDEV,'synthetic nested mount')
            return original(fd,path,**kw)
        with patch('tools.agent_control.supervisor_linux.secure_open',side_effect=cross):
            with self.assertRaises(OSError):self.pin()
        self.assertEqual(open_fds(),before)

    def test_root_mount_identity_and_storage_probe_mismatch_rejected(self):
        wrong=replace(self.mapping,storage=replace(self.mapping.storage,mount_id=self.mapping.storage.mount_id+1))
        inspector=FilesystemInspector((wrong,),storage_probe=lambda fd,p:p.data())
        with self.assertRaises(AuthorityError):
            inspector.prepare(wrong.logical_id,wrong.expectation().policy_digest,uid(),self.generation)
        self.inspector.storage_probe=lambda fd,p:dict(p.data(),bytes=2**40)
        with self.assertRaises(AuthorityError):self.pin()

    def test_evidence_cannot_change_scope_repository_owner_profile_or_storage(self):
        proof=self.pin().evidence()
        for field in ('identity','generation','repository_id','profile_digest','storage','exports'):
            modified=__import__('copy').deepcopy(proof)
            if field=='identity':modified['policy'][field][2]+=1
            elif field=='generation':modified['policy'][field]+=1
            elif field=='repository_id':modified['policy'][field]=uid()
            elif field=='profile_digest':modified['policy'][field]='a'*64
            elif field=='storage':modified['policy'][field]['bytes']*=2
            else:modified['policy'][field][0]['relative']='other-worker'
            modified['policy_digest']=digest(modified['policy'])
            modified['evidence_digest']=digest({k:v for k,v in modified.items() if k!='evidence_digest'})
            with self.subTest(field=field),self.assertRaises(AuthorityError):
                self.mapping.expectation().accept(modified,self.launch,self.generation)

    def test_cancellation_disconnect_close_and_stale_launch_reuse_rejected(self):
        handle=self.pin();fds=handle.pass_fds
        with self.assertRaises(AuthorityError):handle.argv(uid(),self.payload)
        self.inspector.close(self.launch)
        for fd in fds:
            with self.assertRaises(OSError):os.fstat(fd)
        with self.assertRaises(AuthorityError):handle.argv(self.launch,self.payload)
        with self.assertRaises(AuthorityError):self.pin()
        self.launch=uid();handle=self.pin();fds=handle.pass_fds
        self.inspector.disconnect()
        for fd in fds:
            with self.assertRaises(OSError):os.fstat(fd)

    def test_payload_descriptor_closure(self):
        handle=self.pin()
        self.assertTrue(all(not os.get_inheritable(fd) for fd in handle.pass_fds))
        pid=os.fork()
        if pid==0:
            try:
                close_worker_fds()
                os._exit(0 if open_fds()=={0,1,2} else 1)
            except BaseException:os._exit(2)
        self.assertEqual(os.waitpid(pid,0)[1],0)

    def test_controller_view_performs_no_filesystem_io(self):
        view=self.mapping.expectation().root_view('/logical/controller-metadata')
        with patch('os.open',side_effect=AssertionError('controller filesystem read')):
            view.verify();view.inspect('source/file',create=True)
            self.assertEqual(list(view.export_entries('source')),[('source','DIRECTORY')])
            with self.assertRaises(AuthorityError):view.open_read('source/file')

    def test_metadata_only_scope_denies_protected_descendant_without_inspection(self):
        view=self.mapping.expectation().root_view('/logical/controller-metadata')
        with patch('os.open',side_effect=AssertionError('controller filesystem read')):
            for rule in (PathRule('FILE','source/private'),PathRule('DIRECTORY','source/secrets'),
                         PathRule('GLOB','source/**/*.key')):
                with self.assertRaises(ValidationError):view.check_export_denials('source',(rule,))
            view.check_export_denials('source',(PathRule('DIRECTORY','unmounted'),))

    def test_git_external_references_and_config_rejected(self):
        git=self.path/'.git';git.mkdir()
        (git/'config').write_text('[core]\nrepositoryformatversion=0\nbare=false\n')
        mapping=replace(self.mapping,repository_id=uid(),repository_identity=TaskRoot._identity(git.stat()))
        inspector=FilesystemInspector((mapping,),storage_probe=lambda fd,p:p.data())
        handle=inspector.prepare(mapping.logical_id,mapping.expectation().policy_digest,uid(),self.generation)
        self.assertFalse(any('/.git' in arg for arg in handle.argv(handle.launch_id,self.payload)))
        inspector.disconnect()
        for name in ('commondir','gitdir'):
            (git/name).write_text('/synthetic/external')
            with self.assertRaises(AuthorityError):
                inspector.prepare(mapping.logical_id,mapping.expectation().policy_digest,uid(),self.generation)
            (git/name).unlink()
        (git/'objects/info').mkdir(parents=True)
        (git/'objects/info/alternates').write_text('/synthetic/external')
        with self.assertRaises(AuthorityError):
            inspector.prepare(mapping.logical_id,mapping.expectation().policy_digest,uid(),self.generation)
        (git/'objects/info/alternates').unlink()
        (git/'config').write_text('[core]\nrepositoryformatversion=0\nbare=false\n[credential]\nhelper=unsafe\n')
        with self.assertRaises(AuthorityError):
            inspector.prepare(mapping.logical_id,mapping.expectation().policy_digest,uid(),self.generation)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        FilesystemTests.setUp(self)
        self.now=datetime(2026,9,15,tzinfo=timezone.utc)
        self.expiry='2026-09-15T00:00:30+00:00'
        self.boot=uid();self.execution=uid()
        self.record=LaunchRecord(Operation.RUN_TEST,('/usr/bin/true',),'/work',self.profile.environment(),
            30,65536,self.profile.profile_digest,WorkerIdentity('FE-01',Role.FRONTEND_ENGINEERING,
            'synthetic',os.getuid(),os.getgid()),'{}','b'*64,self.expiry,elapsed_deadline=30)
        self.backend=SyntheticProcessBackend(ProcessIdentity(self.boot,42000,123))
        self.argv=[];self.inspected_fds=[]
        def prepare_pinned(launch,record,handle):
            self.argv.append(handle.argv(launch['launch_id'],self.payload))
            self.inspected_fds.extend(handle.pass_fds)
            return self.backend.prepare(launch,record)
        self.backend.prepare_pinned=prepare_pinned
        self.expected=self.mapping.expectation()
        self.plan=ApprovedPlan(uid(),self.execution,self.record,self.mapping.object_identity,'c'*64,
            self.backend.process,filesystem=self.expected)
        self.endpoint=SupervisorEndpoint((self.plan,),self.backend,generation=self.generation,boot_id=self.boot,
            now=lambda:self.now,elapsed=lambda:0,inspector=self.inspector)
        self.addCleanup(self.endpoint.disconnect)
        self.transport=OfflineTransport(self.endpoint)
        self.remote=RemoteProcessBackend(self.transport,{self.execution:self.plan.plan_id},
            generation=self.generation,boot_id=self.boot,filesystem_expectations={self.execution:self.expected})
        self.assertTrue(self.remote.reconcile_unknown())
        self.row=dict(launch_id=self.launch,execution_id=self.execution,request_id=uid(),
            binding=canonical_json(dict(workspace=list(self.mapping.object_identity),repository=None)),reason='CANCELLED')
        self.remote.arm_deadline(self.launch,ExecutionDeadline.arm(self.expiry,now=self.now,elapsed=0,timeout_seconds=30))

    def test_evidence_handoff_and_fd_based_plan_then_release(self):
        self.remote.prepare(self.row,self.record)
        self.assertTrue(self.argv)
        self.assertFalse(self.inspector.handles)
        for fd in self.inspected_fds:
            with self.assertRaises(OSError):os.fstat(fd)
        self.remote.release(self.row,self.record)
        self.assertEqual(self.backend.releases,[self.launch])
        self.assertNotIn(str(self.path),canonical_json(self.transport.sent))

    def test_mismatched_evidence_denies_release_even_with_new_digest(self):
        exchange=self.transport.exchange
        def corrupt(request):
            reply=exchange(request)
            if reply['action']=='PREPARED_EVIDENCE':
                evidence=reply['data']['filesystem_evidence']
                evidence['policy']['identity'][2]+=1
                evidence['policy_digest']=digest(evidence['policy'])
                evidence['evidence_digest']=digest({k:v for k,v in evidence.items() if k!='evidence_digest'})
            return reply
        with patch.object(self.transport,'exchange',side_effect=corrupt):
            with self.assertRaises(AuthorityError):self.remote.prepare(self.row,self.record)
        with self.assertRaises(AuthorityError):self.remote.release(self.row,self.record)
        self.remote.kill(self.row)
        self.assertEqual(self.backend.releases,[])
        self.assertFalse(self.inspector.handles)

    def test_policy_replacement_after_prepared_cannot_release(self):
        self.remote.prepare(self.row,self.record)
        self.remote.filesystem_expectations[self.execution]=replace(self.mapping,generation=2).expectation()
        with self.assertRaises(AuthorityError):self.remote.release(self.row,self.record)
        self.assertEqual(self.backend.releases,[])

    def test_controller_authorization_requires_exact_remote_policy(self):
        controller=ControllerRuntime.__new__(ControllerRuntime)
        request=uid()
        controller.proposals={(self.execution,request):(object(),object())}
        root=self.expected.root_view(str(self.path))
        controller.authorization=SimpleNamespace(_check=lambda *args:self.record,
            store=SimpleNamespace(load=lambda execution:SimpleNamespace(root=root)))
        controller.remote=self.remote
        self.assertEqual(controller._authorize(self.execution,request),self.record)
        self.remote.filesystem_expectations[self.execution]=replace(self.mapping,generation=2).expectation()
        with self.assertRaises(AuthorityError):controller._authorize(self.execution,request)
        self.remote.filesystem_expectations.clear()
        with self.assertRaises(AuthorityError):controller._authorize(self.execution,request)
        self.assertEqual(self.backend.releases,[])

    def test_preparation_failure_closes_every_inspection_fd(self):
        before=open_fds()
        self.backend.fail_setup=True
        with self.assertRaises(AuthorityError):self.remote.prepare(self.row,self.record)
        self.assertEqual(open_fds(),before)
        self.assertFalse(self.inspector.handles)
        self.assertEqual(self.backend.releases,[])

    def test_disconnect_during_prepare_closes_pins_and_denies_release(self):
        self.backend.before_ready=self.endpoint.disconnect
        with self.assertRaises(AuthorityError):self.remote.prepare(self.row,self.record)
        self.assertFalse(self.inspector.handles)
        self.assertEqual(self.backend.releases,[])

    def test_reconciliation_failure_closes_retained_descriptors(self):
        handle=self.inspector.prepare(self.mapping.logical_id,self.expected.policy_digest,self.launch,self.generation)
        fds=handle.pass_fds
        with patch.object(self.backend,'reconcile_unknown',side_effect=AuthorityError('synthetic failure')):
            with self.assertRaises(AuthorityError):self.remote.reconcile_unknown()
        for fd in fds:
            with self.assertRaises(OSError):os.fstat(fd)

    def test_v1_downgrade_and_arbitrary_path_in_request_rejected(self):
        self.remote.filesystem_expectations.clear()
        with self.assertRaises(AuthorityError):self.remote.prepare(self.row,self.record)
        self.assertEqual(self.backend.releases,[])
        request=message('HEARTBEAT',self.launch,self.generation,self.boot,dict(ready=True))
        request['data']['host_root']=str(self.path)
        with self.assertRaises(ValidationError):frame(request)

    def test_durable_worker_repository_and_profile_mismatch_denied(self):
        for updated in (replace(self.record,worker=replace(self.record.worker,uid=self.record.worker.uid+1)),
                        replace(self.record,profile_digest='a'*64)):
            with self.assertRaises(AuthorityError):self.remote.prepare(self.row,updated)
        altered=dict(self.row,binding=canonical_json(dict(workspace=list(self.mapping.object_identity),repository=[1,2,3,4])))
        with self.assertRaises(AuthorityError):self.remote.prepare(altered,self.record)
        self.assertEqual(self.backend.releases,[])
