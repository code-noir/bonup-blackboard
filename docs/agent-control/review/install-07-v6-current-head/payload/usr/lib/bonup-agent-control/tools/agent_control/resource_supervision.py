"""Block 3 contracts and deterministic backend. No privileged operations.

HOST_TEST_REQUIRED: the installed timer driver must service DeadlineScheduler on
an independent timerfd/BOOTTIME lane, never on a blocking request/output handler.
The synthetic backend below models effects; it is not a Linux execution backend.
"""
from dataclasses import asdict, dataclass
import math

from .identity import ProcessIdentity
from .integration_policy import IntegrationPolicy
from .protocol import uuid_value
from .release_gate import FixedPayload
from .serialization import canonical_json, digest
from .supervisor import ExecutionDeadline, SyntheticProcessBackend
from .types import AuthorityError, ValidationError


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError('Finite elapsed time required.')
    return value


def authority_deadline(grant, leases, *, now, elapsed, operation_seconds,
                       operation_elapsed=None, policy=IntegrationPolicy(), original=None):
    """Compose absolute validity with elapsed ceilings; replacement cannot extend."""
    finite(elapsed); finite(operation_seconds)
    if type(policy) is not IntegrationPolicy or type(leases) is not tuple:
        raise ValidationError('Immutable resource/deadline policy required.')
    values = [ExecutionDeadline.arm(expiry, now=now, elapsed=elapsed,
              timeout_seconds=min(operation_seconds, policy.duration_seconds))
              for expiry in (grant, *leases)]
    wall = min(d.expires_at for d in values)
    deadline = min(d.elapsed_deadline for d in values)
    if operation_elapsed is not None:
        deadline = min(deadline, finite(operation_elapsed))
    if original is not None:
        wall = min(wall, original.expires_at)
        deadline = min(deadline, original.elapsed_deadline)
    result = ExecutionDeadline(wall, deadline)
    if result.expired(now=now, elapsed=elapsed):
        raise AuthorityError('No remaining execution authority.')
    return result


class DeadlineScheduler:
    """One-use timer registrations, driven independently of IPC and pipe polling.

    Callbacks must be bounded whole-cgroup termination requests, not waiting for
    exit/SQLite/output. Failed delivery remains observable and is retried; expired
    registration can never be armed again, including after wall-clock rollback.
    """
    def __init__(self, now, elapsed):
        self.now, self.elapsed = now, elapsed
        self.entries, self.consumed = {}, set()

    def arm(self, launch_id, deadline, stop):
        uuid_value(launch_id)
        if self.entries or launch_id in self.consumed or len(self.consumed) >= 4096:
            raise AuthorityError('Timer replay/capacity.')
        if type(deadline) is not ExecutionDeadline or not callable(stop):
            raise ValidationError('Trusted timer registration required.')
        finite(deadline.elapsed_deadline)
        if deadline.expired(now=self.now(), elapsed=self.elapsed()):
            raise AuthorityError('Expired timer registration.')
        self.entries[launch_id] = (deadline, stop)

    def shorten(self, launch_id, deadline):
        old, stop = self.entries[launch_id]
        if deadline.expires_at > old.expires_at or deadline.elapsed_deadline > old.elapsed_deadline:
            raise AuthorityError('Authority deadline cannot extend.')
        finite(deadline.elapsed_deadline)
        self.entries[launch_id] = (deadline, stop)

    def cancel(self, launch_id):
        self.entries.pop(launch_id, None)
        self.consumed.add(launch_id)

    def service(self):
        for key, (deadline, stop) in tuple(self.entries.items()):
            if key in self.consumed or deadline.expired(now=self.now(), elapsed=self.elapsed()):
                self.consumed.add(key)
                stop()  # Delivery failure must propagate; never mistaken for cleanup.
                self.entries.pop(key, None)


@dataclass(frozen=True)
class BackendPlan:
    launch_id: str
    generation: str
    boot_id: str
    worker: tuple
    profile_digest: str
    cgroup: str
    cgroup_values: tuple
    rlimits: tuple
    bwrap_argv: tuple
    pass_fds: tuple
    fixed_payload: FixedPayload
    resource_json: str
    steps: tuple = ('VERIFY_ENROLLMENT', 'PIN_EXPORTS', 'PLACE_CGROUP', 'CLEAR_GROUPS',
        'SET_GID', 'SET_UID', 'DROP_ALL_CAPABILITIES', 'NO_NEW_PRIVS', 'CLEAN_ENV',
        'CLOSE_FDS', 'BWRAP', 'GATE_READY', 'FINAL_AUTHORITY', 'ONE_USE_RELEASE', 'EXEC')

    @property
    def plan_digest(self):
        return digest(asdict(self))


