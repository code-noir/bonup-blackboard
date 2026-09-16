"""Fixed installed adapter factories. No daemon or privileged operation on import.

KernelIO is the explicit syscall boundary used by disposable integration tests.
Installed entrypoints construct KernelIO themselves; JSON/environment cannot
select a Python implementation. Real cgroup/UID/bwrap operations require the
separately approved installed host and remain HOST_TEST_REQUIRED.
"""
from dataclasses import fields
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4
import signal
import socket
import stat
import threading
import time

from .identity import PeerIdentity, ProcessIdentity
from .installed_config import (PREFIX, MANIFEST, IDENTITIES, read_installed,
    validate_activation, parse_record)
from .installed_transport import (UnixTransport, UnixRPCClient, DuplexClient,
    SystemdNotifier, packet, local_socket)
from .protocol import bounded_json, uuid_value
from .serialization import canonical_json, digest
from .service_runtime import PeerEnrollment, keys
from .types import AuthorityError, ValidationError

CONTROLLER = '/etc/bonup-agent-control/controller.json'
SUPERVISOR = '/etc/bonup-agent-control/supervisor.json'
CGROUP = '/sys/fs/cgroup/system.slice/bonup-agent-supervisor.service'


def utc_now(): return datetime.now(timezone.utc)
def boottime(): return time.clock_gettime(time.CLOCK_BOOTTIME)


def process(data):
    keys(data, ('boot_id','pid','start_ticks'))
    uuid_value(data['boot_id'])
    if any(type(data[k]) is not int for k in ('pid','start_ticks')) or data['pid']<=0 or data['start_ticks']<0:
        raise ValidationError('Invalid installed process enrollment.')
    return ProcessIdentity(**data)


def client_peer(data, endpoint, boot_id):
    keys(data, ('endpoint','uid','gid','pid','start_ticks','boot_id','generation','enrollment_id'))
    if (data['endpoint']!=endpoint or data['boot_id']!=boot_id or
            any(type(data[k]) is not int or data[k]<=0 for k in ('uid','gid')) or
            data['uid'] in range(3000,3005)):
        raise AuthorityError('Invalid founder/model endpoint enrollment.')
    proc=process({k:data[k] for k in ('boot_id','pid','start_ticks')})
    uuid_value(data['generation']);uuid_value(data['enrollment_id'])
    return PeerEnrollment(endpoint,data['uid'],data['gid'],proc,data['generation'],data['enrollment_id'])


def profile(data):
    from .confinement import ConfinementProfile
    keys(data, [f.name for f in fields(ConfinementProfile)])
    row=dict(data)
    for key in ('readonly_roots','readable_paths','writable_paths'):
        if type(row[key]) is not list: raise ValidationError('Profile arrays required.')
        row[key]=tuple(row[key])
    return ConfinementProfile(**row)


def mappings(data, *, generation=1):
    from .filesystem_evidence import RootMapping, Export, StoragePolicy
    if type(data) is not list or len(data)>4: raise ValidationError('Bounded root catalog required.')
    result=[]
    for row in data:
        keys(row, ('logical_id','host_root','identity','generation','exports','profile','storage',
                   'repository_id','repository_identity'))
        if not row['host_root'].startswith('/srv/bonup-agent-work/'):
            raise AuthorityError('Installed root outside worker storage.')
        if type(row['generation']) is not int or row['generation']!=generation: raise AuthorityError('Stale provisioning generation.')
        exports=[]
        for export in row['exports']:
            keys(export,('logical_id','relative','identity','kind','writable'))
            exports.append(Export(export['logical_id'],export['relative'],tuple(export['identity']),
                                  export['kind'],export['writable']))
        result.append(RootMapping(row['logical_id'],row['host_root'],tuple(row['identity']),row['generation'],
            tuple(exports),profile(row['profile']),StoragePolicy(**row['storage']),row['repository_id'],
            None if row['repository_identity'] is None else tuple(row['repository_identity'])))
    return tuple(result)


