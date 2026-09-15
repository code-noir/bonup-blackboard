"""Trusted exec-event acknowledgement, never inference from pipe EOF.

The confined gate traces only its own fixed-payload child. PTRACE_EVENT_EXEC is
kernel evidence of a successful exec transition, before payload instructions run.
No host capability is added. AppArmor/user-namespace compatibility is explicitly
HOST_TEST_REQUIRED; denial has no fallback. EOF, death and exec failure deny.
"""
from dataclasses import dataclass
import ctypes
import os
import signal
import struct

from .serialization import canonical_json
from .types import AuthorityError

PTRACE_TRACEME = 0
PTRACE_CONT = 7
PTRACE_DETACH = 17
PTRACE_SETOPTIONS = 0x4200
PTRACE_EVENT_EXEC = 4
PTRACE_O_TRACEEXEC = 1 << PTRACE_EVENT_EXEC
PTRACE_O_EXITKILL = 1 << 20


@dataclass(frozen=True)
class ExecStart:
    launch_id: str
    generation: str
    authorization_digest: str

    def verify(self, launch, record):
        if (self.launch_id != launch['launch_id'] or
                self.generation != launch['supervisor_generation'] or
                self.authorization_digest != record.authorization_digest):
            raise AuthorityError('Execution-start binding mismatch.')


def status_message(expected, outcome):
    return dict(version=1,launch_id=expected.launch_id,
        generation=expected.supervisor_generation,authorization_digest=expected.authorization_digest,
        nonce=expected.nonce,outcome=outcome)


def send_status(channel, expected, outcome):
    raw=canonical_json(status_message(expected,outcome)).encode()
    channel.sendall(struct.pack('!I',len(raw))+raw)
    channel.close()


def authorize_observed(gate, release, status, *, now):
    try:
        return gate.authorize(release,now=now)
    except BaseException:
        send_status(status,gate.expected,'RELEASE_REJECTED')
        raise


def ptrace(request, pid, data=0):
    libc=ctypes.CDLL(None,use_errno=True)
    libc.ptrace.restype=ctypes.c_long
    result=libc.ptrace(ctypes.c_ulong(request),ctypes.c_ulong(pid),ctypes.c_void_p(),ctypes.c_void_p(data))
    if result == -1:
        raise OSError(ctypes.get_errno(),'Trusted exec observation failed')


def execute_observed(payload, expected, channel, *, before_exec):
    """Single-threaded installed gate only; status FD is never in the payload."""
    from .supervisor_linux import close_worker_fds,verify_worker_fds
    signal.signal(signal.SIGCHLD,signal.SIG_DFL)
    parent=os.getpid()
    child=os.fork()
    if child == 0:
        try:
            channel.close()
            close_worker_fds();verify_worker_fds()
            libc=ctypes.CDLL(None,use_errno=True)
            if libc.prctl(1,signal.SIGKILL,0,0,0)!=0 or os.getppid()!=parent:
                raise AuthorityError('Gate parent death boundary unavailable.')
            ptrace(PTRACE_TRACEME,0)
            os.kill(os.getpid(),signal.SIGSTOP)
            os.chdir(payload.cwd)
            before_exec()
            os.execve(payload.argv[0],payload.argv,dict(payload.environment))
        except BaseException:
            os._exit(125)
    # The child is ours and cannot be reaped by another thread in this gate.
    # Pin it before any wait can reap it; cleanup must never signal a reused PID.
    try:
        child_fd=os.pidfd_open(child)
    except BaseException:
        # No wait/reaper has run: this owned child still reserves its PID.
        os.kill(child,signal.SIGKILL)
        os.waitpid(child,0)
        raise
    confirmed=False
    failure='GATE_FAILED'
    try:
        pid,status=os.waitpid(child,0)
        if pid!=child or not os.WIFSTOPPED(status) or os.WSTOPSIG(status)!=signal.SIGSTOP:
            raise AuthorityError('Gate child failed before exec observation.')
        ptrace(PTRACE_SETOPTIONS,child,PTRACE_O_TRACEEXEC | PTRACE_O_EXITKILL)
        ptrace(PTRACE_CONT,child)
        failure='EXEC_FAILED'
        pid,status=os.waitpid(child,0)
        if (pid!=child or not os.WIFSTOPPED(status) or
                os.WSTOPSIG(status)!=signal.SIGTRAP or status >> 16 != PTRACE_EVENT_EXEC):
            raise AuthorityError('No kernel execution-start event.')
        send_status(channel,expected,'EXEC_START_CONFIRMED')
        ptrace(PTRACE_DETACH,child)  # Only after evidence; never a wire command.
        confirmed=True
        _,status=os.waitpid(child,0)
        return os.waitstatus_to_exitcode(status)
    except BaseException:
        if channel.fileno()!=-1:
            send_status(channel,expected,failure)
        raise
    finally:
        channel.close()
        if not confirmed:
            try: signal.pidfd_send_signal(child_fd,signal.SIGKILL)
            except ProcessLookupError: pass
            try: os.waitpid(child,0)
            except ChildProcessError: pass
        os.close(child_fd)
