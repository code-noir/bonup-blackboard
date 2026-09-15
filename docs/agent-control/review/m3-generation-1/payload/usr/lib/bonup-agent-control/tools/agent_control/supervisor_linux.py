"""Explicit Linux primitives. Never called on import; no privileged test fallback."""
import ctypes
import errno
import os
import platform
import resource
import signal
import socket
import stat
from pathlib import Path

from .identity import WorkerIdentity
from .types import AuthorityError, ValidationError


def _libc():
    return ctypes.CDLL(None,use_errno=True)


def _check(result, message):
    if result < 0:
        raise OSError(ctypes.get_errno(),message)
    return result


def close_except(allowed):
    """Single-threaded bootstrap only. Existing FD allowlist, not caller wire input."""
    if type(allowed) is not tuple or any(type(fd) is not int or fd < 0 for fd in allowed):
        raise ValidationError('Invalid FD policy.')
    for fd in allowed:
        os.fstat(fd)
    libc = _libc()
    if not hasattr(libc,'close_range'):
        raise AuthorityError('close_range required; no permissive fallback.')
    start = 0
    for fd in sorted(set(allowed)):
        if start < fd:
            _check(libc.close_range(ctypes.c_uint(start),ctypes.c_uint(fd-1),0),'close_range')
        start = fd+1
    _check(libc.close_range(ctypes.c_uint(start),ctypes.c_uint(0xffffffff),0),'close_range')


def open_fds():
    # listdir's own FD has closed before fstat. Ignore only this EBADF race.
    found = set()
    for name in os.listdir('/proc/self/fd'):
        try:
            os.fstat(int(name))
        except OSError as error:
            if error.errno == errno.EBADF:
                continue
            raise
        found.add(int(name))
    return found


def close_worker_fds():
    close_except((0,1,2))


def verify_worker_fds():
    if open_fds() != {0,1,2}:
        raise AuthorityError('Unexpected worker descriptor.')


def secure_open(root_fd, relative, *, directory=False, git=False, allow_mount=False):
    """Linux openat2 with beneath/no-symlink/no-magiclink/no-mount-crossing."""
    from .confinement import safe_relative
    safe_relative(relative, git=git)
    if type(allow_mount) is not bool or type(git) is not bool:
        raise ValidationError('Trusted resolution policy required.')
    if platform.machine() not in {'x86_64','aarch64'}:
        raise AuthorityError('Unsupported openat2 ABI.')
    class OpenHow(ctypes.Structure):
        _fields_ = [('flags',ctypes.c_uint64),('mode',ctypes.c_uint64),('resolve',ctypes.c_uint64)]
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    how = OpenHow(flags,0,(0 if allow_mount else 0x01) | 0x02 | 0x04 | 0x08)
    libc = _libc()
    libc.syscall.restype = ctypes.c_long
    fd = _check(libc.syscall(ctypes.c_long(437),ctypes.c_int(root_fd),relative.encode(),
                            ctypes.byref(how),ctypes.sizeof(how)),'openat2')
    info = os.fstat(fd)
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or (stat.S_ISREG(info.st_mode) and info.st_nlink!=1):
        os.close(fd)
        raise AuthorityError('Special/hardlinked source rejected.')
    return fd


def drop_worker_identity(worker, *, allowed_fds):
    """Real privileged child bootstrap. Must not run in controller/model process."""
    if os.geteuid()!=0 or type(worker) is not WorkerIdentity:
        raise AuthorityError('Privileged enrolled bootstrap required.')
    import pwd
    account = pwd.getpwnam(worker.username)
    if (account.pw_uid,account.pw_gid)!=(worker.uid,worker.gid):
        raise AuthorityError('Installed account differs from enrollment.')
    close_except(allowed_fds)
    os.environ.clear()
    os.setgroups([])
    os.setresgid(worker.gid,worker.gid,worker.gid)
    os.setresuid(worker.uid,worker.uid,worker.uid)
    # Linux clears effective/permitted capabilities on the transition from root.
    libc = _libc()
    _check(libc.prctl(38,1,0,0,0),'PR_SET_NO_NEW_PRIVS')
    _check(libc.prctl(47,4,0,0,0),'PR_CAP_AMBIENT_CLEAR_ALL')
    if os.getresuid()!=(worker.uid,)*3 or os.getresgid()!=(worker.gid,)*3 or os.getgroups():
        raise AuthorityError('UID/group drop failed.')
    status = Path('/proc/self/status').read_text()
    values = dict(line.split(':',1) for line in status.splitlines() if ':' in line)
    if any(int(values[k].strip(),16) for k in ('CapEff','CapPrm','CapInh','CapAmb')):
        raise AuthorityError('Host capabilities remain.')
    os.umask(0o077)