class KernelIO:
    """Fixed production IO; tests may override syscalls in explicitly constructed objects."""
    now = staticmethod(boottime)
    wall = staticmethod(utc_now)
    process = staticmethod(ProcessIdentity.read)
    identity = staticmethod(PeerIdentity.current)
    @staticmethod
    def peer(sock):
        from .installed_transport import SenderSocket
        if isinstance(sock, SenderSocket):
            if sock.sender is None:
                raise AuthorityError('Actual sender not observed.')
            return sock.sender
        return PeerIdentity.from_socket(sock)
    read = staticmethod(read_installed)

    def founder_root(self):
        from .founder_crypto import load_founder_root
        return load_founder_root()

    def verify_crypto(self):
        from .founder_crypto import OpenSSLVerifier
        OpenSSLVerifier().preflight()

    def witness(self, component):
        from .interruption import Witness
        witness=Witness(component)
        witness.preflight()
        return witness

    def verify_code(self, files):
        from .supervisor_linux import InstalledArtifacts
        if Path(__file__).resolve()!=Path(PREFIX+'/tools/agent_control/installed_runtime.py'):
            raise AuthorityError('Installed runtime cannot execute from a checkout.')
        return InstalledArtifacts(files)

    def open_registry(self, path):
        from .controller_entry import open_existing_registry
        return open_existing_registry(path)

    def capabilities(self):
        data=Path('/proc/self/status').read_text()
        values=dict(line.split(':',1) for line in data.splitlines() if ':' in line)
        return tuple(k for k in ('CapEff','CapPrm','CapInh','CapAmb') if int(values[k].strip(),16))

    def verify_supervisor_capabilities(self):
        # SETUID(7), SETGID(6), KILL(5), DAC_READ_SEARCH(2); never SYS_ADMIN/OVERRIDE.
        data=Path('/proc/self/status').read_text()
        values=dict(line.split(':',1) for line in data.splitlines() if ':' in line)
        expected=sum(1<<n for n in (2,5,6,7))
        if (os.geteuid()!=0 or any(int(values[k].strip(),16)!=expected for k in ('CapEff','CapPrm','CapBnd')) or
                any(int(values[k].strip(),16) for k in ('CapInh','CapAmb')) or values['NoNewPrivs'].strip()!='1'):
            raise AuthorityError('Installed supervisor capability bounds required.')

    def notifier(self): return SystemdNotifier.installed()

    def _listener_socket(self, name, gid):
        """Only systemd-created, verified AF_UNIX listener descriptors are adopted.

        No creation/chmod/chown/unlink here. Socket units must grant exact access;
        root supervisor 0600 would make the controller unable to connect.
        """
        policy={
            'founder':('/run/bonup-agent-control/founder.sock',3000,gid,0o660),
            'proposals':('/run/bonup-agent-control/proposals.sock',3000,gid,0o660),
            'supervisor':('/run/bonup-agent-supervisor/control.sock',0,3000,0o660)}
        if name not in policy: raise AuthorityError('Unknown installed socket.')
        expected_names=['supervisor'] if os.geteuid()==0 else ['founder','proposals']
        if (os.environ.get('LISTEN_PID')!=str(os.getpid()) or
                sorted(os.environ.get('LISTEN_FDNAMES','').split(':'))!=sorted(expected_names) or
                os.environ.get('LISTEN_FDS')!=str(len(expected_names)) or name not in expected_names):
            raise AuthorityError('Exact systemd socket activation required.')
        fd=3+os.environ['LISTEN_FDNAMES'].split(':').index(name)
        sock=local_socket(socket.socket(fileno=os.dup(fd)))
        try:
            path,uid,gid,mode=policy[name]
            info=os.stat(path,follow_symlinks=False)
            if (sock.getsockname()!=path or not stat.S_ISSOCK(info.st_mode) or
                    (info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode))!=(uid,gid,mode)):
                raise AuthorityError('Installed listener identity/mode mismatch.')
            for ancestor in Path(path).parents:
                info=ancestor.lstat()
                if stat.S_ISLNK(info.st_mode) or info.st_mode&0o022 or info.st_uid not in (0,3000):
                    raise AuthorityError('Untrusted listener ancestor.')
            if sock.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)!=1:
                raise AuthorityError('Activated descriptor is not listening.')
            os.set_inheritable(fd,False)
            return sock
        except BaseException:
            sock.close();raise

    def listener(self, name, enrollment):
        return UnixTransport(self._listener_socket(name, enrollment.gid), enrollment,
                             now=self.now, process_reader=self.process)

    def observe_service(self, peer, installation):
        from .operational_enrollment import Observation
        process = self.process(peer.pid)
        lines = Path('/proc/'+str(peer.pid)+'/cgroup').read_text().splitlines()
        expected = '/system.slice/' + installation.service
        paths = [line[3:] for line in lines if line.startswith('0::')]
        if len(paths) != 1 or paths[0] not in (expected, expected+'/supervisor'):
            raise AuthorityError('Peer is outside the enrolled systemd service.')
        process.verify(self.process)
        return Observation(peer, process, installation.service)

    def enroll(self, local, remote):
        from .installed_transport import OperationalChannel, SenderSocket
        import socket
        listener = None
        sock = None
        try:
            if local.component == 'supervisor':
                listener = self._listener_socket('supervisor', 3000)
                listener.settimeout(1)
                sock, _ = listener.accept()
            else:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
                sock.settimeout(1)
                sock.connect('/run/bonup-agent-supervisor/control.sock')
            sock = SenderSocket(sock, remote.uid, remote.gid).authenticate_sender()
            def observe():
                import select
                poll = select.poll()
                mask = select.POLLHUP | select.POLLERR | select.POLLNVAL | select.POLLRDHUP
                poll.register(sock, mask)
                if poll.poll(0):
                    raise AuthorityError('Operational channel disconnected.')
                return self.observe_service(self.peer(sock), remote)
            channel = OperationalChannel(sock, local, remote,
                local_observe=lambda: self.observe_service(self.identity(), local),
                observe=observe, now=self.now)
            channel.listener = listener
            channel.enroll()
            return channel
        except BaseException:
            if sock is not None: sock.close()
            if listener is not None: listener.close()
            raise

    def connect(self, enrollment, handshake):
        return UnixRPCClient.connect_installed('/run/bonup-agent-supervisor/control.sock',enrollment,handshake)

    def inspector(self, roots):
        from .filesystem_evidence import FilesystemInspector
        return FilesystemInspector(roots)

    def backend(self, artifacts, boot_id):
        from .supervisor_linux import LinuxProcessBackend, CgroupV2
        self.verify_supervisor_capabilities()
        fd=os.open(CGROUP,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try: cgroups=CgroupV2(fd)
        finally: os.close(fd)
        try: return LinuxProcessBackend(artifacts,cgroups,plans={},boot_id=boot_id)
        except BaseException:
            cgroups.close();raise


class FixedWork:
    """Single bounded trusted job. Payload execution is never a Python callback."""
    def __init__(self, handler):
        from concurrent.futures import ThreadPoolExecutor
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='agent-prepare')
        self.handler,self.future=handler,None
        self.closed=False

    def submit(self, request):
        if self.closed or self.future is not None: raise AuthorityError('Work queue closed/full.')
        self.future=self.pool.submit(self.handler,request)

    def take_result(self):
        if self.future is None or not self.future.done(): return None
        future,self.future=self.future,None
        return future.result()

    def cancel(self):
        self.closed=True
        if self.future is not None: self.future.cancel()
        self.pool.shutdown(wait=False,cancel_futures=True)