def build_plan(launch, record, handle, *, config_fd, release_fd, policy=IntegrationPolicy()):
    """Supervisor-local arguments only. FDs never come from protocol fields.

    Backend must seal config containing fixed_payload and ExpectedRelease, close
    pins after bwrap setup and close configuration/release FDs before payload exec.
    """
    if type(policy) is not IntegrationPolicy:
        raise ValidationError('Installed integration policy required.')
    policy.validate_record(record)
    candidates = {'ARCH-01': ('bonup-arch01', 3001), 'FE-01': ('bonup-fe01', 3002),
                  'BE-01': ('bonup-be01', 3003), 'QA-01': ('bonup-qa01', 3004)}
    worker = record.worker
    if candidates.get(worker.agent_id) != (worker.username, worker.uid) or worker.gid != worker.uid:
        raise AuthorityError('Exact candidate worker enrollment required.')
    for key in ('launch_id', 'supervisor_generation', 'boot_id'): uuid_value(launch[key])
    if any(type(fd) is not int or fd < 3 for fd in (config_fd, release_fd)) or config_fd == release_fd:
        raise ValidationError('Distinct supervisor-local gate descriptors required.')
    pins = handle.pass_fds
    if config_fd in pins or release_fd in pins:
        raise AuthorityError('Gate descriptor aliases mount pin.')
    if handle.mapping.profile.profile_digest != record.profile_digest:
        raise AuthorityError('Pinned profile differs from authorization.')
    profile = handle.mapping.profile
    if (profile.memory_bytes, profile.process_limit, profile.cpu_seconds,
            profile.timeout_seconds, profile.output_bytes) != (policy.memory_bytes,
            policy.processes, policy.cpu_seconds, policy.duration_seconds, policy.stdout_bytes):
        raise AuthorityError('Confinement and integration resource policies disagree.')
    if handle.mapping.object_identity[2:] != (worker.uid, worker.gid):
        raise AuthorityError('Pinned workspace owner differs from enrollment.')
    payload = FixedPayload(record.argv, record.environment, record.cwd)
    gate = FixedPayload(('/usr/bin/python3', '-I', '/usr/lib/bonup-agent-control/gate_entry.py',
                         str(config_fd), str(release_fd)), record.environment, record.cwd)
    argv = handle.argv(launch['launch_id'], gate)
    return BackendPlan(launch['launch_id'], launch['supervisor_generation'], launch['boot_id'],
        (worker.uid, worker.gid, (), (), True), policy.policy_digest,
        'generation-' + launch['supervisor_generation'] + '/launch-' + launch['launch_id'],
        (('memory.max', str(policy.memory_bytes)), ('memory.swap.max', '0'),
         ('pids.max', str(policy.processes)), ('cpu.max', f'{policy.cpu_quota_us} {policy.cpu_period_us}')),
        (('NOFILE', policy.open_fds), ('FSIZE', policy.file_bytes), ('CORE', 0), ('CPU', policy.cpu_seconds)),
        argv, (*pins, config_fd, release_fd), payload, canonical_json(asdict(policy)))


class OutputCollector:
    """Nonblocking pipe adapter feeds at most 16 KiB per ready-stream event.

    Retain a fixed prefix, discard overflow, keep draining both streams. No reads,
    waits or callbacks here. Counts saturate; hostile output cannot grow state.
    """
    def __init__(self, policy=IntegrationPolicy(), *, limit=None):
        if type(policy) is not IntegrationPolicy: raise ValidationError('Immutable output policy required.')
        if limit is not None and (type(limit) is not int or not 0 < limit <= min(policy.stdout_bytes,policy.stderr_bytes)):
            raise ValidationError('Authorized output ceiling required.')
        self.limits = {'stdout': policy.stdout_bytes if limit is None else limit,
                       'stderr': policy.stderr_bytes if limit is None else limit}
        self.buffers = {key: bytearray() for key in self.limits}
        self.truncated = {key: False for key in self.limits}

    def feed(self, stream, chunk):
        if stream not in self.buffers or type(chunk) is not bytes or len(chunk) > 16384:
            raise ValidationError('Bounded pipe event required.')
        room = self.limits[stream] - len(self.buffers[stream])
        self.buffers[stream].extend(chunk[:room])
        self.truncated[stream] |= len(chunk) > room

    def evidence(self):
        return {key: dict(retained=len(value), truncated=self.truncated[key])
                for key, value in self.buffers.items()}


