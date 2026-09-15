"""Trusted, single-threaded routing foundation; synthetic supervisor only.

Injected state/enrollment/audit providers are trusted controller dependencies,
never model data. This module does not activate agents or launch OS processes.
"""
from dataclasses import asdict, dataclass, replace
import os
import time
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from .confinement import ConfinementProfile, TaskRoot, safe_relative
from .identity import PeerIdentity, ProcessIdentity, WorkerIdentity
from .paths import PathRule, contained_by
from .protocol import ModelProposal, Operation
from .records import ExecutionGrant, Task
from .schema import document, timestamp, validate_schema
from .serialization import canonical_json, digest, parse_json
from .types import AuthorityError, ValidationError

EVENTS = frozenset({'MODEL_PROPOSAL_RECEIVED', 'OPERATION_AUTHORIZED', 'OPERATION_DENIED',
                   'CONFINEMENT_SETUP_STARTED', 'CONFINEMENT_SETUP_FAILED', 'WORKER_STARTED', 'WORKER_EXITED'})


class RoutingDenied(AuthorityError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class RoutingEvent:
    event_type: str
    correlation_id: str
    reason_code: str

    def __post_init__(self):
        if self.event_type not in EVENTS or self.reason_code not in {
            'RECEIVED', 'AUTHORIZED', 'SETUP', 'SETUP_FAILED', 'STARTED', 'EXITED',
            'INVALID_PROPOSAL', 'IDENTITY', 'GRANT', 'EXPIRED', 'REVOKED', 'FENCING',
            'SPEC', 'PROFILE', 'PATH', 'OPERATION', 'RESERVATION', 'REPLAY', 'CANCELLED',
            'AUTHORITY_CHANGED'}:
            raise ValidationError('Invalid routing audit event.')


@dataclass(frozen=True)
class Enrollment:
    """Controller-created connection binding, not a payload credential."""
    peer: PeerIdentity
    process: ProcessIdentity
    execution_id: str


@dataclass(frozen=True)
class CommandPolicy:
    command_id: str
    operation: Operation
    argv: tuple
    required_reservations: tuple = ()

    def __post_init__(self):
        if type(self.argv) is not tuple or not self.argv or any(type(v) is not str or not v or '\0' in v for v in self.argv):
            raise ValidationError('Fixed argv required.')
        if not self.argv[0].startswith('/usr/bin/') or '/' in self.argv[0][len('/usr/bin/'):]:
            raise ValidationError('Fixed runtime executable required.')
        if type(self.required_reservations) is not tuple or type(self.operation) is not Operation:
            raise ValidationError('Invalid command policy.')


@dataclass(frozen=True)
class RequiredLease:
    """Exact durable authority including the canonical granted Reservation record."""
    resource_key: str
    execution_id: str
    fencing_epoch: int
    expires_at: str
    revision: int
    held: bool
    revoked: bool
    resource_json: str

    def __post_init__(self):
        if (type(self.resource_key) is not str or not self.resource_key or
                type(self.execution_id) is not str or not self.execution_id or
                any(type(v) is not int or v < 1 for v in (self.fencing_epoch, self.revision)) or
                type(self.held) is not bool or type(self.revoked) is not bool):
            raise ValidationError('Invalid required lease authority.')
        timestamp(self.expires_at)
        resource = parse_json(self.resource_json)
        validate_schema('Reservation', resource)
        if (canonical_json(resource)!=self.resource_json or resource['reservation_id']!=self.resource_key or
                resource['owner_execution']!=self.execution_id or resource['fencing_epoch']!=self.fencing_epoch or
                timestamp(self.expires_at)>timestamp(resource['lease_expires_at'])):
            raise ValidationError('Lease resource binding mismatch.')


@dataclass(frozen=True)
class ExecutionBinding:
    grant: ExecutionGrant
    task: Task
    worker: WorkerIdentity
    execution_process: ProcessIdentity
    root: TaskRoot
    profile: ConfinementProfile
    profile_digest: str
    commands: tuple = ()
    active: bool = True
    revoked: bool = False
    fencing_epoch: int = 1
    active_reservations: frozenset = frozenset()
    repository_identity: tuple | None = None
    authority_revision: int = 0  # Store increments on every authority transition, including revoke/restore.
    required_leases: tuple = ()


class ExecutionStore(Protocol):
    def load(self, execution_id) -> ExecutionBinding: ...


@dataclass(frozen=True)
class LaunchRecord:
    """Controller-produced description, never a bearer authorization token."""
    operation: Operation
    argv: tuple
    cwd: str
    environment: tuple
    timeout_seconds: float
    output_bytes: int
    profile_digest: str
    worker: WorkerIdentity
    payload_json: str
    authorization_digest: str
    expires_at: str
    inherited_fds: tuple = ()
    shell: bool = False
    elapsed_deadline: float | None = None  # CLOCK_BOOTTIME, same boot as process binding.

    def __post_init__(self):
        if type(self.argv) is not tuple or not self.argv or self.shell is not False or self.inherited_fds != ():
            raise ValidationError('Unsafe launch record.')
        if self.environment != ConfinementProfile().environment() or self.cwd != '/work':
            raise ValidationError('Unsafe launch environment.')


@dataclass(frozen=True)
class LaunchResult:
    status: str
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    truncated: bool

    @classmethod
    def bounded(cls, status, stdout=b'', stderr=b'', *, limit=65536, exit_code=None):
        if status not in {'EXITED', 'TIMED_OUT', 'CANCELLED'} or type(stdout) is not bytes or type(stderr) is not bytes:
            raise ValidationError('Invalid worker result.')
        if type(limit) is not int or not 1 <= limit <= 1048576:
            raise ValidationError('Invalid output limit.')
        return cls(status, exit_code, stdout[:limit], stderr[:limit], len(stdout) > limit or len(stderr) > limit)


class Cancellation:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class LaunchSupervisor(Protocol):
    def record_stage(self, stage): ...
    def prepare(self, record): ...
    def abort(self, handle): ...
    def execute(self, handle, cancellation, release) -> LaunchResult: ...


class SyntheticLaunchSupervisor:
    """A simulation: no subprocess or actual file operation exists here.

    before_ready is a trusted test injection point, never model-controlled code.
    Duration, output and setup failure let tests exercise supervision outcomes
    without execution, credentials, worker UIDs or network access.
    """
    def __init__(self, *, fail_setup=False, before_ready=None, duration=0, stdout=b'', stderr=b''):
        self.fail_setup = fail_setup
        self.before_ready = before_ready
        self.duration = duration
        self.stdout, self.stderr = stdout, stderr
        self.trace = []
        self.records = []
        self._prepared = {}

    def record_stage(self, stage):
        self.trace.append(stage)

    def prepare(self, record):
        self.trace.append('CONFINEMENT_SETUP')
        if self.fail_setup:
            raise RoutingDenied('SETUP_FAILED')
        if self.before_ready:
            self.before_ready()
        handle = object()
        self._prepared[handle] = record
        return handle

    def abort(self, handle):
        self._prepared.pop(handle, None)
        self.trace.append('ABORT')

    def execute(self, handle, cancellation, release):
        prepared = self._prepared[handle]
        # No callbacks, I/O or setup after this controller-owned release gate.
        record = release(prepared)
        self._prepared.pop(handle)  # exactly one use; failure leaves handle for abort
        if cancellation.cancelled:
            return LaunchResult.bounded('CANCELLED', limit=record.output_bytes)
        self.trace.append('EXEC')
        self.records.append(record)
        status = 'TIMED_OUT' if self.duration > record.timeout_seconds else 'EXITED'
        return LaunchResult.bounded(status, self.stdout, self.stderr, limit=record.output_bytes,
                                    exit_code=0 if status == 'EXITED' else None)


class Controller:
    """One synchronous request at a time. No durable runtime is enabled yet."""
    def __init__(self, store, enrollments, supervisor, audit, *, clock=None, process_reader=None, elapsed=None):
        self.store = store
        self.enrollments = tuple(enrollments)
        self.supervisor = supervisor
        self.audit = audit
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.process_reader = process_reader
        self.elapsed = elapsed or (lambda: time.clock_gettime(time.CLOCK_BOOTTIME))
        self._deadlines = {}
        self._lease_deadlines = {}
        self._grant_deadlines = {}
        self._used = set()
        self._issued = {}

    def _event(self, kind, correlation, reason):
        self.audit(RoutingEvent(kind, correlation, reason))

    def _check(self, enrollment, proposal):
        # Sample elapsed first: validation work must consume, never extend, authority.
        started_elapsed, started_at = self.elapsed(), self.clock()
        if type(enrollment) is not Enrollment:
            raise RoutingDenied('IDENTITY')
        if not any(enrollment is e for e in self.enrollments) or enrollment.peer.pid != enrollment.process.pid:
            raise RoutingDenied('IDENTITY')
        try:
            enrollment.process.verify(self.process_reader)
        except AuthorityError:
            raise RoutingDenied('IDENTITY') from None
        if proposal.execution_id != enrollment.execution_id:
            raise RoutingDenied('GRANT')
        try:
            binding = self.store.load(enrollment.execution_id)
        except (KeyError, LookupError):
            raise RoutingDenied('GRANT') from None
        grant, task = binding.grant, binding.task
        if grant['execution_id'] != enrollment.execution_id or grant['agent_id'] != binding.worker.agent_id or grant['role'] != binding.worker.role.value:
            raise RoutingDenied('IDENTITY')
        if not binding.active or binding.revoked:
            raise RoutingDenied('REVOKED')
        grant_key=digest(grant.to_dict())
        grant_deadline=started_elapsed+(timestamp(grant['expires_at'])-started_at).total_seconds()
        grant_deadline=min(grant_deadline,self._grant_deadlines.get(grant_key,grant_deadline))
        self._grant_deadlines[grant_key]=grant_deadline
        if self.clock() >= timestamp(grant['expires_at']) or self.elapsed()>=grant_deadline:
            self._grant_deadlines[grant_key]=min(grant_deadline,self.elapsed())
            raise RoutingDenied('EXPIRED')
        if grant['fencing_epoch'] != binding.fencing_epoch:
            raise RoutingDenied('FENCING')
        try:
            grant.assert_task_binding(task)
        except (AuthorityError, ValidationError):
            raise RoutingDenied('SPEC') from None
        if task['state'] not in {'ASSIGNED', 'IN_PROGRESS', 'QA_REVIEW'}:
            raise RoutingDenied('SPEC')
        proc = binding.execution_process
        if grant['boot_id'] != proc.boot_id or grant['process_start_identity'] != str(proc.start_ticks) or grant['process_scope'] != f'pid:{proc.pid}':
            raise RoutingDenied('IDENTITY')
        try:
            proc.verify(self.process_reader)
        except AuthorityError:
            raise RoutingDenied('IDENTITY') from None
        if grant['worktree'] != binding.root.path or binding.profile.profile_digest != binding.profile_digest:
            raise RoutingDenied('PROFILE')
        required = set(grant['reserved_resources'])
        if not required <= binding.active_reservations:
            raise RoutingDenied('RESERVATION')
        leases = binding.required_leases
        if (type(leases) is not tuple or any(type(l) is not RequiredLease for l in leases) or
                len(leases) != len(required) or {l.resource_key for l in leases} != required or
                any(l.execution_id != enrollment.execution_id or l.fencing_epoch != binding.fencing_epoch or
                    not l.held or l.revoked or parse_json(l.resource_json)['owner_task']!=task['task_id'] or
                    parse_json(l.resource_json)['status']!='ACTIVE' for l in leases)):
            raise RoutingDenied('RESERVATION')
        expiry = min([timestamp(grant['expires_at']), *(timestamp(l.expires_at) for l in leases)])
        lease_deadlines=[]
        for lease in leases:
            key=digest(asdict(lease))
            deadline=started_elapsed+(timestamp(lease.expires_at)-started_at).total_seconds()
            deadline=min(deadline,self._lease_deadlines.get(key,deadline))
            self._lease_deadlines[key]=deadline
            lease_deadlines.append(deadline)
        if any(started_elapsed>=d for d in lease_deadlines):
            raise RoutingDenied('EXPIRED')
        try:
            binding.root.verify()
            protected = tuple(PathRule.from_dict(p) for p in document('policy.json')['protected_paths'])
            readable = tuple(PathRule.from_dict(p) for p in grant['can_read'])
            writable = tuple(PathRule.from_dict(p) for p in grant['can_write'])
            task_denied = tuple(PathRule.from_dict(p) for p in task['forbidden_paths'])
            task_readonly = tuple(PathRule.from_dict(p) for p in task['read_only_paths'])
            def permitted(path, write=False):
                safe_relative(path)
                deny = (*protected, *task_denied, *(task_readonly if write else ()))
                if any(p.matches(path) for p in deny) or not any(p.matches(path) for p in (writable if write else readable)):
                    raise RoutingDenied('PATH')
            # A mount must not expose a broader directory than the grant, even for command execution.
            for paths, rules, write in ((binding.profile.readable_paths, readable, False),
                                         (binding.profile.writable_paths, writable, True)):
                for path in paths:
                    for entry, kind in binding.root.export_entries(path):
                        permitted(entry, write)
                        if write:
                            permitted(entry, False)
                        if not any(contained_by(PathRule(kind, entry), rule) for rule in rules):
                            raise RoutingDenied('PATH')
            args = proposal.arguments
            if 'path' in args:
                write = proposal.operation in {Operation.WRITE_FILE, Operation.APPLY_PATCH}
                permitted(args['path'], write)
                mounts = binding.profile.writable_paths if write else binding.profile.readable_paths + binding.profile.writable_paths
                if not any(args['path'] == p or args['path'].startswith(p + '/') for p in mounts):
                    raise RoutingDenied('PATH')
                binding.root.inspect(args['path'], create=write)
        except (ValidationError, OSError):
            raise RoutingDenied('PATH') from None
        if proposal.operation == Operation.GIT_COMMIT_LOCAL:
            if not grant['can_commit_local'] or binding.profile.git_metadata != 'commit':
                raise RoutingDenied('OPERATION')
        elif binding.profile.git_metadata == 'commit':
            raise RoutingDenied('PROFILE')
        if proposal.operation in {Operation.GIT_STATUS, Operation.GIT_DIFF, Operation.GIT_COMMIT_LOCAL}:
            if binding.profile.git_metadata == 'hidden':
                raise RoutingDenied('PROFILE')
            try:
                fd = binding.root.open_read('.git', git=True)
                try:
                    if binding.repository_identity != TaskRoot._identity(os.fstat(fd)):
                        raise RoutingDenied('PATH')
                finally:
                    os.close(fd)
            except (ValidationError, OSError):
                raise RoutingDenied('PATH') from None
        command_id = args.get('command_id', proposal.operation.value)
        policies = [c for c in binding.commands if c.command_id == command_id and c.operation == proposal.operation]
        if len(policies) != 1:
            raise RoutingDenied('OPERATION')
        command = policies[0]
        if proposal.operation == Operation.RUN_COMMAND and tuple(args['argv']) != command.argv:
            raise RoutingDenied('OPERATION')
        if not set(command.required_reservations) <= (binding.active_reservations & required):
            raise RoutingDenied('RESERVATION')
        authorization = self._snapshot(binding, enrollment, command)
        # Reload after potentially slow filesystem validation: do not use stale store state.
        try:
            latest = self.store.load(enrollment.execution_id)
        except (KeyError, LookupError):
            raise RoutingDenied('GRANT') from None
        if self._snapshot(latest, enrollment, command) != authorization:
            raise RoutingDenied('AUTHORITY_CHANGED')
        key = (enrollment.execution_id, proposal.request_id)
        deadline = started_elapsed + min(binding.profile.timeout_seconds, (expiry-started_at).total_seconds())
        deadline = min([deadline,grant_deadline,*lease_deadlines])
        # A repeated recheck, including after wall-clock rollback, cannot re-arm.
        deadline = min(deadline, self._deadlines.get(key, deadline))
        self._deadlines[key] = deadline
        final_now, final_elapsed = self.clock(), self.elapsed()
        remaining = min((expiry-final_now).total_seconds(), deadline-final_elapsed)
        if remaining <= 0:
            # Latch observed absolute expiry too: a later UTC rollback cannot revive it.
            if final_now>=timestamp(grant['expires_at']):
                self._grant_deadlines[grant_key]=min(grant_deadline,final_elapsed)
            for lease in leases:
                if final_now>=timestamp(lease.expires_at):
                    key=digest(asdict(lease))
                    self._lease_deadlines[key]=min(self._lease_deadlines[key],final_elapsed)
            raise RoutingDenied('EXPIRED')
        # Payload travels through a bounded pipe in a future helper, never a shell.
        return LaunchRecord(proposal.operation, command.argv, '/work', binding.profile.environment(),
                            min(binding.profile.timeout_seconds, remaining), binding.profile.output_bytes,
                            binding.profile_digest, binding.worker, proposal.arguments_json,
                            authorization, expiry.isoformat(), elapsed_deadline=deadline)

    @staticmethod
    def _snapshot(binding, enrollment, command):
        """Digest trusted state using the existing canonical JSON format, not model claims.

        Full validated records avoid duplicating M1/M2 authority field selection.
        The store revision detects change-and-restore (ABA) between observations.
        """
        if type(binding.authority_revision) is not int or binding.authority_revision < 0:
            raise RoutingDenied('AUTHORITY_CHANGED')
        return digest({
            'version': 1, 'grant': binding.grant.to_dict(), 'task': binding.task.to_dict(),
            'worker': [binding.worker.agent_id, binding.worker.role.value, binding.worker.username,
                       binding.worker.uid, binding.worker.gid],
            'caller': [enrollment.execution_id, enrollment.peer.uid, enrollment.peer.gid,
                       enrollment.peer.pid, enrollment.process.boot_id, enrollment.process.start_ticks],
            'process': [binding.execution_process.boot_id, binding.execution_process.pid,
                        binding.execution_process.start_ticks],
            'workspace': [binding.root.path, list(binding.root.identity)],
            'repository': None if binding.repository_identity is None else list(binding.repository_identity),
            'profile': binding.profile.profile_digest, 'configured_profile': binding.profile_digest,
            'environment': [list(pair) for pair in binding.profile.environment()],
            'active': binding.active, 'revoked': binding.revoked, 'revision': binding.authority_revision,
            'fence': binding.fencing_epoch, 'reservations': sorted(binding.active_reservations),
            'leases': [asdict(l) for l in sorted(binding.required_leases, key=lambda l:l.resource_key)],
            'command': [command.command_id, command.operation.value, list(command.argv),
                        list(command.required_reservations)],
            'commands': [[c.command_id, c.operation.value, list(c.argv), list(c.required_reservations)]
                         for c in binding.commands],
        })

    def dispatch(self, raw, enrollment, *, cancellation=None):
        correlation = str(uuid4())  # never trust model text for audit fields
        self._event('MODEL_PROPOSAL_RECEIVED', correlation, 'RECEIVED')
        handle = None
        ticket = None
        try:
            try:
                proposal = ModelProposal.parse(raw)
            except ValidationError:
                raise RoutingDenied('INVALID_PROPOSAL') from None
            if type(enrollment) is not Enrollment:
                raise RoutingDenied('IDENTITY')
            replay_key = (enrollment.execution_id, proposal.request_id)
            if replay_key in self._used or len(self._used) >= 1024:
                raise RoutingDenied('REPLAY')
            self._used.add(replay_key)
            record = self._check(enrollment, proposal)
            self._event('OPERATION_AUTHORIZED', correlation, 'AUTHORIZED')
            self.supervisor.record_stage('AUTHORIZATION')
            ticket = object()
            self._issued[ticket] = record
            self._event('CONFINEMENT_SETUP_STARTED', correlation, 'SETUP')
            if self.clock() >= timestamp(record.expires_at):
                raise RoutingDenied('EXPIRED')
            try:
                handle = self.supervisor.prepare(record)
            except Exception:
                self._event('CONFINEMENT_SETUP_FAILED', correlation, 'SETUP_FAILED')
                raise RoutingDenied('SETUP_FAILED') from None
            self.supervisor.record_stage('FINAL_AUTHORITY_RECHECK')
            issued = self._issued.pop(ticket)
            cancel = cancellation or Cancellation()
            if cancel.cancelled:
                raise RoutingDenied('CANCELLED')
            self._event('WORKER_STARTED', correlation, 'STARTED')

            def release(prepared):
                if prepared is not issued:
                    raise RoutingDenied('AUTHORITY_CHANGED')
                current = self._check(enrollment, proposal)
                # Time may only shorten the timeout; it is not an authority change.
                if replace(current, timeout_seconds=issued.timeout_seconds,
                           elapsed_deadline=issued.elapsed_deadline) != issued:
                    raise RoutingDenied('AUTHORITY_CHANGED')
                if cancel.cancelled:
                    raise RoutingDenied('CANCELLED')
                remaining = min((timestamp(issued.expires_at) - self.clock()).total_seconds(),
                                issued.elapsed_deadline-self.elapsed())
                if remaining <= 0:
                    raise RoutingDenied('EXPIRED')
                return replace(current, timeout_seconds=min(issued.timeout_seconds,
                                                            current.timeout_seconds, remaining))

            result = self.supervisor.execute(handle, cancel, release)
            handle = None
            self._event('WORKER_EXITED', correlation, 'EXITED')
            return result
        except RoutingDenied as error:
            self._event('OPERATION_DENIED', correlation, error.reason)
            raise
        finally:
            if ticket is not None:
                self._issued.pop(ticket, None)
            if handle is not None:
                self.supervisor.abort(handle)