class DeadlineService:
    """Independent kernel deadline lane; a blocking PREPARE cannot renew authority."""
    def __init__(self, backend, io):
        self.backend,self.io=backend,io
        self.stop=threading.Event()
        self.failure=None
        self.thread=None

    def step(self):
        self.backend.service_deadlines(now=self.io.wall(),elapsed=self.io.now())

    def start(self):
        self.step()
        self.thread=threading.Thread(target=self.run,name='agent-deadlines',daemon=True)
        self.thread.start()

    def run(self):
        try:
            while not self.stop.wait(.02): self.step()
        except BaseException as error:
            self.failure=error
            # Fail-stop is observable by the event loop/watchdog. No READY after it.
            self.stop.set()

    def check(self):
        if self.failure is not None: raise AuthorityError('Deadline servicing failed.') from self.failure

    def close(self):
        self.stop.set()
        if self.thread is not None: self.thread.join(1)


class InstalledBase:
    def __init__(self, component, io):
        self.component,self.io=component,io
        self.shutdown=threading.Event()
        self.config=None
        self.driver=None
        self.transport=None
        self.notify_adapter=None

    def identity(self): return self.io.identity()
    def boot_id(self): return self.io.process(os.getpid()).boot_id
    def capabilities(self): return self.io.capabilities()
    def now(self): return self.io.now()
    def wait(self, seconds): self.shutdown.wait(min(seconds,.05))
    def shutdown_requested(self): return self.shutdown.is_set()
    def notify(self, value):
        if self.notify_adapter is None: raise AuthorityError('Notifier not initialized.')
        self.notify_adapter(value)

    def load_config(self,path):
        if path != (CONTROLLER if self.component=='controller' else SUPERVISOR):
            raise AuthorityError('Fixed installed configuration required.')
        manifest=self.io.read(MANIFEST)
        identities=self.io.read(IDENTITIES)
        data=self.io.read(path)
        if type(data) is dict and type(data.get('version')) is int and data['version']==3:
            return self.load_successor(data,manifest,identities)
        modern = manifest.get('version') in (3,4)
        # v2 exists solely for the prior offline fixtures. Installed startup cannot
        # pre-enroll future processes via that superseded configuration contract.
        if type(self.io) is KernelIO and manifest.get('version') != 4:
            raise AuthorityError('Complete installation bundle and per-start enrollment required.')
        required=(('version','service','founder_uid','founder','proposal','executions') if modern else
                  ('version','service','handshake','founder','proposal','executions')) if self.component=='controller' else (
            'version','service','roots','plans')
        keys(data,required)
        if type(data['version']) is not int or data['version'] != (2 if modern else 1):
            raise ValidationError('Unsupported component configuration.')
        evidence = {}
        if manifest.get('version') == 4:
            from .installation_bundle import validate_manifest
            validate_manifest(manifest)
            if not manifest['approved'] or not (manifest['activation'] or manifest['integration_services_approved']):
                raise AuthorityError('No installation/service approval.')
            evidence['receipt'] = self.io.read('/etc/bonup-agent-control/installation-receipt.json')
            if manifest['activation']:
                evidence['host_tests'] = self.io.read('/etc/bonup-agent-control/host-tests.json')
        self.manifest_digest=validate_activation(manifest,identities,data,component=self.component,**evidence)
        self.artifacts=self.io.verify_code(manifest['files'])
        from .supervisor_linux import InstalledArtifacts
        if type(self.artifacts) is InstalledArtifacts:
            self.artifacts.bind_installation(manifest['bundle_digest'],manifest['provisioning_generation'])
        self.config=data
        self.notify_adapter=self.io.notifier()
        if not modern:
            service=dict(data['service'])
            keys(service,('version','component','approved','generation','boot_id','peer','registry_path'))
            service['manifest_digest']=self.manifest_digest
            return service
        from .operational_enrollment import installation_pair
        from dataclasses import asdict
        local, remote = installation_pair(data, manifest, self.component)
        # Existing registry validation precedes controller enrollment. No missing
        # registry is initialized. The normal startup retains its own DB handle.
        if self.component == 'controller':
            from .controller_entry import validate_registry
            registry = self.io.open_registry('/var/lib/bonup-agent-control/control.sqlite3')
            try: validate_registry(registry)
            finally: registry.close()
            if self.io.capabilities() != ():
                raise AuthorityError('Controller capabilities prohibited.')
            # Human/model contexts are separate authority, never auto-enrolled by
            # this service handshake. Initial installed intake is explicitly shut.
            if (type(data['founder_uid']) is not int or data['founder_uid'] <= 0 or data['founder_uid'] in range(3000,3005)):
                raise AuthorityError('Explicit separate founder installation UID required.')
            if data['founder'] is not None or data['proposal'] is not None or data['executions'] != []:
                raise AuthorityError('Client/task enrollment is separate from service enrollment.')
        elif data['plans'] != [] or data['roots'] != []:
            raise AuthorityError('Per-execution catalogs require separate operational enrollment.')
        self.operational_channel = self.io.enroll(local, remote)
        session = self.operational_channel.session
        self.admission = session.admission
        peer = session.peer_enrollment()
        service = dict(version=1, component=self.component, approved=True,
            generation=session.generation, boot_id=session.boot_id,
            manifest_digest=self.manifest_digest,
            registry_path='/var/lib/bonup-agent-control/control.sqlite3' if self.component=='controller' else None,
            peer=dict(endpoint=peer.endpoint, uid=peer.uid, gid=peer.gid, **asdict(peer.process),
                      generation=peer.generation, enrollment_id=peer.enrollment_id))
        return service

    def load_successor(self, data, manifest, identities):
        from . import successor_config as successor
        from .authority_installation import approval_projection
        from .host_test_catalog import ROOT_ID, PROFILE
        from .operational_enrollment import installation_pair
        from dataclasses import asdict
        attestation=self.io.read(successor.ATTESTATION)
        root=self.io.founder_root()
        receipt=successor.validate(data,attestation,identities,
            self.io.read(successor.RECEIPT),root,component=self.component)
        candidate=self.io.read('/etc/bonup-agent-control/installation-candidate.json')
        approved=self.io.read('/etc/bonup-agent-control/installation-approved.json')
        if manifest != approved:
            raise AuthorityError('Successor policy cannot be installed over a different generation manifest.')
        approval_projection(canonical_json(candidate).encode(),canonical_json(approved).encode(),receipt.binding)
        for field in ('files','configuration_digests','identity_map_digest','resource_digest','authority_digest'):
            if approved.get(field) != attestation[field]:
                raise AuthorityError('Runtime attestation changes approved installation policy.')
        if approved.get('source_commit') != receipt.binding.source_commit:
            raise AuthorityError('Runtime attestation source mismatch.')
        self.artifacts=self.io.verify_code(attestation['files'])
        from .supervisor_linux import InstalledArtifacts
        if type(self.artifacts) is InstalledArtifacts:
            self.artifacts.bind_installation(receipt.binding.candidate_bundle_digest,2)
        self.io.verify_crypto()
        raw_roots=self.io.read('/etc/bonup-agent-control/host-test-roots.json')
        if digest(raw_roots) != attestation['filesystem_digest']:
            raise AuthorityError('Physical installation enrollment mismatch.')
        roots=mappings(raw_roots, generation=2)
        enabled=data['authority']['host_tests_enabled']
        if enabled:
            if (len(roots)!=1 or roots[0].host_root!='/srv/bonup-agent-work/bonup-fe01/workspace' or
                    roots[0].logical_id!=ROOT_ID or roots[0].profile!=PROFILE or
                    roots[0].object_identity[2:]!=(3002,3002) or roots[0].repository_id is not None or
                    len(roots[0].exports)!=1 or roots[0].exports[0].relative!='frontend/example.ts' or
                    roots[0].exports[0].writable):
                raise AuthorityError('Only the installed synthetic canary root is permitted.')
        elif roots:
            raise AuthorityError('Disabled host tests cannot enroll storage.')
        self.manifest_digest=digest(attestation)
        self.config=dict(data)
        if self.component=='controller':
            from .controller_entry import validate_registry
            registry=self.io.open_registry('/var/lib/bonup-agent-control/control.sqlite3')
            try: validate_registry(registry)
            finally: registry.close()
            if self.io.capabilities()!=():
                raise AuthorityError('Controller capabilities prohibited.')
            self.config['founder_policy']=dict(enabled=data['authority']['founder_enabled'],
                binding=receipt.binding.data(),root_digest=root.identity,receipt_digest=receipt.receipt_digest,
                activation=False,host_tests_enabled=enabled,
                filesystem=roots[0].expectation().policy if enabled else None)
        else:
            self.config['roots']=raw_roots
            self.config['host_test_catalog']=data['authority']['catalog_digest'] if enabled else None
            self.config['host_installation_digest']=digest(receipt.binding.data())
        self.notify_adapter=self.io.notifier()
        local,remote=installation_pair(data,attestation,self.component,generation=2)
        self.operational_channel=self.io.enroll(local,remote)
        session=self.operational_channel.session
        self.admission=session.admission
        peer=session.peer_enrollment()
        return dict(version=1,component=self.component,approved=True,generation=session.generation,
            boot_id=session.boot_id,manifest_digest=self.manifest_digest,
            registry_path='/var/lib/bonup-agent-control/control.sqlite3' if self.component=='controller' else None,
            peer=dict(endpoint=peer.endpoint,uid=peer.uid,gid=peer.gid,**asdict(peer.process),
                      generation=peer.generation,enrollment_id=peer.enrollment_id))

    def abort_startup(self):
        channel = getattr(self, 'operational_channel', None)
        if channel is not None:
            channel.close()
            if channel.listener is not None: channel.listener.close()

    def verify_manifest(self):
        if self.config is None: raise AuthorityError('Configuration not verified.')
        return self.manifest_digest

    def install_signals(self):
        for sig in (signal.SIGTERM,signal.SIGINT):
            signal.signal(sig,lambda *_: self.shutdown.set())


