"""Installed factories with temporary AF_UNIX and explicit fake kernel effects.

Nothing here installs services, switches UID, mounts tmpfs or writes live cgroups.
The production factories/authorization/protocol/gate are exercised; kernel effect
substitution is confined to this test module and is not selectable by installed JSON.
"""
from dataclasses import asdict, replace
from datetime import timedelta
import copy
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_supervisor as fixtures
from tools.agent_control import installed_runtime as ir
from tools.agent_control import installed_config as ic
from tools.agent_control.installed_transport import Packet, packet, UnixTransport, UnixRPCClient, SystemdNotifier
from tools.agent_control.identity import PeerIdentity, ProcessIdentity, WorkerIdentity
from tools.agent_control.service_runtime import PeerEnrollment
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.protocol import bounded_json
from tools.agent_control.integration_policy import IntegrationPolicy
from tools.agent_control.provisioning import MODULES, POLICIES
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control.supervisor_linux import LinuxProcessBackend, CgroupV2, InstalledArtifacts


def uid(): return str(uuid4())


def manifest_for(controller,supervisor):
    additions=('bootstrap_entry','composition','composition_protocol','controller_entry',
        'filesystem_evidence','installed_config','installed_transport','installed_runtime',
        'integration_policy','resource_supervision','service_runtime','supervisor_entry')
    names={ic.PREFIX+'/tools/agent_control/'+n+'.py' for n in (*MODULES,*additions)}
    names.update(ic.PREFIX+'/docs/agent-control/'+n+'.json' for n in POLICIES)
    names.update(ic.PREFIX+'/'+n for n in ('bootstrap_entry.py','gate_entry.py','controller','supervisor'))
    identities=dict(version=1,provisioning_generation=1,accounts=[
        dict(username=n,uid=3000+i,gid=3000+i,groups=[],shell='/usr/sbin/nologin',password='LOCKED',ssh=False)
        for i,n in enumerate(('bonup-agentctl','bonup-arch01','bonup-fe01','bonup-be01','bonup-qa01'))])
    m=dict(version=2,approved=True,activation=True,provisioning_generation=1,source_commit='be8270ea2c067612843504d5835aee6cc772f940',
        identity_map_digest=digest(identities),configuration_digests=dict(controller=digest(controller),supervisor=digest(supervisor)),
        files={n:'a'*64 for n in sorted(names)},resource_digest=IntegrationPolicy().policy_digest)
    m['bundle_digest']=digest(m)
    return m,identities


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.c,self.s={'controller':'synthetic'},{'supervisor':'synthetic'}
        self.m,self.i=manifest_for(self.c,self.s)
    def verify(self):return ic.validate_activation(self.m,self.i,self.c,component='controller')
    def resign(self):self.m['bundle_digest']=digest({k:v for k,v in self.m.items() if k!='bundle_digest'})
    def test_complete_attestation(self):self.assertEqual(self.verify(),digest(self.m))
    def test_unapproved_rejected(self):
        self.m['approved']=False;self.resign()
        with self.assertRaises(AuthorityError):self.verify()
    def test_activation_false_rejected(self):
        self.m['activation']=False;self.resign()
        with self.assertRaises(AuthorityError):self.verify()
    def test_wrong_generation(self):
        self.m['provisioning_generation']=2;self.resign()
        with self.assertRaises(AuthorityError):self.verify()
    def test_digest_mismatch(self):
        self.m['bundle_digest']='b'*64
        with self.assertRaises(AuthorityError):self.verify()
    def test_changed_configuration(self):
        self.c['controller']='changed'
        with self.assertRaises(AuthorityError):self.verify()
    def test_approved_source_commit_is_not_self_referential_code_constant(self):
        self.m['source_commit']='b'*40;self.resign()
        self.assertEqual(self.verify(),digest(self.m))
    def test_malformed_source_commit_rejected(self):
        self.m['source_commit']='not-a-commit';self.resign()
        with self.assertRaises(AuthorityError):self.verify()
    def test_missing_dependency(self):
        self.m['files'].pop(ic.PREFIX+'/tools/agent_control/runtime.py');self.resign()
        with self.assertRaises(AuthorityError):self.verify()
    def test_unknown_adapter_field(self):
        self.m['adapter']='tests.fake'
        with self.assertRaises(ValidationError):self.verify()
    def test_repository_artifact_rejected(self):
        self.m['files']['/home/bonup/bonup-blackboard/main.py']='a'*64;self.resign()
        with self.assertRaises(ValidationError):self.verify()
    def test_no_environment_adapter_selection(self):
        with patch.dict(os.environ,{'BONUP_ADAPTER':'tests.fake','PYTHONPATH':'/synthetic/evil'}):
            c=ir.build_installed_controller_adapters();s=ir.build_installed_supervisor_adapters()
            self.assertIs(type(c),ir.InstalledControllerAdapters)
            self.assertIs(type(s),ir.InstalledSupervisorAdapters)
            self.assertIs(type(s.io),ir.KernelIO)
            self.assertFalse(hasattr(s,'open_registry'))
    def test_checkout_code_cannot_activate(self):
        with self.assertRaises(AuthorityError):ir.KernelIO().verify_code(self.m['files'])
    def test_missing_manifest_fails_before_backend(self):
        io=ir.KernelIO()
        with patch.object(io,'read',side_effect=FileNotFoundError),patch.object(io,'backend') as backend:
            with self.assertRaises(FileNotFoundError):ir.build_installed_supervisor_adapters(_io=io).load_config(ir.SUPERVISOR)
            backend.assert_not_called()
    def test_controller_never_reads_supervisor_catalog(self):
        from tools.agent_control import installation_bundle as bundle
        io=ir.KernelIO();seen=[]
        m,_=bundle.build(Path(__file__).resolve().parents[2],source_commit=bundle.SOURCE_COMMIT)
        m['approved']=True;m['integration_services_approved']=True;bundle.seal(m)
        c=bundle.configurations()['controller'];i=bundle.identities()
        observations=[dict(row,device=1,inode=n+1,created=True)
                      for n,row in enumerate(bundle.receipt_objects(m))]
        accounts=[dict(a,created=True,group_created=True) for a in i['accounts']]
        receipt=bundle.make_receipt(m,observations,accounts=accounts,
            boot_id='00000000-0000-4000-8000-000000000001',installed_at='2026-09-15T00:00:00Z')
        def read(path):
            seen.append(path)
            return {ic.MANIFEST:m,ic.IDENTITIES:i,ir.CONTROLLER:c,
                    bundle.ETC+'/installation-receipt.json':receipt}[path]
        with patch.object(io,'read',side_effect=read),patch.object(io,'verify_code'),patch.object(io,'notifier'), \
                patch.object(io,'open_registry'),patch.object(io,'capabilities',return_value=()), \
                patch('tools.agent_control.controller_entry.validate_registry'), \
                patch.object(io,'enroll',side_effect=AuthorityError('enrollment sentinel')) as enroll:
            with self.assertRaisesRegex(AuthorityError,'enrollment sentinel'):
                ir.build_installed_controller_adapters(_io=io).load_config(ir.CONTROLLER)
            enroll.assert_called_once()
        self.assertEqual(seen,[ic.MANIFEST,ic.IDENTITIES,ir.CONTROLLER,bundle.ETC+'/installation-receipt.json'])
        self.assertNotIn(ir.SUPERVISOR,seen)
    def test_production_factory_dependencies_are_fixed(self):
        import inspect
        source=inspect.getsource(ir)
        for forbidden in ('importlib','SyntheticProcessBackend','ResourceBackend(', 'from tests', 'sys.path.insert'):
            self.assertNotIn(forbidden,source)
        self.assertIn('LinuxProcessBackend(artifacts,cgroups',source)
        self.assertIn('CgroupV2(fd)',source)
    def test_entrypoints_have_fixed_default_factories(self):
        import inspect
        from tools.agent_control import controller_entry,supervisor_entry
        self.assertIsNone(inspect.signature(controller_entry.main).parameters['adapters'].default)
        self.assertIsNone(inspect.signature(supervisor_entry.main).parameters['adapters'].default)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.bind(str(Path(self.temp.name)/'test.sock'));self.sock.listen(1)
        self.process=ProcessIdentity.read(os.getpid())
        self.peer=PeerIdentity.current()
        self.enrollment=PeerEnrollment('controller',self.peer.uid,self.peer.gid,self.process,uid(),uid())
        self.transport=UnixTransport(self.sock,self.enrollment)
        self.addCleanup(self.transport.close)
        self.client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.client.connect(self.sock.getsockname());self.addCleanup(self.client.close)
        self.handshake=dict(endpoint='controller',generation=self.enrollment.generation,enrollment_id=self.enrollment.enrollment_id)
    def accept(self):
        self.client.sendall(packet(self.handshake))
        self.assertIsNone(self.transport.accept()) # header
        return self.transport.accept()
    def test_real_unix_kernel_peer_and_cloexec(self):
        self.assertEqual(self.accept()[0],self.peer)
        self.assertFalse(self.transport.conn.get_inheritable())
    def test_wrong_uid_denied(self):
        self.transport.auth.enrollment=replace(self.enrollment,uid=self.peer.uid+1)
        with self.assertRaises(AuthorityError):self.accept()
    def test_wrong_start_identity_denied(self):
        self.transport.auth.enrollment=replace(self.enrollment,process=replace(self.process,start_ticks=self.process.start_ticks+1))
        with self.assertRaises(AuthorityError):self.accept()
    def test_wrong_generation_denied(self):
        self.handshake['generation']=uid()
        with self.assertRaises(AuthorityError):self.accept()
    def test_no_tcp_fallback(self):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
            with self.assertRaises(AuthorityError):UnixTransport(sock,self.enrollment)
    def test_partial_timeout(self):
        p=Packet(0);self.assertIsNone(p.feed(b'\0',0))
        with self.assertRaises(AuthorityError):p.feed(b'\0',1)
    def test_bad_json_duplicate_keys_unknown_handshake(self):
        for raw in (b'{"a":1,"a":2}',b'\xff'):
            with self.assertRaises(ValidationError):Packet(0).feed(struct.pack('!I',len(raw))+raw,0)
        self.handshake['uid']=0
        with self.assertRaises(ValidationError):self.accept()
    def test_oversized_frame(self):
        with self.assertRaises(ValidationError):Packet(0).feed(struct.pack('!I',4097),0)
    def test_disconnect_visible(self):
        self.accept();self.transport.poll(4);self.client.close()
        self.assertEqual(self.transport.poll(4),[('disconnect',b'')])
    def test_replay_enrollment_denied(self):
        observed=self.accept()
        with self.assertRaises(AuthorityError):self.transport.auth.verify(*observed,consume=True)
    def test_stream_frames_do_not_assume_message_boundaries(self):
        self.accept();self.transport.poll(4)
        self.client.sendall(packet({'one':1})+packet({'two':2}))
        self.assertEqual(self.transport.poll(4),[])
        first=self.transport.poll(4)
        self.assertEqual(bounded_json(first[0][1][4:]),{'one':1})
        self.assertEqual(self.transport.poll(4),[])
        second=self.transport.poll(4)
        self.assertEqual(bounded_json(second[0][1][4:]),{'two':2})


