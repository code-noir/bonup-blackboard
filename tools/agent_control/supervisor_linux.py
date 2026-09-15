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


def secure_open(root_fd, relative, *, directory=False):
    """Linux openat2 with beneath/no-symlink/no-magiclink/no-mount-crossing."""
    from .confinement import safe_relative
    safe_relative(relative)
    if platform.machine() not in {'x86_64','aarch64'}:
        raise AuthorityError('Unsupported openat2 ABI.')
    class OpenHow(ctypes.Structure):
        _fields_ = [('flags',ctypes.c_uint64),('mode',ctypes.c_uint64),('resolve',ctypes.c_uint64)]
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    how = OpenHow(flags,0,0x01 | 0x02 | 0x04 | 0x08)
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
        self.armed,self.children = {},{}
        self.reconciled = False
        from .identity import ProcessIdentity
        self.anchor = ProcessIdentity.read(os.getpid())
        if '/usr/lib/bonup-agent-control/gate_entry.py' not in artifacts.files:
            raise AuthorityError('Installed gate missing.')

    def arm_deadline(self, launch_id, deadline):
        # Kernel timer is armed before any child. A stalled controller cannot renew it.
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
        with ExitStack() as stack:
            return self._prepare(launch,record,stack)

    def _prepare(self, launch, record, stack):
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
        root,profile,expected_identity = self.plans[launch_id]
        from .serialization import parse_json
        binding = parse_json(launch['binding'])
        if binding['supervisor_anchor'] != asdict(self.anchor) or list(expected_identity)!=binding['workspace']:
            raise AuthorityError('Supervisor anchor/workspace differs from registered launch.')
        self.anchor.verify()
        if profile.profile_digest!=record.profile_digest:
            raise AuthorityError('Installed launch profile mismatch.')
        mounts = PinnedMounts(root,profile,expected_identity=expected_identity)
        stack.callback(mounts.close)
        def owned(fd):
            stack.callback(os.close,fd)
            return fd
        parent,child = socket.socketpair()
        stack.callback(parent.close);stack.callback(child.close)
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
        config['expected']['channel_identity']=list(expected.channel_identity)
        cfgfd = owned(os.memfd_create('bonup-gate',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING))
        raw = canonical_json(config).encode()
        os.write(cfgfd,raw);os.lseek(cfgfd,0,os.SEEK_SET)
        fcntl.fcntl(cfgfd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
        # Gate receives only a sealed trusted config, its one-shot channel and standard pipes.
        gate = FixedPayload(('/usr/bin/python3','-I','/usr/lib/bonup-agent-control/gate_entry.py',str(cfgfd),str(child.fileno())),record.environment)
        argv = mounts.argv(gate)
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
                     output=[os.dup(out_r),os.dup(err_r)],buffers=[bytearray(),bytearray()],limit=record.output_bytes,exited=False)
        self.children[launch_id]=state
        pid = os.fork()
        if pid==0:
            try:
                os.dup2(null,0);os.dup2(out_w,1);os.dup2(err_w,2)
                keep=(0,1,2,start_r,cfgfd,child.fileno(),*mounts.pass_fds)
                close_except(keep)
                # Parent attaches child to cgroup before allowing even trusted bwrap setup.
                if os.read(start_r,1)!=b'P':
                    os._exit(125)
                os.close(start_r)
                set_process_limits(nofile=256,file_bytes=16777216,cpu_seconds=profile.cpu_seconds)
                drop_worker_identity(record.worker,allowed_fds=tuple(fd for fd in keep if fd!=start_r))
                for fd in (cfgfd,child.fileno(),*mounts.pass_fds):
                    os.set_inheritable(fd,True)
                os.chdir('/')
                os.execve('/usr/bin/bwrap',argv,{})
            except BaseException:
                os._exit(125)
        state['pid']=pid
        state['pidfd']=os.pidfd_open(pid)
        try:
            self.cgroups.attach(cgroup,pid)
            start_writer.write(b'P')
        finally:
            start_writer.close()
        # Gate announces readiness after setup and descriptor pruning; no model code runs.
        ready = receive_one(parent,limit=1024,timeout=5)
        if ready!={'version':1,'ready':launch_id}:
            raise AuthorityError('Confinement gate did not become ready.')
        return ProcessIdentity.read(pid)

    def release(self, launch, record):
        from .release_gate import release_frame
        state = self.children[launch['launch_id']]
        if state['expected'].authorization_digest!=record.authorization_digest:
            raise AuthorityError('Prepared authorization replaced.')
        state['socket'].sendall(release_frame(state['expected']))
        state['socket'].shutdown(socket.SHUT_WR)
        state['socket'].close()
        # Delivery is release intent, not proof of exec. Process exit is observed separately.

    def service_deadlines(self, *, now, elapsed):
        for launch_id,(deadline,fd) in self.armed.items():
            if deadline.expired(now=now,elapsed=elapsed) and launch_id in self.children:
                self.cgroups.kill(self.children[launch_id]['cgroup'])

    def kill(self, launch):
        state = self.children.get(launch['launch_id'])
        if state:
            self.cgroups.kill(state['cgroup'])
            # Covers trusted bootstrap failure before cgroup attachment.
            if state['pidfd'] is not None:
                try:
                    kill_pidfd(state['pidfd'])
                except ProcessLookupError:
                    pass  # Kernel confirms the exact pinned process no longer exists.

    def empty(self, launch):
        state = self.children.get(launch['launch_id'])
        if state is None:
            return self.reconciled  # Only after complete owned-subtree cleanup, never on missing evidence alone.
        return self.cgroups.empty(state['cgroup']) and self.exited(launch)

    def exited(self, launch):
        state = self.children.get(launch['launch_id'])
        if state is None:
            return False
        if state['pid'] is None:
            return True  # fork never created a process; cgroup emptiness is checked separately.
        for i,fd in enumerate(state['output']):
            try:
                chunk = os.read(fd,65536)
            except BlockingIOError:
                continue
            room=max(0,state['limit']-len(state['buffers'][i]))
            state['buffers'][i].extend(chunk[:room])
            if len(chunk)>room:
                self.cgroups.kill(state['cgroup'])
        if not state['exited']:
            pid,status=os.waitpid(state['pid'],os.WNOHANG)
            if pid:
                state['exited']=True
                state['exit_code']=os.waitstatus_to_exitcode(status)
        return state['exited']

    def finish(self, launch):
        """Close parent resources only after positive descendant cleanup evidence."""
        if not self.empty(launch):
            raise AuthorityError('Cannot finish uncertain launch.')
        launch_id=launch['launch_id']
        state=self.children.get(launch_id)
        exit_code=None
        if state is not None:
            self.cgroups.remove_empty(state['cgroup'])
            state['socket'].close()
            for fd in (*state['output'],state['pidfd']):
                if fd is not None:
                    os.close(fd)
            exit_code=state.get('exit_code')
            del self.children[launch_id]
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