class InstalledSupervisorAdapters(InstalledBase):
    """Root-side composition; no registry opener, database argument or model client."""
    def __init__(self, io): super().__init__('supervisor',io)

    def compose_supervisor(self, config):
        from .composition import ApprovedPlan,SupervisorEndpoint
        from .filesystem_evidence import ExpectedFilesystem
        from .supervisor_entry import SupervisorDriver
        roots=mappings(self.config['roots'],generation=2 if self.config['version']==3 else 1)
        roots_by_id={r.logical_id:r for r in roots}
        if len(roots_by_id)!=len(roots):raise ValidationError('Duplicate installed root.')
        raw_plans=self.config['plans']
        if type(raw_plans) is not list or len(raw_plans)>4: raise ValidationError('Bounded plan catalog required.')
        plans=[]
        for row in raw_plans:
            keys(row,('plan_id','execution_id','record','root_id','profile_id','anchor'))
            root=roots_by_id[row['root_id']]
            anchor=process(row['anchor'])
            if anchor!=self.io.process(os.getpid()):raise AuthorityError('Stale supervisor anchor.')
            plans.append(ApprovedPlan(row['plan_id'],row['execution_id'],parse_record(row['record']),
                root.object_identity,row['profile_id'],anchor,filesystem=root.expectation()))
        host_only = self.config.get('host_test_catalog') is not None
        if host_only:
            from .host_test_catalog import CATALOG_DIGEST
            from .host_test_launch import supervisor_catalog
            if self.config['host_test_catalog'] != CATALOG_DIGEST or raw_plans != [] or len(roots) != 1:
                raise AuthorityError('Exact installed host-test catalog required.')
            plans = supervisor_catalog(roots[0], config.generation, self.io.process(os.getpid()))
        backend=self.io.backend(self.artifacts,config.boot_id)
        inspector=self.io.inspector(roots)
        endpoint=SupervisorEndpoint(tuple(plans),backend,generation=config.generation,boot_id=config.boot_id,
            now=self.io.wall,elapsed=self.io.now,inspector=inspector,
            admission=getattr(self, "admission", None), host_only=host_only,
            witness=self.io.witness('supervisor') if host_only else None,
            controller_process=config.peer.process if host_only else None,
            ordinary_admission=self.config['version']!=3,
            host_installation_digest=self.config.get('host_installation_digest'))
        deadline=DeadlineService(backend,self.io)
        driver=InstalledSupervisorDriver(endpoint,FixedWork(endpoint.handle),deadline)
        self.driver=driver
        return driver

    def listener(self, config):
        if hasattr(self, 'operational_channel'):
            from .installed_transport import enrolled_transport
            c = self.operational_channel
            self.transport = enrolled_transport(c, c.listener, process_reader=self.io.process, peer_reader=self.io.peer)
        else:
            self.transport=self.io.listener('supervisor',config.peer)
        return self.transport