class KernelContractTests(unittest.TestCase):
    def test_pinned_interface_requires_handle_no_fallback(self):
        backend=LinuxProcessBackend.__new__(LinuxProcessBackend);backend.reconciled=True
        with self.assertRaises(AuthorityError),patch.object(backend,'_prepare') as prepare:
            backend.prepare_pinned({'launch_id':uid()},None,object())
        prepare.assert_not_called()
    def test_live_cgroup_requires_real_cgroup_filesystem(self):
        with tempfile.TemporaryDirectory() as p:
            fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
            try:
                with self.assertRaises(AuthorityError):CgroupV2(fd)
            finally:os.close(fd)
    def test_repository_gate_rejected(self):
        with self.assertRaises(AuthorityError):InstalledArtifacts({'/home/bonup/bonup-blackboard/gate.py':'a'*64})
    def test_notifier_emits_only_known_bounded_messages(self):
        from unittest.mock import MagicMock
        sock=MagicMock();sock.__enter__.return_value=sock;sock.send.side_effect=lambda raw:len(raw)
        with patch('tools.agent_control.installed_transport.socket.socket',return_value=sock):
            notifier=SystemdNotifier('/run/systemd/notify')
            for value in ('READY=1','WATCHDOG=1','STOPPING=1'):notifier(value)
            with self.assertRaises(ValidationError):notifier('EXEC=anything')
        self.assertEqual(sock.send.call_count,3)
    def test_notifier_error_observable(self):
        with patch('tools.agent_control.installed_transport.socket.socket',side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):SystemdNotifier('/run/systemd/notify')('READY=1')
    def test_bad_notifier_path(self):
        for path in ('/home/bonup/socket','tcp://localhost','../notify','@random'):
            with self.assertRaises(ValidationError):SystemdNotifier(path)
    def test_deadline_lane_runs_without_request_handler(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        backend=Mock();io=SimpleNamespace(wall=lambda:fixtures.NOW,now=lambda:.25)
        deadline=ir.DeadlineService(backend,io);deadline.step()
        backend.service_deadlines.assert_called_once_with(now=fixtures.NOW,elapsed=.25)

    def test_preparing_linux_child_is_not_reported_exited(self):
        backend=LinuxProcessBackend.__new__(LinuxProcessBackend)
        backend.release_lock=threading.RLock()
        key=uid();backend.children={key:dict(preparing=True,pid=None)}
        with patch('os.waitpid') as wait:
            self.assertFalse(backend.exited({'launch_id':key}))
            wait.assert_not_called()

    def test_duplicate_kernel_deadline_rejected_before_syscall(self):
        backend=LinuxProcessBackend.__new__(LinuxProcessBackend)
        key=uid();backend.armed={key:object()};backend.results={}
        with self.assertRaises(AuthorityError):backend.arm_deadline(key,None)

    def test_terminal_output_evidence_survives_fd_cleanup(self):
        backend=LinuxProcessBackend.__new__(LinuxProcessBackend)
        backend.release_lock=threading.RLock();backend.children={}
        key=uid();backend.results={key:{'stdout':dict(retained=65536,truncated=True),
                                       'stderr':dict(retained=0,truncated=False)}}
        result=backend.output_evidence({'launch_id':key})
        self.assertTrue(result['stdout']['truncated'])
        result['stdout']['retained']=0
        self.assertEqual(backend.output_evidence({'launch_id':key})['stdout']['retained'],65536)

    def test_cgroup_open_failure_has_no_synthetic_fallback(self):
        io=ir.KernelIO()
        with patch.object(io,'verify_supervisor_capabilities'),patch('os.open',side_effect=OSError('synthetic cgroup unavailable')) as opened:
            with self.assertRaises(OSError):io.backend(None,fixtures.U)
        self.assertEqual(opened.call_args.args[0],ir.CGROUP)


class KernelEffects(LinuxProcessBackend):
    """Test-only kernel effect substitution; retains real prepare_pinned dispatch."""
    def __init__(self,io,files):
        from types import SimpleNamespace
        self.io=io;self.artifacts=SimpleNamespace(files=files)
        self.reconciled=False;self.children={};self.armed={};self.plans={}
        self.releases=[];self.cleanup_known=True;self.fail_prepare=False;self.eof=False
        self.fixed=[];self.gates=[];self.used=set();self.before_prepare=None
    def reconcile_unknown(self):
        self.reconciled=self.cleanup_known
        if self.cleanup_known:self.children.clear()
        return self.reconciled
    def arm_deadline(self,key,deadline):
        if key in self.armed:raise AuthorityError('Test deadline replay.')
        self.armed[key]=deadline
    def _prepare(self,launch,record,stack,handle=None):
        from tools.agent_control.resource_supervision import build_plan
        if self.fail_prepare:raise AuthorityError('Injected pinned preparation failure.')
        if self.before_prepare is not None:self.before_prepare()
        self.assert_handle=handle
        handle.verify(launch['launch_id'])
        config=os.memfd_create('synthetic-config',os.MFD_CLOEXEC);stack.callback(os.close,config)
        a,b=socket.socketpair();stack.callback(a.close);stack.callback(b.close)
        self.fixed.append(build_plan(launch,record,handle,config_fd=config,release_fd=b.fileno()))
        self.children[launch['launch_id']]=dict(preparing=True,alive=True)
        return ProcessIdentity(fixtures.U,42002,125)
    def release(self,launch,record):
        from tools.agent_control.release_gate import ExpectedRelease,FixedPayload,ReleaseGate,release_frame
        key=launch['launch_id']
        if key in self.used or not self.children[key]['alive']:raise AuthorityError('Duplicate/stopped release.')
        self.used.add(key)
        a,b=socket.socketpair()
        try:
            expected=ExpectedRelease(key,launch['supervisor_generation'],record.authorization_digest,
                uid(),record.expires_at,PeerIdentity.current(),int(self.armed[key].elapsed_deadline*1e9))
            gate=ReleaseGate(expected,FixedPayload(record.argv,record.environment));self.gates.append(gate)
            if not self.eof:a.sendall(release_frame(expected))
            a.shutdown(socket.SHUT_WR)
            gate.authorize(b,now=self.io.wall,elapsed_ns=lambda:int(self.io.now()*1e9))
            self.releases.append(key)
            from tools.agent_control.exec_start import ExecStart
            return ExecStart(key,launch['supervisor_generation'],record.authorization_digest)
        finally:a.close();b.close()
    def kill(self,launch):
        if launch['launch_id'] in self.children:self.children[launch['launch_id']]['alive']=False
    def empty(self,launch):return self.cleanup_known and not self.children.get(launch['launch_id'],{}).get('alive',False)
    def finish(self,launch):
        if not self.empty(launch):raise AuthorityError('Uncertain synthetic cleanup.')
        self.children.pop(launch['launch_id'],None)
        return 0
    def exited(self,launch):return launch['launch_id'] in self.children and not self.children[launch['launch_id']]['alive']
    def service_deadlines(self,*,now,elapsed):
        for key,deadline in tuple(self.armed.items()):
            if deadline.expired(now=now,elapsed=elapsed):self.kill({'launch_id':key})
    def output_evidence(self,launch):return {s:dict(retained=0,truncated=False) for s in ('stdout','stderr')}


class CompositionIO(ir.KernelIO):
    """Only test paths/kernel observations are substituted, not authority or wire code."""
    def __init__(self,test,component):self.test,self.component=test,component;self.notifications=[]
    def now(self):return self.test.elapsed
    def wall(self):return self.test.now
    def identity(self):return PeerIdentity(0 if self.component=='supervisor' else 3000,
        0 if self.component=='supervisor' else 3000,100 if self.component=='supervisor' else 101)
    def process(self,pid):
        if pid==os.getpid():pid=100 if self.component=='supervisor' else 101
        return ProcessIdentity(fixtures.U,pid,{100:10,101:11,102:12,103:13,42000:123,42002:125}[pid])
    def read(self,path):return copy.deepcopy(self.test.documents[path])
    def verify_code(self,files):
        from types import SimpleNamespace
        return SimpleNamespace(files=files)
    def capabilities(self):return ()
    def notifier(self):return self.notifications.append
    def open_registry(self,path):
        from tools.agent_control.registry import Registry
        return Registry(Path(self.test.temp.name)/'state.sqlite3')
    def listener(self,name,enrollment):
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        path=str(Path(self.test.temp.name)/(name+'.sock'))
        sock.bind(path);sock.listen(1)
        def peer(_):return PeerIdentity(enrollment.uid,enrollment.gid,enrollment.process.pid)
        return UnixTransport(sock,enrollment,process_reader=self.process,peer_reader=peer)
    def connect(self,enrollment,handshake):
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        sock.settimeout(1);sock.connect(str(Path(self.test.temp.name)/'supervisor.sock'))
        return UnixRPCClient(sock,enrollment,handshake,process_reader=self.process,
            peer_reader=lambda _:PeerIdentity(0,0,100))
    def backend(self,artifacts,boot_id):
        self.test.kernel=KernelEffects(self,artifacts.files)
        return self.test.kernel
    def inspector(self,roots):
        from tools.agent_control.filesystem_evidence import FilesystemInspector
        local=[replace(r,host_root=str(self.test.root_path)) for r in roots]
        return FilesystemInspector(tuple(local),storage_probe=lambda fd,p:p.data())


class FactoryCompositionTests(unittest.TestCase):
    def setUp(self):
        from tools.agent_control.confinement import ConfinementProfile,TaskRoot
        from tools.agent_control.filesystem_evidence import RootMapping,Export,StoragePolicy,mount_id
        # Reuse durable M1/M2 data fixtures, changing only candidate UID/profile facts.
        real_worker=WorkerIdentity
        original_blank=fixtures.blank
        def blank(name):
            result=original_blank(name)
            if name=='ExecutionGrant':result['can_read']=[dict(kind='FILE',path='frontend/example.ts')]
            return result
        with patch.object(fixtures,'blank',side_effect=blank),patch.object(fixtures,'WorkerIdentity',side_effect=lambda a,r,n,u,g:real_worker(a,r,n,3002,3002)),\
             patch.object(fixtures,'ConfinementProfile',side_effect=lambda:ConfinementProfile(readable_paths=('frontend/example.ts',))):
            fixtures.RuntimeTests.setUp(self)
        self.supervisor.stop(self.launch_id,'CANCELLED')
        self.root_path=Path(self.temp.name)/'worker';(self.root_path/'frontend').mkdir(parents=True)
        (self.root_path/'frontend/example.ts').write_text('synthetic source')
        # Kernel-only UID observation substitution; no account/chown is performed.
        self.original_identity=TaskRoot._identity
        observe=lambda v:(v.st_dev,v.st_ino,3002,3002)
        self.identity_patch=patch.object(TaskRoot,'_identity',staticmethod(observe));self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)
        fd=os.open(self.root_path,os.O_RDONLY|os.O_DIRECTORY)
        try:storage=StoragePolicy(mount_id(fd))
        finally:os.close(fd)
        mapping=RootMapping(uid(),'/srv/bonup-agent-work/bonup-fe01/workspace',observe(self.root_path.stat()),1,
            (Export(uid(),'frontend/example.ts',observe((self.root_path/'frontend/example.ts').stat()),'FILE',False),),self.profile,storage)
        def peer(endpoint,uid_,pid,gen):return dict(endpoint=endpoint,uid=uid_,gid=uid_,pid=pid,start_ticks=pid-90,
            boot_id=fixtures.U,generation=gen,enrollment_id=uid())
        cg,sg=uid(),uid()
        controller_peer=peer('controller',3000,101,cg);supervisor_peer=peer('supervisor',0,100,sg)
        founder=peer('founder',1000,102,uid());proposal=peer('proposal',1000,103,uid())
        def service(component,generation,p):return dict(version=1,component=component,approved=True,
            generation=generation,boot_id=fixtures.U,peer=p,
            registry_path='/var/lib/bonup-agent-control/control.sqlite3' if component=='controller' else None)
        plan_id=uid()
        controller=dict(version=1,service=service('controller',cg,supervisor_peer),
            handshake={k:controller_peer[k] for k in ('endpoint','generation','enrollment_id')},
            founder=founder,proposal=proposal,executions=[dict(execution_id=self.execution_id,plan_id=plan_id,
                filesystem=mapping.expectation().policy,grant_path='/synthetic/work')])
        root=dict(logical_id=mapping.logical_id,host_root=mapping.host_root,identity=list(mapping.object_identity),
            generation=1,exports=[e.data() for e in mapping.exports],profile=asdict(self.profile),storage=storage.data(),
            repository_id=None,repository_identity=None)
        root=json.loads(json.dumps(root))
        record=asdict(replace(self.record,payload_json=canonical_json({'command_id':'true'})));record['operation']=self.record.operation.value;record['worker']['role']=self.worker.role.value
        record=json.loads(json.dumps(record))
        supervisor=dict(version=1,service=service('supervisor',sg,controller_peer),roots=[root],plans=[
            dict(plan_id=plan_id,execution_id=self.execution_id,record=record,root_id=mapping.logical_id,
                 profile_id=self.profile_id,anchor=dict(boot_id=fixtures.U,pid=100,start_ticks=10))])
        m,i=manifest_for(controller,supervisor)
        self.documents={ic.MANIFEST:m,ic.IDENTITIES:i,ir.CONTROLLER:controller,ir.SUPERVISOR:supervisor}
        self.sio,self.cio=CompositionIO(self,'supervisor'),CompositionIO(self,'controller')
        self.sa=ir.build_installed_supervisor_adapters(_io=self.sio)
        self.ca=ir.build_installed_controller_adapters(_io=self.cio)
        self.server_errors=[];self.halt=threading.Event()
        from tools.agent_control import supervisor_entry,controller_entry
        self.loop=supervisor_entry.start(adapters=self.sa)
        def serve():
            try:
                while not self.halt.is_set():
                    self.loop.step();self.halt.wait(.001)
            except BaseException as error:self.server_errors.append(error)
        self.thread=threading.Thread(target=serve);self.thread.start()
        self.addCleanup(self.close_server)
        self.service=controller_entry.start(adapters=self.ca)
        self.expected_disconnect=False
        self.addCleanup(self.close_service)
        self.driver=self.ca.driver
        self.model=dict(version=1,request_id=uid(),execution_id=self.execution_id,operation='RUN_TEST',arguments=dict(command_id='true'))
    def close_service(self):
        try:self.service.close()
        except AuthorityError:
            if not self.expected_disconnect:raise
            self.assertTrue(self.ca.driver.client.stopped.is_set())
    def close_server(self):
        self.halt.set();self.thread.join(2)
        self.loop.shutdown()
    def observed(self,kind):
        e=getattr(self.driver,kind)
        return PeerIdentity(e.uid,e.gid,e.process.pid),e.process,dict(endpoint=e.endpoint,generation=e.generation,enrollment_id=e.enrollment_id)
    def propose(self):
        try:return self.driver.request('proposal',self.model,self.observed('proposal'))
        except BaseException:
            if self.server_errors:raise self.server_errors[-1]
            raise
    def test_full_production_factory_lifecycle(self):
        reply=self.propose();key=reply['launch_id']
        self.assertEqual(reply['state'],'RUNNING')
        self.assertEqual(self.kernel.releases,[key])
        self.assertIn('--ro-bind-fd',self.kernel.fixed[0].bwrap_argv)
        self.assertIn('/usr/lib/bonup-agent-control/gate_entry.py',self.kernel.fixed[0].bwrap_argv)
        self.assertTrue(self.kernel.gates[0].used)
        self.assertEqual(self.driver.controller.stop(key)['state'],'TERMINAL')
        self.assertFalse(self.sa.driver.endpoint.inspector.handles)
        self.assertFalse(hasattr(self.sa.driver.endpoint,'db'))
        self.assertIn('READY=1',self.sio.notifications);self.assertIn('READY=1',self.cio.notifications)
        self.assertFalse(self.server_errors)

    def routing_events(self):
        return [json.loads(row[0]) for row in self.driver.controller.runtime.db.execute(
            'SELECT payload FROM audit_events ORDER BY sequence') if '"routing"' in row[0]]

    def test_production_audit_lifecycle_is_correlated_and_published(self):
        reply=self.propose();self.driver.controller.stop(reply['launch_id'])
        events=self.routing_events()
        self.assertEqual([e['event_type'] for e in events],['MODEL_PROPOSAL_RECEIVED',
            'OPERATION_AUTHORIZED','CONFINEMENT_SETUP_STARTED','WORKER_STARTED','WORKER_EXITED'])
        self.assertTrue(all(e['actor']=={'component':'CONTROLLER'} for e in events))
        self.assertTrue(all(e['routing']['request_id']==self.model['request_id'] for e in events))
        self.assertTrue(all(e['execution_id']==self.execution_id for e in events))
        self.assertTrue(all(e['routing']['launch_id']==reply['launch_id'] for e in events[1:]))
        registry=self.driver.controller.runtime.registry
        self.assertNotEqual(registry.verify(check_history=False)['status'],'BLOCKED')
        for event in events:
            self.assertIsNotNone(registry.db.execute('SELECT 1 FROM outbox WHERE operation_id=?',
                (event['operation_id'],)).fetchone())

    def test_malformed_proposal_audited_before_registration_without_secret(self):
        self.model['founder']='synthetic-secret-must-not-be-logged'
        with self.assertRaises(ValidationError):self.propose()
        events=self.routing_events()
        self.assertEqual([e['event_type'] for e in events],['MODEL_PROPOSAL_RECEIVED','OPERATION_DENIED'])
        self.assertNotIn('synthetic-secret',json.dumps(events))
        self.assertTrue(all(e['routing']['launch_id'] is None for e in events))
        self.assertFalse(self.kernel.releases)

    def test_wrong_execution_audited_before_registration(self):
        self.model['execution_id']=uid()
        with self.assertRaises(AuthorityError):self.propose()
        events=self.routing_events()
        self.assertEqual(events[-1]['event_type'],'OPERATION_DENIED')
        self.assertEqual(events[-1]['reason_code'],'IDENTITY')

    def test_unknown_operation_audited(self):
        self.model['operation']='SUDO'
        with self.assertRaises(ValidationError):self.propose()
        self.assertEqual(self.routing_events()[-1]['event_type'],'OPERATION_DENIED')

    def test_production_setup_failure_audited(self):
        self.expected_disconnect=True;self.kernel.fail_prepare=True
        with self.assertRaises((AuthorityError,OSError)):self.propose()
        kinds=[e['event_type'] for e in self.routing_events()]
        self.assertIn('CONFINEMENT_SETUP_STARTED',kinds)
        self.assertIn('CONFINEMENT_SETUP_FAILED',kinds)
        self.assertNotIn('WORKER_STARTED',kinds)

    def test_gate_denial_never_audits_worker_started(self):
        self.expected_disconnect=True;self.kernel.eof=True
        with self.assertRaises((AuthorityError,OSError)):self.propose()
        kinds=[e['event_type'] for e in self.routing_events()]
        self.assertIn('OPERATION_DENIED',kinds)
        self.assertNotIn('WORKER_STARTED',kinds)

    def test_audit_failure_before_authorization_never_prepares(self):
        with patch.object(self.driver.controller.runtime.registry,'routing_event',side_effect=OSError('audit unavailable')):
            with self.assertRaises(OSError):self.propose()
        self.assertFalse(self.kernel.releases)
        self.assertFalse(self.kernel.children)

    def test_normal_exit_emits_worker_exited_after_cleanup(self):
        reply=self.propose();key=reply['launch_id']
        self.kernel.children[key]['alive']=False
        self.driver.controller.tick()
        self.assertEqual(self.driver.controller.runtime.launch(key)['state'],'TERMINAL')
        self.assertEqual(self.routing_events()[-1]['event_type'],'WORKER_EXITED')

    def test_authority_denial_reason_is_preserved(self):
        runtime=self.driver.controller.runtime
        with runtime.transaction('synthetic-fence-advance'):
            runtime.db.execute('UPDATE execution_runtime SET fencing_epoch=fencing_epoch+1, '
                'authority_revision=authority_revision+1 WHERE execution_id=?',(self.execution_id,))
        with self.assertRaises(AuthorityError):self.propose()
        self.assertEqual(self.routing_events()[-1]['reason_code'],'FENCING')
        self.assertFalse(self.kernel.releases)
    def test_wrong_model_peer_denied(self):
        observed=list(self.observed('proposal'));observed[0]=PeerIdentity(0,0,103)
        with self.assertRaises(AuthorityError):self.driver.request('proposal',self.model,tuple(observed))
        self.assertFalse(self.kernel.releases)
    def test_pinned_prepare_failure_never_releases(self):
        self.expected_disconnect=True
        self.kernel.fail_prepare=True
        with self.assertRaises((AuthorityError,OSError)):self.propose()
        self.assertFalse(self.kernel.releases)
    def test_gate_eof_never_releases(self):
        self.expected_disconnect=True
        self.kernel.eof=True
        with self.assertRaises((AuthorityError,OSError)):self.propose()
        self.assertFalse(self.kernel.releases)
    def test_cleanup_uncertainty_retains_reservation(self):
        reply=self.propose();self.kernel.cleanup_known=False
        self.assertEqual(self.driver.controller.stop(reply['launch_id'])['state'],'STOPPING')
        self.kernel.cleanup_known=True
        self.assertEqual(self.driver.controller.stop(reply['launch_id'])['state'],'TERMINAL')
    def test_replay_does_not_reexecute(self):
        reply=self.propose()
        with self.assertRaises(AuthorityError):self.propose()
        self.assertEqual(self.kernel.releases,[reply['launch_id']])
        self.driver.controller.stop(reply['launch_id'])
    def test_deadline_lane_stops_during_no_requests(self):
        reply=self.propose();self.elapsed=31
        self.sa.driver.deadline.step()
        self.assertFalse(self.kernel.children[reply['launch_id']]['alive'])
        self.elapsed=0 # Test transport clock is separate; authority remains stopped.
        self.assertEqual(self.driver.controller.stop(reply['launch_id'])['state'],'TERMINAL')

    def prepare_only(self):
        controller=self.driver.controller
        enrollment=self.driver.enrollments[self.execution_id]
        key=controller.register(canonical_json(self.model).encode(),enrollment)
        controller.prepare(key)
        return key

    def test_authority_replacement_after_prepared(self):
        key=self.prepare_only()
        runtime=self.driver.controller.runtime
        runtime.revoke(self.execution_id,runtime.runtime(self.execution_id)['authority_revision'],context=fixtures.FOUNDER)
        with self.assertRaises(AuthorityError):self.driver.controller.release(key)
        self.assertFalse(self.kernel.releases)
        self.assertEqual(runtime.launch(key)['state'],'TERMINAL')

    def test_supervisor_disconnect_leaves_uncertain_durable_state(self):
        reply=self.propose();self.expected_disconnect=True
        self.ca.driver.client.close()
        with self.assertRaises(AuthorityError):self.driver.controller.stop(reply['launch_id'])
        self.assertEqual(self.driver.controller.runtime.launch(reply['launch_id'])['state'],'STOPPING')

    def test_controller_disconnect_terminates_without_replay(self):
        reply=self.propose()
        self.driver.disconnect()
        self.assertEqual(self.driver.controller.runtime.launch(reply['launch_id'])['state'],'TERMINAL')
        self.assertFalse(self.kernel.children)
        self.assertEqual(self.kernel.releases,[reply['launch_id']])

    def test_final_database_failure_prevents_release(self):
        key=self.prepare_only();runtime=self.driver.controller.runtime
        transition=runtime.transition
        def fail(launch,revision,target,**kw):
            if target=='RELEASE_PENDING':raise AuthorityError('Injected database failure.')
            return transition(launch,revision,target,**kw)
        with patch.object(runtime,'transition',side_effect=fail):
            with self.assertRaises(AuthorityError):self.driver.controller.release(key)
        self.assertFalse(self.kernel.releases)

    def test_missing_supervisor_socket_is_not_tcp_fallback(self):
        io=ir.KernelIO()
        with patch('tools.agent_control.installed_transport.socket.socket') as make:
            make.return_value.connect.side_effect=FileNotFoundError('synthetic missing endpoint')
            with self.assertRaises(FileNotFoundError):io.connect(None,{})
            self.assertEqual(make.call_args.args[0],socket.AF_UNIX)
            make.return_value.close.assert_called_once()

    def add_lease(self):
        from tools.agent_control.records import ExecutionGrant
        from test_boundary_hardening import resource
        runtime=self.driver.controller.runtime;registry=runtime.registry
        original=registry.load;data=original('ExecutionGrant',self.execution_id).to_dict()
        key=uid();data['reserved_resources']=[key];grant=ExecutionGrant(data)
        patcher=patch.object(registry,'load',side_effect=lambda kind,k:grant if kind=='ExecutionGrant' and k==self.execution_id else original(kind,k))
        patcher.start();self.addCleanup(patcher.stop)
        from tools.agent_control.records import Task
        original_task=registry.get_task
        task=original_task(grant['task_id']).to_dict();task['resource_reservations']=[key]
        task=Task(task)
        task_patch=patch.object(registry,'get_task',side_effect=lambda tid:task if tid==grant['task_id'] else original_task(tid))
        task_patch.start();self.addCleanup(task_patch.stop)
        runtime.acquire_lease(self.execution_id,key,1,(self.now+timedelta(seconds=1)).isoformat(),self.now,
            reservation=resource(self.execution_id,key,grant['task_id']))
        return key

    def test_required_lease_expiry_after_prepared(self):
        self.add_lease();key=self.prepare_only()
        self.assertEqual(self.kernel.armed[key].elapsed_deadline,1)
        self.elapsed=1
        with self.assertRaises(AuthorityError):self.driver.controller.release(key)
        self.assertFalse(self.kernel.releases)
        self.assertEqual(self.driver.controller.runtime.launch(key)['state'],'TERMINAL')

    def test_required_lease_revocation_running(self):
        lease=self.add_lease();reply=self.propose();key=reply['launch_id']
        runtime=self.driver.controller.runtime
        runtime.revoke_lease(lease,1,context=fixtures.FOUNDER)
        self.driver.controller.tick()
        self.assertEqual(runtime.launch(key)['state'],'TERMINAL')
        self.assertFalse(self.kernel.children)

    def test_founder_cancel_serviced_while_prepare_waits(self):
        controller=self.driver.controller
        key=controller.register(canonical_json(self.model).encode(),self.driver.enrollments[self.execution_id])
        allowed=threading.Event()
        def blocked_prepare():
            if not allowed.wait(2):raise AuthorityError('Test synchronization timeout.')
        self.kernel.before_prepare=blocked_prepare
        client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(client.close)
        client.settimeout(2);client.connect(str(Path(self.temp.name)/'founder.sock'))
        e=self.driver.founder
        client.sendall(packet(dict(endpoint=e.endpoint,generation=e.generation,enrollment_id=e.enrollment_id)))
        errors=[]
        def sender():
            try:
                reader=Packet(ir.time.monotonic(),timeout=2)
                while reader.feed(client.recv(reader.wanted),ir.time.monotonic()) is None:pass
                client.sendall(packet(dict(version=1,request_id=uid(),action='CANCEL',execution_id=self.execution_id,
                    revision=0,launch_id=key)))
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=sender);thread.start()
        original=self.driver.client.maintenance
        def maintenance():
            original()
            if controller.runtime.launch(key)['state']=='STOPPING':allowed.set()
        self.driver.client.maintenance=maintenance
        try:
            with self.assertRaises(AuthorityError):controller.prepare(key)
        finally:
            allowed.set();thread.join(2)
            self.driver.client.maintenance=original
        self.assertFalse(errors)
        self.assertEqual(controller.runtime.launch(key)['state'],'TERMINAL')
        self.assertFalse(self.kernel.releases)