def set_process_limits(*, nofile, file_bytes, cpu_seconds):
    if any(type(x) is not int or x<=0 for x in (nofile,file_bytes,cpu_seconds)):
        raise ValidationError('Positive process limits required.')
    for kind,value in ((resource.RLIMIT_NOFILE,nofile),(resource.RLIMIT_FSIZE,file_bytes),
                       (resource.RLIMIT_CPU,cpu_seconds),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(value,value))


class CgroupV2:
    """A pre-opened, root-owned delegated subtree. Never accepts absolute child paths."""
    def __init__(self, root_fd):
        info = os.fstat(root_fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise AuthorityError('Root-owned delegated cgroup required.')
        # Filesystem magic CGROUP2_SUPER_MAGIC. Reject an ordinary directory backend.
        class StatFS(ctypes.Structure):
            _fields_ = [('type',ctypes.c_long),('rest',ctypes.c_byte*248)]
        fs = StatFS()
        _check(_libc().fstatfs(root_fd,ctypes.byref(fs)),'fstatfs')
        if fs.type != 0x63677270:
            raise AuthorityError('cgroup v2 filesystem required.')
        self.root_fd = os.dup(root_fd)
        self.children = {}

    def create(self, launch_id, *, cpu_percent, memory_bytes, pids):
        from .protocol import uuid_value
        uuid_value(launch_id)
        if any(type(v) is not int or v<=0 for v in (cpu_percent,memory_bytes,pids)):
            raise ValidationError('Invalid cgroup limits.')
        name = 'launch-'+launch_id
        os.mkdir(name,0o700,dir_fd=self.root_fd)
        fd = os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.root_fd)
        self.children[name] = fd
        for key,value in (('cpu.max',f'{cpu_percent*1000} 100000'),('memory.max',str(memory_bytes)),
                          ('memory.swap.max','0'),('pids.max',str(pids)),('memory.oom.group','1')):
            self._write(name,key,value)
        return name

    def _write(self, name, key, value):
        fd = os.open(key,os.O_WRONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=self.children[name])
        try:
            raw = value.encode('ascii')
            if os.write(fd,raw)!=len(raw):
                raise AuthorityError('Short cgroup write.')
        finally:
            os.close(fd)

    def attach(self, name, pid):
        if type(pid) is not int or pid<=0:
            raise ValidationError('Invalid bootstrap PID.')
        self._write(name,'cgroup.procs',str(pid))

    def kill(self, name):
        self._write(name,'cgroup.kill','1')

    def empty(self, name):
        fd = os.open('cgroup.events',os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=self.children[name])
        try:
            data = os.read(fd,4096).decode('ascii')
        finally:
            os.close(fd)
        fields = dict(line.split() for line in data.splitlines())
        if fields.get('populated') not in {'0','1'}:
            raise AuthorityError('Uncertain cgroup state.')
        return fields['populated']=='0'

    def cpu_usage(self, name):
        fd=os.open('cpu.stat',os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=self.children[name])
        try: raw=os.read(fd,4097)
        finally: os.close(fd)
        if len(raw)>4096: raise AuthorityError('Unbounded cgroup CPU evidence.')
        rows=dict(line.split() for line in raw.decode('ascii').splitlines())
        value=rows.get('usage_usec')
        if value is None or not value.isdecimal(): raise AuthorityError('Missing cgroup CPU evidence.')
        return int(value)

    def close(self):
        for fd in self.children.values():
            os.close(fd)
        self.children.clear()
        os.close(self.root_fd)

    def remove_empty(self, name):
        if not self.empty(name):
            raise AuthorityError('Cgroup descendants remain.')
        os.rmdir(name,dir_fd=self.root_fd)
        os.close(self.children.pop(name))