# Kept outside the root adapter class: controller imports and SQLite are selected
# only by the controller factory. The supervisor never constructs these objects.
class InstalledControllerAdapters(InstalledBase):
    def __init__(self, io): super().__init__('controller',io)
    def open_registry(self,path): return self.io.open_registry(path)

    def compose_controller(self,registry,config):
        from .composition import ControllerRuntime,RemoteProcessBackend
        from .execution import Controller,Enrollment
        from .filesystem_evidence import ExpectedFilesystem
        from .runtime import RuntimeRegistry,DurableExecutionStore
        from .service_runtime import PeerAuthenticator
        modern = hasattr(self, 'operational_channel')
        founder=None if modern else client_peer(self.config['founder'],'founder',config.boot_id)
        proposal=None if modern else client_peer(self.config['proposal'],'proposal',config.boot_id)
        if not modern and founder.process==proposal.process:
            raise AuthorityError('Model process cannot be founder session.')
        if modern:
            self.config = dict(self.config, handshake=dict(endpoint='controller',
                generation=self.operational_channel.session.generation,
                enrollment_id=self.operational_channel.session.nonce))
        keys(self.config['handshake'],('endpoint','generation','enrollment_id'))
        if self.config['handshake']['endpoint']!='controller' or self.config['handshake']['generation']!=config.generation:
            raise AuthorityError('Wrong controller handshake generation.')
        uuid_value(self.config['handshake']['enrollment_id'])
        runtime=RuntimeRegistry(registry,founder_uid=self.config['founder_uid'] if modern else founder.uid,now=self.io.wall)
        roots,expected,plan_ids,repositories,enrollments={},{},{},{},[]
        rows=self.config['executions']
        if type(rows) is not list or len(rows)>4: raise ValidationError('Bounded execution catalog required.')
        for row in rows:
            keys(row,('execution_id','plan_id','filesystem','grant_path'))
            eid=uuid_value(row['execution_id']);uuid_value(row['plan_id'])
            if eid in roots:raise ValidationError('Duplicate execution enrollment.')
            expected[eid]=ExpectedFilesystem(canonical_json(row['filesystem']))
            roots[eid]=expected[eid].root_view(row['grant_path'])
            repositories[eid]=None if row['filesystem']['repository_identity'] is None else tuple(row['filesystem']['repository_identity'])
            plan_ids[eid]=row['plan_id']
            enrollments.append(Enrollment(PeerIdentity(proposal.uid,proposal.gid,proposal.process.pid),proposal.process,eid))
        if modern:
            from .installed_transport import enrolled_rpc
            rpc = enrolled_rpc(self.operational_channel, process_reader=self.io.process, peer_reader=self.io.peer)
        else:
            rpc = self.io.connect(config.peer,self.config['handshake'])
        client=DuplexClient(rpc,config.peer.generation,config.boot_id)
        remote=RemoteProcessBackend(client,plan_ids,generation=config.peer.generation,boot_id=config.boot_id,
            filesystem_expectations=expected)
        store=DurableExecutionStore(runtime,roots,repositories)
        # Routing event records are bounded and contain no command/environment content.
        def audit(event):
            runtime.registry.routing_event(event)
        authorization=Controller(store,tuple(enrollments),None,audit,clock=self.io.wall,
                                elapsed=self.io.now,process_reader=self.io.process)
        controller=ControllerRuntime(runtime,authorization,remote,generation=config.peer.generation,boot_id=config.boot_id,
            admission=getattr(self, "admission", None))
        self.driver=InstalledControllerDriver(controller,client,founder,proposal,enrollments,self.io)
        if self.config.get('founder_policy') is not None:
            self.driver.configure_founder(self.config['founder_policy'])
        return self.driver

    def listener(self,config):
        self.driver.open_clients()
        self.transport=ClientEvidenceTransport(self.driver.client,config.peer)
        return self.transport


