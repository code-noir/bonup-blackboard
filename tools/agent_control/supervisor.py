"""Supervisor state machine and authenticated one-shot control protocol.

No listening socket or host cgroup is created on import. Backend setup is trusted
installation code; wire requests select a registered launch, never host parameters.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import socket
import struct
import time
from uuid import uuid4

from .identity import PeerIdentity, ProcessIdentity
from .protocol import uuid_value
from .release_gate import ExpectedRelease, receive_one, release_frame
from .runtime import STATES
from .schema import timestamp
from .serialization import canonical_json, digest, parse_json
from .types import AuthorityError, ValidationError


@dataclass(frozen=True)
class ControllerEnrollment:
    peer: PeerIdentity
    process: ProcessIdentity
    generation: str

    def __post_init__(self):
        uuid_value(self.generation)
        if type(self.peer) is not PeerIdentity or type(self.process) is not ProcessIdentity or self.peer.uid<=0 or self.peer.pid!=self.process.pid:
            raise AuthorityError('Unprivileged controller process enrollment required.')


def supervisor_frame(request_id, launch_id, generation, action):
    data = dict(version=1, request_id=request_id,launch_id=launch_id,supervisor_generation=generation,action=action)
    raw = canonical_json(data).encode()
    return struct.pack('!I',len(raw))+raw


class SupervisorProtocol:
    def __init__(self, enrollment, runtime, process_reader=None):
        if type(enrollment) is not ControllerEnrollment:
            raise AuthorityError('Controller enrollment required.')
        self.enrollment, self.runtime, self.process_reader = enrollment, runtime, process_reader

    def receive(self, sock):
        try:
            if PeerIdentity.from_socket(sock)!=self.enrollment.peer:
                raise AuthorityError('Controller peer mismatch.')
            self.enrollment.process.verify(self.process_reader)
            data = receive_one(sock,limit=4096)
            if type(data) is not dict or set(data)!={'version','request_id','launch_id','supervisor_generation','action'}:
                raise ValidationError('Unexpected supervisor fields.')
            if type(data['version']) is not int or data['version']!=1 or data['action'] not in ('PREPARE','RELEASE','CANCEL','STATUS'):
                raise ValidationError('Unsupported supervisor action.')
            for k in ('request_id','launch_id','supervisor_generation'):
                uuid_value(data[k])
            if data['supervisor_generation']!=self.enrollment.generation:
                raise AuthorityError('Stale supervisor generation.')
            launch = self.runtime.launch(data['launch_id'])
            if launch['supervisor_generation']!=data['supervisor_generation']:
                raise AuthorityError('Launch generation mismatch.')
            # Unique private operation IDs reject replay across reconnect/restart.
            with self.runtime.transaction('supervisor-request'):
                if self.runtime.db.execute('SELECT 1 FROM operations WHERE operation_id=?',(data['request_id'],)).fetchone():
                    raise AuthorityError('Request ID already belongs to registry operation.')
                self.runtime.db.execute('INSERT INTO maintenance_operations VALUES (?,?,?)',
                    (data['request_id'],digest(data),'{"status":"CONSUMED"}'))
            return data
        finally:
            sock.close()


@dataclass(frozen=True)
class ExecutionDeadline:
    expires_at: datetime
    elapsed_deadline: float

    @classmethod
    def arm(cls, expires_at, *, now, elapsed, timeout_seconds):
        expiry = timestamp(expires_at)
        remaining = min((expiry-now).total_seconds(),timeout_seconds)
        if remaining<=0:
            raise AuthorityError('Expired authority.')
        return cls(expiry,elapsed+remaining)

    def expired(self, *, now, elapsed):
        return now>=self.expires_at or elapsed>=self.elapsed_deadline


class Supervisor:
    """Single authority sequencer. Backend must keep children gated until release.

    backend.arm_deadline is independent of controller IPC; loss of the controller
    also invokes stop. Production wiring must drive poll and watchdog continuously.
    """
    def __init__(self, runtime, backend, *, generation, boot_id, authorize, now=None, elapsed=None):
        uuid_value(generation); uuid_value(boot_id)
        self.runtime,self.backend,self.generation,self.boot_id = runtime,backend,generation,boot_id
        self.authorize = authorize  # Controller-owned full M3 authorization, not wire data.
        self.now = now or (lambda:datetime.now(timezone.utc))
        self.elapsed = elapsed or (lambda:time.clock_gettime(time.CLOCK_BOOTTIME))
        self.deadlines = {}

    def _validate(self, launch):
        if self.runtime.launch(launch['launch_id']) != launch:
            raise AuthorityError('Launch state changed before release.')
        if launch['supervisor_generation']!=self.generation or launch['boot_id']!=self.boot_id:
            raise AuthorityError('Stale launch generation/boot.')
        runtime = self.runtime.runtime(launch['execution_id'])
        if runtime['revoked'] or runtime['authority_revision']!=launch['authority_revision']:
            raise AuthorityError('Authority changed.')
        leases = self.runtime.required_leases(launch['execution_id'])
        if ([asdict(l) for l in leases] != parse_json(launch['binding'])['required_leases'] or
                any(l.revoked or not l.held or l.execution_id!=launch['execution_id'] or
                    l.fencing_epoch!=runtime['fencing_epoch'] or self.now()>=timestamp(l.expires_at)
                    for l in leases)):
            raise AuthorityError('Required lease changed or expired.')
        record = self.authorize(launch['execution_id'],launch['request_id'])
        if record.authorization_digest!=launch['authorization_digest'] or self.now()>=timestamp(launch['deadline']):
            raise AuthorityError('Launch authority/expiry mismatch.')
        return record

    def prepare(self, launch_id):
        launch = self.runtime.launch(launch_id)
        try:
            elapsed, now = self.elapsed(), self.now()
            record = self._validate(launch)
            launch = self.runtime.transition(launch_id,launch['revision'],'PREPARING')
            deadline = ExecutionDeadline.arm(launch['deadline'],now=now,elapsed=elapsed,
                                             timeout_seconds=record.timeout_seconds)
            if record.elapsed_deadline is not None:
                deadline = replace(deadline,elapsed_deadline=min(deadline.elapsed_deadline,record.elapsed_deadline))
            if deadline.expired(now=self.now(),elapsed=self.elapsed()):
                raise AuthorityError('Expired before preparation.')
            self.deadlines[launch_id] = deadline
            self.backend.arm_deadline(launch_id,self.deadlines[launch_id])
            process = self.backend.prepare(launch,record)
            # Backend returns only after namespace/FD/capability verification, payload still gated.
            self._validate(launch)
            return self.runtime.transition(launch_id,launch['revision'],'PREPARED',process=process)
        except BaseException:
            self.stop(launch_id,'SETUP_FAILED')
            raise

    def release(self, launch_id):
        launch = self.runtime.launch(launch_id)
        try:
            self._validate(launch)
            if launch_id not in self.deadlines or self.deadlines[launch_id].expired(now=self.now(),elapsed=self.elapsed()):
                raise AuthorityError('Release deadline unavailable/expired.')
            launch = self.runtime.transition(launch_id,launch['revision'],'RELEASE_PENDING')
            # Hold the SQLite writer transaction through exact authority validation and send.
            # This orders revoke vs release; it DOES NOT make OS execution transactional.
            with self.runtime.transaction('release'):
                record = self._validate(launch)
                if self.deadlines[launch_id].expired(now=self.now(),elapsed=self.elapsed()):
                    raise AuthorityError('Expired before release.')
                self.backend.release(launch,record)
            # An exception/lost acknowledgement is ambiguous and is never retried.
            return self.runtime.transition(launch_id,launch['revision'],'RUNNING')
        except BaseException:
            self.stop(launch_id,'INTERRUPTED')
            raise

    def stop(self, launch_id, reason):
        launch = self.runtime.launch(launch_id)
        if launch['state']=='TERMINAL':
            return launch
        if launch['state']!='STOPPING':
            launch = self.runtime.transition(launch_id,launch['revision'],'STOPPING',reason=reason)
        self.backend.kill(launch)
        if self.backend.empty(launch) is True:
            exit_code=self.backend.finish(launch)
            self.deadlines.pop(launch_id,None)
            return self.runtime.transition(launch_id,launch['revision'],'TERMINAL',cleanup=True,exit_code=exit_code)
        return launch

    def poll(self, launch_id, *, controller_alive=True, cancelled=False):
        launch = self.runtime.launch(launch_id)
        if launch['state']=='TERMINAL':
            return launch
        runtime = self.runtime.runtime(launch['execution_id'])
        reason = None
        if not controller_alive:
            reason = 'INTERRUPTED'
        elif cancelled:
            reason = 'CANCELLED'
        elif runtime['revoked'] or runtime['authority_revision']!=launch['authority_revision']:
            reason = 'REVOKED'
        elif launch['state']!='REGISTERED' and (launch_id not in self.deadlines or self.deadlines[launch_id].expired(now=self.now(),elapsed=self.elapsed())):
            reason = 'TIMEOUT'
        elif self.backend.exited(launch):
            reason = 'EXITED'
        if reason is None and launch['state'] not in {'REGISTERED','STOPPING'}:
            try:
                self._validate(launch)
            except (AuthorityError,ValidationError):
                reason = 'REVOKED'
        if launch['state']=='STOPPING':
            reason = launch['reason']
        return self.stop(launch_id,reason) if reason else launch

    def reconcile(self):
        """Fresh supervisor startup kills ALL unfinished known attempts, never resumes."""
        result = []
        for row in self.runtime.db.execute("SELECT launch_id FROM launch_attempts WHERE state!='TERMINAL'").fetchall():
            result.append(self.stop(row[0],'INTERRUPTED'))
        # Backend enumerates ONLY its pinned delegated subtree. Unknown survivors
        # must be terminated; missing/inaccessible evidence is not emptiness.
        if self.backend.reconcile_unknown() is not True:
            raise AuthorityError('Unknown supervisor descendants remain.')
        return [self.stop(row['launch_id'],'INTERRUPTED') if row['state']!='TERMINAL' else row for row in result]


class SyntheticProcessBackend:
    """Deterministic tests only; never writes the host cgroup tree or launches code."""
    def __init__(self, process):
        self.process = process
        self.children, self.armed, self.releases = {}, {}, []
        self.fail_setup = False
        self.cleanup_known = True
        self.acknowledge = True
        self.before_ready = None

    def service_deadlines(self, *, now, elapsed):
        for launch_id, deadline in self.armed.items():
            if deadline.expired(now=now,elapsed=elapsed) and self.cleanup_known:
                self.children.pop(launch_id,None)

    def arm_deadline(self, launch_id, deadline):
        self.armed[launch_id] = deadline

    def prepare(self, launch, record):
        self.children[launch['launch_id']] = {'alive':True,'descendants':1,'exited':False}
        if self.fail_setup:
            raise AuthorityError('Synthetic setup failure.')
        if self.before_ready:
            self.before_ready()
        return self.process

    def release(self, launch, record):
        self.releases.append(launch['launch_id'])
        if not self.acknowledge:
            raise AuthorityError('Synthetic lost acknowledgement.')

    def kill(self, launch):
        if self.cleanup_known:
            self.children.pop(launch['launch_id'],None)

    def empty(self, launch):
        return self.cleanup_known and launch['launch_id'] not in self.children

    def exited(self, launch):
        return self.children.get(launch['launch_id'],{}).get('exited',False)

    def reconcile_unknown(self):
        if self.cleanup_known:
            self.children.clear()
        return self.cleanup_known

    def finish(self, launch):
        if not self.empty(launch):
            raise AuthorityError('Synthetic cleanup uncertain.')
        self.armed.pop(launch['launch_id'],None)
        return None


def run_supervisor_loop(supervisor, *, next_request, controller_alive, notify_watchdog, shutdown):
    """Installed service driver; next_request must return within its supplied timeout.

    IPC parsing/enrollment precedes this boundary. No sockets/services are created by
    this function. All unfinished launches are reconciled before accepting requests.
    A database failure never converts into permission to keep running workers.
    """
    supervisor.reconcile()
    try:
        while not shutdown():
            supervisor.backend.service_deadlines(now=supervisor.now(),elapsed=supervisor.elapsed())
            rows=supervisor.runtime.db.execute("SELECT launch_id FROM launch_attempts WHERE state!='TERMINAL'").fetchall()
            for row in rows:
                supervisor.poll(row[0],controller_alive=controller_alive())
            request=next_request(timeout=.1)
            if request is not None:
                launch_id,action=request['launch_id'],request['action']
                if action=='PREPARE':
                    supervisor.prepare(launch_id)
                elif action=='RELEASE':
                    supervisor.release(launch_id)
                elif action=='CANCEL':
                    supervisor.stop(launch_id,'CANCELLED')
                elif action!='STATUS':
                    raise AuthorityError('Unknown supervisor action.')
            notify_watchdog()
    finally:
        # Even DB failure must invoke the independent OS cleanup backstop.
        if supervisor.backend.reconcile_unknown() is not True:
            raise AuthorityError('Supervisor shutdown cleanup uncertain.')
