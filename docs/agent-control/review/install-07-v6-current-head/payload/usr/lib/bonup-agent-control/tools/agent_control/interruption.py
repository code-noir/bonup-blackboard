"""Kernel-bound interruption observations; never accepts caller PASS assertions.

The surviving service records target death while the exact canary is still alive,
before normal cleanup. Simultaneous/ambiguous deaths produce no passing evidence.
Generation-2 provisioning must create these fixed evidence directories first.
"""
from dataclasses import asdict
import os
from pathlib import Path
import select
import stat
import time

from .identity import ProcessIdentity
from .protocol import bounded_json, uuid_value
from .serialization import canonical_json
from .types import AuthorityError

PATHS = {'controller':'/var/lib/bonup-agent-control/runtime/interruption',
         'supervisor':'/var/lib/bonup-agent-supervisor/evidence'}
CGROUP='/sys/fs/cgroup/system.slice/bonup-agent-supervisor.service/'


def dead(fd):
    poll=select.poll();poll.register(fd,select.POLLIN)
    return bool(poll.poll(0))


def live_canary(process):
    process.verify()
    raw=Path('/proc/'+str(process.pid)+'/stat').read_text()
    if len(raw)>4096 or raw.rsplit(') ',1)[-1].split(' ',1)[0] not in ('R','S'):
        raise AuthorityError('Canary is stopped, exited or not observable.')


class Witness:
    def __init__(self, component):
        if component not in PATHS: raise AuthorityError('Unknown witness component.')
        self.component=component
        self.watches={}

    def preflight(self):
        for component in PATHS:
            fd=self._directory(component)
            try:
                if component==self.component and (os.fstatvfs(fd).f_flag & os.ST_RDONLY or
                        os.fstat(fd).st_mode & 0o300 != 0o300):
                    raise AuthorityError('Witness storage must be writable by its service owner.')
            finally:os.close(fd)

    def inspect(self, launch, worker, target):
        uuid_value(launch)
        for process in (worker,target): process.verify()
        live_canary(worker)
        path=CGROUP+'launch-'+launch
        info=os.stat(path,follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode): raise AuthorityError('Missing launch cgroup.')
        row=dict(launch_id=launch,process=asdict(worker),target=asdict(target),
                 cgroup_name='launch-'+launch,cgroup_identity=[info.st_dev,info.st_ino])
        if launch not in self.watches:
            worker_fd=os.pidfd_open(worker.pid,0)
            try: target_fd=os.pidfd_open(target.pid,0)
            except BaseException: os.close(worker_fd);raise
            self.watches[launch]=(row,worker_fd,target_fd)
        if self.watches[launch][0]!=row: raise AuthorityError('Interruption identity replaced.')
        if dead(self.watches[launch][1]) or dead(self.watches[launch][2]):
            raise AuthorityError('Interruption must be armed before either process exits.')
        return row

    def capture(self, launch):
        watch=self.watches.get(launch)
        if watch is None:return None
        row,worker_fd,target_fd=watch
        if not dead(target_fd) or dead(worker_fd):return None
        worker=ProcessIdentity(**row['process']);live_canary(worker)
        info=os.stat(CGROUP+row['cgroup_name'],follow_symlinks=False)
        if [info.st_dev,info.st_ino]!=row['cgroup_identity']:
            raise AuthorityError('Cgroup replaced at interruption.')
        # Recheck after the identity reads. No authority is inferred from a
        # socket close, journal message, PID number or a stopped test fixture.
        if dead(worker_fd):return None
        return dict(row,phase='TARGET_INTERRUPTED',worker_alive=True,
                   observed_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))

    def persist(self, event):
        if event is None:return False
        launch=event['launch_id']
        fd=self._directory(self.component)
        try:
            out=os.open(launch+'.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o644,dir_fd=fd)
            try:
                raw=canonical_json(event).encode()
                if os.write(out,raw)!=len(raw): raise AuthorityError('Short witness write.')
                os.fchmod(out,0o644)
                os.fsync(out)
            finally:os.close(out)
            os.fsync(fd)
        finally:os.close(fd)
        return True

    def observe(self, launch, *, cleanup=None):
        try:event=self.capture(launch)
        finally:
            if cleanup is not None:cleanup()
        # Durable evidence must never delay termination of the launch.
        return self.persist(event)

    @staticmethod
    def _directory(component):
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        try:
            for part in Path(PATHS[component]).parts[1:]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                os.close(fd);fd=child
                info=os.fstat(fd)
                owners=(0,3000) if component=='controller' else (0,)
                if info.st_uid not in owners or info.st_mode&0o022:
                    raise AuthorityError('Mutable witness path.')
            if info.st_uid != (3000 if component=='controller' else 0):
                raise AuthorityError('Wrong witness owner.')
            return fd
        except BaseException:os.close(fd);raise

    def read(self, component, launch):
        uuid_value(launch)
        fd=self._directory(component)
        try:
            source=os.open(launch+'.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=fd)
            try:
                info=os.fstat(source)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>4096 or
                        info.st_uid!=(3000 if component=='controller' else 0) or info.st_mode&0o022):
                    raise AuthorityError('Invalid witness artifact.')
                return bounded_json(os.read(source,4097))
            finally:os.close(source)
        finally:os.close(fd)

    def close(self):
        for _,worker,target in self.watches.values(): os.close(worker);os.close(target)
        self.watches.clear()