from .supervisor_entry import SupervisorDriver
class InstalledSupervisorDriver(SupervisorDriver):
    def __init__(self,endpoint,work,deadline):
        self.deadline=deadline
        super().__init__(endpoint,work,heartbeat=deadline.check,control=deadline.check)
    def reconcile(self):
        clean=super().reconcile()
        if clean:self.deadline.start()
        return clean
    def disconnect(self):
        try:super().disconnect()
        finally:
            self.deadline.close()
            if self.endpoint.witness is not None:self.endpoint.witness.close()


class EvidenceWork:
    """Only heartbeat evidence flows through the controller's service pump."""
    def submit(self,request): raise AuthorityError('Unsolicited evidence outside correlated RPC.')
    def take_result(self): return None
    def cancel(self): pass


class ClientEvidenceTransport:
    """Adapts authenticated RPC heartbeat evidence to the existing ServiceLoop.

    It cannot synthesize a supervisor response. RPC responses are consumed by the
    controller sequencer; only actual correlated heartbeats enter the pump.
    """
    def __init__(self,client,enrollment):
        self.client,self.enrollment=client,enrollment
        self.accepted=False
        self.last=None
    def ready(self):self.client.check();return True
    def identity(self):
        self.client.rpc.verify()
        e=self.enrollment
        peer=self.client.rpc.peer_reader(self.client.rpc.sock)
        return peer,self.client.rpc.process_reader(peer.pid),dict(endpoint=e.endpoint,generation=e.generation,enrollment_id=e.enrollment_id)
    def accept(self):
        if self.accepted:return None
        self.accepted=True
        return self.identity()
    def poll(self,limit):
        from .composition_protocol import frame
        self.client.check()
        evidence=self.client.heartbeat_evidence
        if evidence is None or evidence['request_id']==self.last:return []
        self.last=evidence['request_id']
        return [('data',frame(evidence)),('end',b'')]
    def send(self,raw):raise AuthorityError('Controller pump cannot send uncorrelated execution requests.')
    def close(self):self.client.close()