def kill_pidfd(pidfd):
    signal.pidfd_send_signal(pidfd,signal.SIGKILL)


class InstalledArtifacts:
    """Only verified root-owned immutable installed files may enter a privileged launch."""
    def __init__(self, files):
        import hashlib
        if type(files) is not dict or not files:
            raise AuthorityError('Installed artifact hash manifest required.')
        self.files = dict(files)
        self.installation = None
        for path, expected in self.files.items():
            absolute = Path(path)
            if not absolute.is_absolute() or not str(absolute).startswith('/usr/lib/bonup-agent-control/'):
                raise AuthorityError('Artifacts must be installed outside writable checkout.')
            for parent in (absolute,*absolute.parents):
                info = parent.lstat()
                if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
                    raise AuthorityError('Mutable installed artifact/ancestor.')
            if not absolute.is_file() or hashlib.sha256(absolute.read_bytes()).hexdigest()!=expected:
                raise AuthorityError('Installed artifact digest mismatch.')

    def bind_installation(self, bundle_digest, generation):
        from .schema import valid_format
        if self.installation is not None or not valid_format('sha256',bundle_digest) or type(generation) is not int or generation != 1:
            raise AuthorityError('Invalid installation binding.')
        self.installation = (bundle_digest,generation)

    def pin(self, worker):
        """Inspect and retain exactly the installed subtree mounted for this gate."""
        from .gate_entry import installation_object
        if self.installation is None:
            raise AuthorityError('Bundle identity not bound.')
        prefix='/usr/lib/bonup-agent-control'
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        try:
            for part in prefix.split('/')[1:]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                os.close(fd);fd=child
                info=os.fstat(fd)
                if info.st_uid!=0 or info.st_gid!=0 or info.st_mode&0o022:
                    raise AuthorityError('Untrusted installation ancestor.')
            names={''}
            for path in self.files:
                relative=path[len(prefix)+1:]
                names.add(relative)
                names.update(str(p) for p in Path(relative).parents if str(p)!='.')
            members={name:installation_object(fd,name) for name in sorted(names)}
            for name,item in members.items():
                if item['uid']!=0 or item['gid']!=0 or item['mode']&0o022:
                    raise AuthorityError('Mutable installation member.')
                if not item['directory'] and item['sha256']!=self.files.get(prefix+'/'+name):
                    raise AuthorityError('Installation artifact substituted.')
            proof=dict(version=1,generation=self.installation[1],bundle_digest=self.installation[0],members=members,
                uid_map=[[worker.uid,worker.uid,1]],gid_map=[[worker.gid,worker.gid,1]],
                namespace_owner=[int(Path('/proc/sys/kernel/overflowuid').read_text()),
                                 int(Path('/proc/sys/kernel/overflowgid').read_text())])
            return fd,proof
        except BaseException:
            os.close(fd)
            raise