class ResourceBackend(SyntheticProcessBackend):
    """Deterministic enforcement model only: HOST_TEST_REQUIRED for every OS effect."""
    def __init__(self, process, scheduler, *, policy=IntegrationPolicy(), gate_fds=None):
        super().__init__(process)
        if type(process) is not ProcessIdentity or type(policy) is not IntegrationPolicy:
            raise ValidationError('Trusted process/resource policy required.')
        self.scheduler, self.policy = scheduler, policy
        self.gate_fds, self.plans = gate_fds, {}
        self.output, self.exit_codes, self.stop_requested, self.cpu_used = {}, {}, set(), {}
        self.output_summaries = {}

    def arm_deadline(self, launch_id, deadline):
        deadline = ExecutionDeadline(deadline.expires_at, min(deadline.elapsed_deadline,
            self.scheduler.elapsed() + self.policy.duration_seconds))
        self.scheduler.arm(launch_id, deadline, lambda: self.kill({'launch_id': launch_id}))
        super().arm_deadline(launch_id, deadline)

    def prepare(self, launch, record):
        self.policy.validate_record(record)
        if self.children or launch['launch_id'] in self.stop_requested:
            raise AuthorityError('Global concurrency/cleanup boundary.')
        self.output[launch['launch_id']] = OutputCollector(self.policy,limit=record.output_bytes)
        self.cpu_used[launch['launch_id']] = 0
        return super().prepare(launch, record)

    def prepare_pinned(self, launch, record, handle):
        if self.gate_fds is None:
            raise AuthorityError('Trusted sealed gate-channel adapter required.')
        config_fd, release_fd = self.gate_fds(launch)
        self.plans[launch['launch_id']] = build_plan(launch, record, handle,
            config_fd=config_fd, release_fd=release_fd, policy=self.policy)
        return self.prepare(launch, record)

    def release(self, launch, record):
        key = launch['launch_id']
        self.scheduler.service()
        if key in self.stop_requested or key not in self.children:
            raise AuthorityError('Stopped launch cannot release.')
        return super().release(launch, record)

    def kill(self, launch):
        self.stop_requested.add(launch['launch_id'])
        super().kill(launch)

    def service_deadlines(self, *, now, elapsed):
        self.scheduler.service()

    def output_evidence(self, launch):
        key = launch['launch_id']
        return self.output[key].evidence() if key in self.output else self.output_summaries[key]

    def account_cpu(self, launch_id, seconds):
        if finite(seconds) < 0: raise ValidationError('Negative CPU accounting.')
        self.cpu_used[launch_id] += seconds
        if self.cpu_used[launch_id] >= self.policy.cpu_seconds:
            self.kill({'launch_id': launch_id})  # Aggregate cgroup usage, not per-process RLIMIT only.

    def observe_exit(self, launch, process, exit_code):
        if process != self.process or process.boot_id != launch['boot_id']:
            raise AuthorityError('Stale process/boot evidence.')
        if type(exit_code) is not int or not -255 <= exit_code <= 255:
            raise ValidationError('Bounded exit code required.')
        self.children[launch['launch_id']]['exited'] = True
        self.exit_codes[launch['launch_id']] = exit_code

    def reconcile_unknown(self):
        keys = set(self.children) | set(self.armed)
        for key in keys:
            self.kill({'launch_id': key})
        if not self.cleanup_known:
            return False
        for key in keys:
            self.finish({'launch_id': key})
        return True

    def finish(self, launch):
        super().finish(launch)  # Never succeeds before whole-cgroup cleanup.
        key = launch['launch_id']
        self.scheduler.cancel(key)
        if key in self.output:
            self.output_summaries[key] = self.output.pop(key).evidence()
        self.cpu_used.pop(key, None)
        self.plans.pop(key, None)  # Never retain closed descriptor numbers for another launch.
        return self.exit_codes.get(key)