class InstalledControllerDriver:
    def __init__(self,controller,client,founder,proposal,enrollments,io):
        self.controller,self.client,self.founder,self.proposal=controller,client,founder,proposal
        self.enrollments={e.execution_id:e for e in enrollments}
        self.io,self.work=io,EvidenceWork()
        self.listeners={}
        self.seen=set()
        self.client.maintenance=self.service_founder
        self.founder_transport = None
        self.founder_factory = None
        self.successor = False

    def configure_founder(self, installed_policy):
        """Generation-2 typed installed contract; never called from client data.

        Generation-1 configuration continues to reject this extra field. The
        successor bundle must bind this policy through its config digest.
        """
        self.successor = True
        from .authority_installation import InstallationBinding
        from .authority_journal import AuthorityJournal
        from .founder_intake import FounderPolicy, FounderIntake
        from .founder_crypto import load_founder_root
        from .filesystem_evidence import ExpectedFilesystem
        from .host_test_launch import CatalogLaunches
        keys(installed_policy, ('enabled','binding','root_digest','receipt_digest','activation','filesystem','host_tests_enabled'))
        policy = FounderPolicy(installed_policy['enabled'], InstallationBinding(**installed_policy['binding']),
            installed_policy['root_digest'], installed_policy['receipt_digest'], installed_policy['activation'],
            installed_policy['host_tests_enabled'])
        if not policy.enabled:
            return
        root = self.io.founder_root()
        journal = AuthorityJournal(self.controller.runtime.registry)
        expected = ExpectedFilesystem(canonical_json(installed_policy['filesystem'])) if policy.host_tests_enabled else None
        anchor = self.client.rpc.auth.enrollment.process
        peer = PeerIdentity(0, 0, anchor.pid)
        runner = CatalogLaunches(self.controller, policy.binding, expected, anchor, peer=peer,
            witness=self.io.witness('controller'),own_process=self.io.process(os.getpid()),elapsed=self.io.now) if expected else None
        self.host_runner = runner
        def context():
            self.client.rpc.verify()
            return dict(boot_id=self.controller.sequencer.boot_id,
                        controller_generation=self.controller.admission.session,
                        supervisor_generation=self.controller.sequencer.generation)
        def read_receipt():
            return canonical_json(self.io.read('/etc/bonup-agent-control/authority-receipt.json')).encode()
        def read_candidates():
            return tuple(canonical_json(self.io.read('/etc/bonup-agent-control/installation-'+name+'.json')).encode()
                         for name in ('candidate','approved'))
        self.founder_factory = lambda observe: FounderIntake(policy, root, observe, journal,
            controller=self.controller, runner=runner, runtime_context=context, receipt_reader=read_receipt,
            candidate_reader=read_candidates, clock=self.io.wall, boottime=self.io.now)
    def validate_config(self,config):
        return self.controller.sequencer.generation==config.peer.generation and self.controller.sequencer.boot_id==config.boot_id
    def reconcile(self):
        return all(r['state']=='TERMINAL' and r['cleanup_confirmed'] for r in self.controller.reconcile())
    def establish_admission(self):
        row=self.controller.runtime.db.execute("SELECT 1 FROM launch_attempts WHERE state!='TERMINAL'").fetchone()
        if row:
            return 'CLOSED'
        admission = self.controller.admission
        if admission is not None:
            from .operational_enrollment import AdmissionState
            if admission.state == AdmissionState.RECONCILING:
                self.deadlines()
                self.controller.tick()  # Durable revocation/deadline servicing before OPEN.
                admission.reconciled()
                if getattr(self, 'successor', False):
                    return 'CLOSED'
                result = self.controller.remote._call('OPEN_ADMISSION', str(uuid4()),
                    dict(session_digest=admission.session), 'ADMISSION_EVIDENCE')
                if result['session_digest'] != admission.session:
                    admission.close()
                    raise AuthorityError('Admission acknowledgement mismatch.')
                admission.open(admission.session)
            admission.require_open()
        return 'OPEN'
    def open_clients(self):
        if self.founder_factory is not None:
            from .founder_transport import FounderTransport
            self.founder_transport = FounderTransport(self.io._listener_socket('founder',1000),
                self.founder_factory, now=self.io.now, process_reader=self.io.process)
            return
        if self.founder is None and self.proposal is None:
            return  # No human/model authority is created by service enrollment.
        try:
            self.listeners['founder']=self.io.listener('founder',self.founder)
            self.listeners['proposal']=self.io.listener('proposals',self.proposal)
            if not all(t.ready() for t in self.listeners.values()):raise AuthorityError('Client listener unavailable.')
        except BaseException:
            for listener in self.listeners.values():listener.close()
            raise
    def heartbeat(self):self.client.check()
    def deadlines(self):self.client.check()
    def control(self):
        self.controller.tick()
        if self.founder_transport is not None:
            if self.founder_transport.intake is not None:
                self.founder_transport.intake.tick()
            self.founder_transport.poll()
        for kind,listener in self.listeners.items():
            if listener.handshake is None:listener.accept()
            if listener.handshake is None:continue
            try:
                incoming=listener.poll(4)
            except (AuthorityError,ValidationError,OSError):
                if kind=='proposal':self.controller.reject(b'', 'INVALID_PROPOSAL')
                raise
            for event,raw in incoming:
                if event=='disconnect':raise AuthorityError('Enrolled client disconnected.')
                if event=='data':
                    result=self.request(kind,bounded_json(raw[4:]),listener.identity())
                    listener.send(packet(result))
    def service_founder(self):
        # During final RELEASE the existing authority transaction linearizes
        # release versus revocation. Outside it, PREPARE waits service founder
        # control on this same SQLite-owning thread, without nested RPC.
        if self.controller.runtime.db.in_transaction:return
        if self.founder_transport is not None:
            self.founder_transport.poll()
            return
        listener=self.listeners.get('founder')
        if listener is None:return
        if listener.handshake is None:listener.accept()
        if listener.handshake is None:return
        for event,raw in listener.poll(4):
            if event=='disconnect':raise AuthorityError('Founder disconnected.')
            if event=='data':
                result=self.request('founder',bounded_json(raw[4:]),listener.identity(),defer_stop=True)
                listener.send(packet(result))

    def request(self,kind,data,observed,*,defer_stop=False):
        from .service_runtime import PeerAuthenticator
        from .identity import founder_context
        from .protocol import ModelProposal
        if kind not in ('founder','proposal'):raise AuthorityError('Unknown admission channel.')
        peer=self.founder if kind=='founder' else self.proposal
        if peer is None:
            raise AuthorityError('Human/model session not enrolled.')
        try:
            PeerAuthenticator(peer).verify(*observed)
        except BaseException:
            if kind=='proposal':self.controller.reject(b'', 'IDENTITY')
            raise
        if kind=='proposal':
            # Parsing/denial belongs to the audited controller path, including
            # malformed requests and unknown execution enrollment.
            eid=data.get('execution_id') if type(data) is dict else None
            enrollment=self.enrollments.get(eid) if type(eid) is str else None
            launch=self.controller.register(canonical_json(data).encode(),enrollment)
            self.controller.prepare(launch)
            row=self.controller.release(launch)
            return dict(version=1,request_id=data['request_id'],launch_id=launch,state=row['state'])
        keys(data,('version','request_id','action','execution_id','revision','launch_id'))
        if type(data['version']) is not int or data['version']!=1 or data['action'] not in ('REVOKE','CANCEL'):
            raise ValidationError('Unsupported founder control operation.')
        for key in ('request_id','execution_id','launch_id'):uuid_value(data[key])
        if data['request_id'] in self.seen or len(self.seen)>=4096:raise AuthorityError('Founder request replay/capacity.')
        if type(data['revision']) is not int or data['revision']<0:raise ValidationError('Explicit authority revision required.')
        launch=self.controller.runtime.launch(data['launch_id'])
        if launch['execution_id']!=data['execution_id']:raise AuthorityError('Wrong launch execution pairing.')
        context=founder_context(observed[0],founder_uid=peer.uid,enrolled_process=peer.process,reader=self.io.process)
        self.seen.add(data['request_id'])
        if data['action']=='REVOKE':self.controller.runtime.revoke(data['execution_id'],data['revision'],context=context)
        reason='REVOKED' if data['action']=='REVOKE' else 'CANCELLED'
        if defer_stop:
            row=launch
            if row['state'] not in ('STOPPING','TERMINAL'):
                row=self.controller.runtime.transition(data['launch_id'],row['revision'],'STOPPING',reason=reason)
        else:
            row=self.controller.stop(data['launch_id'],reason)
        return dict(version=1,request_id=data['request_id'],launch_id=data['launch_id'],state=row['state'])
    def disconnect(self):
        try:
            runner=getattr(self,'host_runner',None)
            if runner is not None:
                runner.observe_interruption(cleanup=lambda:self.controller.tick(controller_alive=False))
            else:self.controller.tick(controller_alive=False)
        finally:
            try:
                if self.founder_transport is not None:self.founder_transport.close()
            finally:
                try:
                    for listener in self.listeners.values():listener.close()
                finally:
                    try:self.client.close()
                    finally:
                        runner=getattr(self,'host_runner',None)
                        if runner is not None:runner.close()


def build_installed_controller_adapters(*, _io=None):
    return InstalledControllerAdapters(KernelIO() if _io is None else _io)


def build_installed_supervisor_adapters(*, _io=None):
    return InstalledSupervisorAdapters(KernelIO() if _io is None else _io)