class LinuxProcessBackend:
    """Explicit installed-host adapter. No automatic creation/startup or root fallback.

    The service's single-threaded event loop must call service_deadlines independently
    of controller messages and feed systemd's watchdog. Unit integration is separately
    gated. No instance is constructed by ordinary tests.
    """
    def __init__(self, artifacts, cgroups, *, plans, boot_id):
        if os.geteuid()!=0 or type(artifacts) is not InstalledArtifacts or type(cgroups) is not CgroupV2:
            raise AuthorityError('Verified installed privileged supervisor required.')
        self.artifacts,self.cgroups,self.plans,self.boot_id = artifacts,cgroups,plans,boot_id
        self.armed,self.children,self.results = {},{},{}
        import threading
        self.release_lock=threading.RLock()
        self.reconciled = False
        from .identity import ProcessIdentity
        self.anchor = ProcessIdentity.read(os.getpid())
        if '/usr/lib/bonup-agent-control/gate_entry.py' not in artifacts.files:
            raise AuthorityError('Installed gate missing.')

    def arm_deadline(self, launch_id, deadline):
        # Kernel timer is armed before any child. A stalled controller cannot renew it.
        if launch_id in self.armed or launch_id in self.results:
            raise AuthorityError('Launch deadline replay.')
        import time
        class Timespec(ctypes.Structure):
            _fields_ = [('seconds',ctypes.c_long),('nanoseconds',ctypes.c_long)]
        class Itimerspec(ctypes.Structure):
            _fields_ = [('interval',Timespec),('value',Timespec)]
        fd = _check(_libc().timerfd_create(7,os.O_CLOEXEC|os.O_NONBLOCK),'timerfd_create')
        seconds = int(deadline.elapsed_deadline)
        value = Itimerspec(Timespec(0,0),Timespec(seconds,int((deadline.elapsed_deadline-seconds)*1_000_000_000)))
        try:
            _check(_libc().timerfd_settime(fd,1,ctypes.byref(value),None),'timerfd_settime')
            self.armed[launch_id]=(deadline,fd)
        except BaseException:
            os.close(fd)
            raise

    def prepare(self, launch, record):
        from contextlib import ExitStack
        if not self.reconciled:
            raise AuthorityError('Startup survivor reconciliation required.')
        try:
            with ExitStack() as stack:
                return self._prepare(launch,record,stack)
        finally:
            state=self.children.get(launch['launch_id'])
            if state is not None: state['preparing']=False

    def prepare_pinned(self, launch, record, handle):
        """Installed pinned route; borrowed descriptors remain inspector-owned.

        Requires the immutable bootstrap artifact. No legacy pathname fallback.
        Actual UID/cgroup/bwrap execution is separately HOST_TEST_REQUIRED.
        """
        from contextlib import ExitStack
        from .filesystem_evidence import PinnedFilesystem
        if type(handle) is not PinnedFilesystem or not self.reconciled:
            raise AuthorityError('Reconciled pinned filesystem handle required.')
        if '/usr/lib/bonup-agent-control/bootstrap_entry.py' not in self.artifacts.files:
            raise AuthorityError('Verified installed bootstrap missing.')
        handle.verify(launch['launch_id'])
        try:
            with ExitStack() as stack:
                return self._prepare(launch, record, stack, handle=handle)
        finally:
            state=self.children.get(launch['launch_id'])
            if state is not None:
                state['preparing']=False

    def _prepare(self, launch, record, stack, handle=None):
        import fcntl
        import json
        import socket
        from dataclasses import asdict
        from uuid import uuid4
        from .identity import PeerIdentity, ProcessIdentity
        from .release_gate import ExpectedRelease, FixedPayload, receive_one
        from .serialization import canonical_json
        from .confinement import PinnedMounts
        launch_id = launch['launch_id']
        if handle is None:
            root,profile,expected_identity = self.plans[launch_id]
        else:
            root,profile,expected_identity = handle.root,handle.mapping.profile,handle.mapping.object_identity
        from .serialization import parse_json
        binding = parse_json(launch['binding'])
        if binding['supervisor_anchor'] != asdict(self.anchor) or list(expected_identity)!=binding['workspace']:
            raise AuthorityError('Supervisor anchor/workspace differs from registered launch.')
        self.anchor.verify()
        if profile.profile_digest!=record.profile_digest:
            raise AuthorityError('Installed launch profile mismatch.')
        if handle is None:
            mounts = PinnedMounts(root,profile,expected_identity=expected_identity)
            stack.callback(mounts.close)
        else:
            mounts = handle
        def owned(fd):
            stack.callback(os.close,fd)
            return fd
        parent,child = socket.socketpair()
        stack.callback(parent.close);stack.callback(child.close)
        status_parent,status_child=socket.socketpair()
        stack.callback(status_parent.close);stack.callback(status_child.close)
        if PeerIdentity.from_socket(child)!=PeerIdentity.current():
            raise AuthorityError('Bootstrap release peer mismatch.')
        channel_info=os.fstat(child.fileno())
        expected = ExpectedRelease(launch_id,launch['supervisor_generation'],record.authorization_digest,
                                   str(uuid4()),launch['deadline'],PeerIdentity.current(),
                                   int(self.armed[launch_id][0].elapsed_deadline*1_000_000_000),
                                   (channel_info.st_dev,channel_info.st_ino))
        config = dict(expected=asdict(expected),payload=dict(argv=list(record.argv),environment=[list(x) for x in record.environment],cwd=record.cwd),
                      worker=[record.worker.uid,record.worker.gid],
                      host_namespaces={n:os.stat('/proc/self/ns/'+n).st_ino for n in ('mnt','pid','net')})
        installation_fd,config['installation']=self.artifacts.pin(record.worker)
        owned(installation_fd)
        status_info=os.fstat(status_child.fileno())
        config['status_channel']=dict(fd=status_child.fileno(),device=status_info.st_dev,inode=status_info.st_ino)
        config['expected']['channel_identity']=list(expected.channel_identity)
        cfgfd = owned(os.memfd_create('bonup-gate',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING))
        raw = canonical_json(config).encode()
        os.write(cfgfd,raw);os.lseek(cfgfd,0,os.SEEK_SET)
        fcntl.fcntl(cfgfd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
        # Gate receives only a sealed trusted config, its one-shot channel and standard pipes.
        gate = FixedPayload(('/usr/bin/python3','-I','/usr/lib/bonup-agent-control/gate_entry.py',str(cfgfd),str(child.fileno())),record.environment)
        if handle is None:
            argv = mounts.argv(gate)
        else:
            from .resource_supervision import build_plan
            fixed = build_plan(launch,record,handle,config_fd=cfgfd,release_fd=child.fileno())
            argv = fixed.bwrap_argv
        # The same inspected descriptor is bound over the installed subtree.
        # No host pathname is reopened between verification and bwrap exposure.
        mount_at=argv.index('--remount-ro')
        argv=tuple(argv[:mount_at])+('--ro-bind-fd',str(installation_fd),'/usr/lib/bonup-agent-control')+tuple(argv[mount_at:])
        start_r,start_w = os.pipe2(os.O_CLOEXEC)
        owned(start_r)
        start_writer=stack.enter_context(os.fdopen(start_w,"wb",buffering=0))
        out_r,out_w = os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK)
        owned(out_r);owned(out_w)
        err_r,err_w = os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK)
        owned(err_r);owned(err_w)
        null = owned(os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC))
        cgroup = self.cgroups.create(launch_id,cpu_percent=100,memory_bytes=profile.memory_bytes,pids=profile.process_limit)
        state = dict(cgroup=cgroup,pid=None,pidfd=None,socket=parent.dup(),expected=expected,
                     status_socket=status_parent.dup(),exec_confirmed=False,
                     output=[os.dup(out_r),os.dup(err_r)],buffers=[bytearray(),bytearray()],limit=record.output_bytes,exited=False,
                     preparing=True,stopped=False,released=False,truncated=[False,False])
        self.children[launch_id]=state
        if handle is not None:
            # posix_spawn executes only an immutable trusted bootstrap. Unlike a
            # Python post-fork callback this is safe to invoke from a work thread.
            bootfd = owned(os.memfd_create('bonup-bootstrap',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING))
            keep=(0,1,2,start_r,cfgfd,child.fileno(),status_child.fileno(),installation_fd,*mounts.pass_fds,bootfd)
            bootconfig=dict(version=1,worker=[record.worker.uid,record.worker.gid],argv=list(argv),
                keep=list(keep),start_fd=start_r,cpu_seconds=profile.cpu_seconds)
            os.write(bootfd,canonical_json(bootconfig).encode());os.lseek(bootfd,0,os.SEEK_SET)
            fcntl.fcntl(bootfd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
            actions=[(os.POSIX_SPAWN_DUP2,null,0),(os.POSIX_SPAWN_DUP2,out_w,1),(os.POSIX_SPAWN_DUP2,err_w,2)]
            for fd in keep[3:]:
                duplicate=owned(os.dup(fd))
                actions.append((os.POSIX_SPAWN_DUP2,duplicate,fd))
            pid=os.posix_spawn('/usr/bin/python3',('/usr/bin/python3','-I',
                '/usr/lib/bonup-agent-control/bootstrap_entry.py',str(bootfd)),{},file_actions=actions)
        else:
            pid = os.fork()
        if pid==0:
            try:
                os.dup2(null,0);os.dup2(out_w,1);os.dup2(err_w,2)
                keep=(0,1,2,start_r,cfgfd,child.fileno(),status_child.fileno(),installation_fd,*mounts.pass_fds)
                close_except(keep)
                # Parent attaches child to cgroup before allowing even trusted bwrap setup.
                if os.read(start_r,1)!=b'P':
                    os._exit(125)
                os.close(start_r)
                set_process_limits(nofile=256,file_bytes=16777216,cpu_seconds=profile.cpu_seconds)
                drop_worker_identity(record.worker,allowed_fds=tuple(fd for fd in keep if fd!=start_r))
                for fd in (cfgfd,child.fileno(),status_child.fileno(),installation_fd,*mounts.pass_fds):
                    os.set_inheritable(fd,True)
                os.chdir('/')
                os.execve('/usr/bin/bwrap',argv,{})
            except BaseException:
                os._exit(125)
        state['pid']=pid
        state['pidfd']=os.pidfd_open(pid)
        try:
            self.cgroups.attach(cgroup,pid)
            if state['stopped']:
                raise AuthorityError('Preparation was cancelled.')
            start_writer.write(b'P')
        finally:
            start_writer.close()
        # Gate announces readiness after setup and descriptor pruning; no model code runs.
        ready = receive_one(parent,limit=1024,timeout=5)
        if ready!={'version':1,'ready':launch_id}:
            raise AuthorityError('Confinement gate did not become ready.')
        state['preparing']=False
        if state['stopped']:
            raise AuthorityError('Cancelled preparation cannot release.')
        return ProcessIdentity.read(pid)

    def release(self, launch, record):
        with self.release_lock:
            self._release(launch,record)
        # Never hold the deadline/kill lock while waiting on a gate status pipe.
        from .release_gate import receive_one
        from .exec_start import ExecStart,status_message
        state=self.children[launch['launch_id']]
        try:
            proof=receive_one(state['status_socket'],limit=2048,timeout=.5)
            outcome=proof.get('outcome') if type(proof) is dict else None
            if (outcome not in ('EXEC_START_CONFIRMED','RELEASE_REJECTED','GATE_FAILED','EXEC_FAILED') or
                    proof!=status_message(state['expected'],outcome)):
                raise AuthorityError('Malformed execution-start evidence.')
            state['start_outcome']=outcome
            if outcome!='EXEC_START_CONFIRMED':
                raise AuthorityError('Gate did not confirm a kernel exec transition.')
            with self.release_lock:
                if state['stopped']:
                    raise AuthorityError('Launch stopped before execution acknowledgement.')
                state['exec_confirmed']=True
            return ExecStart(launch['launch_id'],launch['supervisor_generation'],record.authorization_digest)
        except BaseException:
            if state.get('start_outcome') in (None,'RELEASE_DELIVERED'):
                state['start_outcome']='UNCERTAIN'
            raise
        finally:
            state['status_socket'].close()

    def _release(self, launch, record):
        from .release_gate import release_frame
        state = self.children[launch['launch_id']]
        deadline=self.armed[launch['launch_id']][0]
        from datetime import datetime,timezone
        import time
        if (state['stopped'] or state['preparing'] or state['released'] or
                deadline.expired(now=datetime.now(timezone.utc),elapsed=time.clock_gettime(time.CLOCK_BOOTTIME)) or
                state['expected'].authorization_digest!=record.authorization_digest):
            raise AuthorityError('Prepared authorization replaced.')
        state['released']=True
        state['socket'].settimeout(.1)
        state['socket'].sendall(release_frame(state['expected']))
        state['socket'].shutdown(socket.SHUT_WR)
        state['socket'].close()
        state['start_outcome']='RELEASE_DELIVERED'
        # Delivery is only intent. release() separately requires the gate exec event.

    def service_deadlines(self, *, now, elapsed):
        with self.release_lock:
            return self._service_deadlines(now=now,elapsed=elapsed)

    def _service_deadlines(self, *, now, elapsed):
        for launch_id,(deadline,fd) in tuple(self.armed.items()):
            state=self.children.get(launch_id)
            if state is not None and (deadline.expired(now=now,elapsed=elapsed) or
                    self.cgroups.cpu_usage(state['cgroup'])>=30_000_000):
                self.kill({'launch_id':launch_id})

    def kill(self, launch):
        with self.release_lock:
            self._kill(launch)

    def _kill(self, launch):
        state = self.children.get(launch['launch_id'])
        if not state:
            name='launch-'+launch['launch_id']
            if name in self.cgroups.children: self.cgroups.kill(name)
        if state:
            state['stopped']=True
            self.cgroups.kill(state['cgroup'])
            # Covers trusted bootstrap failure before cgroup attachment.
            if state['pidfd'] is not None:
                try:
                    kill_pidfd(state['pidfd'])
                except ProcessLookupError:
                    pass  # Kernel confirms the exact pinned process no longer exists.

    def empty(self, launch):
        with self.release_lock:
            return self._empty(launch)

    def _empty(self, launch):
        state = self.children.get(launch['launch_id'])
        if state is None:
            name='launch-'+launch['launch_id']
            return self.reconciled and (name not in self.cgroups.children or self.cgroups.empty(name))
        if state.get('preparing',False):
            return False
        return self.cgroups.empty(state['cgroup']) and self.exited(launch)

    def exited(self, launch):
        with self.release_lock:
            return self._exited(launch)

    def _exited(self, launch):
        state = self.children.get(launch['launch_id'])
        if state is None or state.get('preparing',False):
            return False
        if state['pid'] is None:
            return True  # fork never created a process; cgroup emptiness is checked separately.
        for i,fd in enumerate(state['output']):
            try:
                chunk = os.read(fd,16384)
            except BlockingIOError:
                continue
            room=max(0,state['limit']-len(state['buffers'][i]))
            state['buffers'][i].extend(chunk[:room])
            if len(chunk)>room:
                state['truncated'][i]=True
        if not state['exited']:
            pid,status=os.waitpid(state['pid'],os.WNOHANG)
            if pid:
                state['exited']=True
                state['exit_code']=os.waitstatus_to_exitcode(status)
        return state['exited']

    def output_evidence(self, launch):
        with self.release_lock:
            return self._output_evidence(launch)

    def _output_evidence(self, launch):
        if launch['launch_id'] in self.results:
            return {k:dict(v) for k,v in self.results[launch['launch_id']].items()}
        state=self.children[launch['launch_id']]
        return {name:dict(retained=len(state['buffers'][i]),truncated=state['truncated'][i])
                for i,name in enumerate(('stdout','stderr'))}

    def finish(self, launch):
        with self.release_lock:
            return self._finish(launch)

    def _finish(self, launch):
        """Close parent resources only after positive descendant cleanup evidence."""
        if not self.empty(launch):
            raise AuthorityError('Cannot finish uncertain launch.')
        launch_id=launch['launch_id']
        state=self.children.get(launch_id)
        exit_code=None
        if state is not None:
            # The launch is empty: drain bounded kernel pipe capacity before closing.
            for _ in range(4): self.exited(launch)
            self.results[launch_id]=self.output_evidence(launch)
            self.cgroups.remove_empty(state['cgroup'])
            state['socket'].close()
            if 'status_socket' in state:
                state['status_socket'].close()
            for fd in (*state['output'],state['pidfd']):
                if fd is not None:
                    os.close(fd)
            exit_code=state.get('exit_code')
            del self.children[launch_id]
        elif 'launch-'+launch_id in self.cgroups.children:
            self.cgroups.remove_empty('launch-'+launch_id)
        armed=self.armed.pop(launch_id,None)
        if armed is not None:
            os.close(armed[1])
        return exit_code

    def reconcile_unknown(self):
        from .protocol import uuid_value
        clean = True
        for name in os.listdir(self.cgroups.root_fd):
            info = os.stat(name,dir_fd=self.cgroups.root_fd,follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or name=='supervisor':
                continue
            if not name.startswith('launch-'):
                raise AuthorityError('Unknown delegated child directory.')
            uuid_value(name.removeprefix('launch-'))
            if info.st_uid!=0 or info.st_mode & 0o022:
                raise AuthorityError('Untrusted delegated child.')
            if name not in self.cgroups.children:
                self.cgroups.children[name]=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=self.cgroups.root_fd)
            self.cgroups.kill(name)
            clean = self.cgroups.empty(name) and clean
        self.reconciled = clean
        return clean
