"""Offline composition with an explicit database/privilege separation.

ControllerRuntime owns SQLite and final authorization. SupervisorEndpoint receives
only fixed-plan selectors and bounded authority, and has no registry reference.
The in-memory transport is deliberately test-only; no listener is opened here.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import time
from types import MappingProxyType
from uuid import uuid4

from .composition_protocol import FrameReader, frame, validate
from .execution import LaunchRecord
from .identity import ProcessIdentity
from .integration_policy import IntegrationPolicy
from .protocol import ModelProposal, uuid_value
from .schema import timestamp
from .serialization import canonical_json, digest, parse_json
from .supervisor import ExecutionDeadline, Supervisor
from .types import AuthorityError, ValidationError


def payload_digest(record):
    """Bind the selected installed payload to the command the controller authorized."""
    return digest(dict(operation=record.operation.value, argv=list(record.argv),
                       cwd=record.cwd, environment=[list(p) for p in record.environment],
                       profile_digest=record.profile_digest,
                       worker=dict(asdict(record.worker), role=record.worker.role.value),
                       payload_json=record.payload_json, output_bytes=record.output_bytes,
                       resources=IntegrationPolicy().policy_digest))


@dataclass(frozen=True)
class ApprovedPlan:
    """Constructed from trusted local configuration, never from protocol data.

    The backend owns the actual pinned exports. workspace_identity is the approved
    device/inode/owner tuple. Root pathnames and payloads never cross the channel.
    """
    plan_id: str
    execution_id: str
    record: LaunchRecord
    workspace_identity: tuple
    profile_id: str
    anchor: ProcessIdentity
    limits: IntegrationPolicy = IntegrationPolicy()
    filesystem: object = None  # ExpectedFilesystem from installed controller/root policy.

    def __post_init__(self):
        uuid_value(self.plan_id)
        uuid_value(self.execution_id)
        if (type(self.record) is not LaunchRecord or type(self.anchor) is not ProcessIdentity or
                type(self.workspace_identity) is not tuple or len(self.workspace_identity) != 4 or
                any(type(v) is not int or v < 0 for v in self.workspace_identity) or
                self.workspace_identity[2:] != (self.record.worker.uid, self.record.worker.gid)):
            raise ValidationError('Invalid installed launch plan.')
        if type(self.limits) is not IntegrationPolicy:
            raise ValidationError('Approved immutable integration limits required.')
        self.limits.validate_record(self.record)
        if self.filesystem is not None:
            from .filesystem_evidence import ExpectedFilesystem
            if (type(self.filesystem) is not ExpectedFilesystem or
                    tuple(self.filesystem.policy['identity']) != self.workspace_identity or
                    self.filesystem.policy['profile_digest'] != self.record.profile_digest):
                raise ValidationError('Filesystem plan differs from approved worker/profile.')


def message(action, launch_id, generation, boot_id, data, *, request_id=None, version=1):
    return validate(dict(version=version, action=action, launch_id=launch_id,
                         request_id=request_id or str(uuid4()), generation=generation,
                         boot_id=boot_id, data=data))


class SupervisorEndpoint:
    """Privileged-side state contains processes and plans, never controller SQLite.

    An authenticated transport must call handle only after peer enrollment checks.
    A new generation starts closed and requires reconciliation. Any ambiguity stops
    admission and retains launch identities until cleanup can be established.
    """
    def __init__(self, plans, backend, *, generation, boot_id, now=None, elapsed=None, inspector=None, admission=None, host_only=False, witness=None, controller_process=None, ordinary_admission=True):
        self.witness,self.controller_process=witness,controller_process
        self.ordinary_admission=ordinary_admission
        uuid_value(generation)
        uuid_value(boot_id)
        if any(type(p) is not ApprovedPlan for p in plans) or len({p.plan_id for p in plans}) != len(plans):
            raise ValidationError('Unique installed plans required.')
        self.plans = MappingProxyType({p.plan_id: p for p in plans})
        self.backend = backend
        self.inspector = inspector
        self.generation, self.boot_id = generation, boot_id
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.elapsed = elapsed or (lambda: time.clock_gettime(time.CLOCK_BOOTTIME))
        self.launches, self.seen = {}, set()
        self.ready = False
        self.admission = admission
        self.host_only = host_only
        self.last_heartbeat = self.elapsed()

    def _reply(self, request, action, data):
        return message(action, request['launch_id'], self.generation, self.boot_id,
                       data, request_id=request['request_id'], version=request['version'])

    def _cleanup(self, entry):
        preparing = entry.get('preparing', False)
        entry['state'] = 'STOPPING'
        try:
            self.backend.kill(entry['launch'])
        finally:
            if self.inspector is not None and not preparing:
                self.inspector.close(entry['launch']['launch_id'])
        if preparing:
            return dict(empty=False, exit_code=None)
        empty = self.backend.empty(entry['launch']) is True
        exit_code = None
        if empty:
            exit_code = self.backend.finish(entry['launch'])
            entry['exit_code'] = exit_code
            entry['state'] = 'TERMINAL'
        return dict(empty=empty, exit_code=exit_code)

    def disconnect(self, *, close_admission=True):
        if self.admission is not None and close_admission:
            self.admission.close()
        self.ready = False
        try:
            for entry in tuple(self.launches.values()):
                if entry['state'] != 'TERMINAL':
                    if self.witness is not None and entry['state']=='RUNNING':
                        self.witness.observe(entry['launch']['launch_id'],
                                             cleanup=lambda:self._cleanup(entry))
                    else:self._cleanup(entry)
        finally:
            if self.inspector is not None and not any(e.get('preparing',False) for e in self.launches.values()):
                self.inspector.disconnect()

    def tick(self):
        # Run independently of partial request parsing. CLOCK_BOOTTIME includes suspend.
        self.backend.service_deadlines(now=self.now(), elapsed=self.elapsed())
        if self.elapsed() - self.last_heartbeat >= 2:
            self.disconnect()
        for entry in tuple(self.launches.values()):
            if entry['state'] == 'TERMINAL':
                continue
            if (entry['state'] == 'STOPPING' or
                    entry['deadline'].expired(now=self.now(), elapsed=self.elapsed()) or
                    self.backend.exited(entry['launch'])):
                self._cleanup(entry)

    def handle(self, request):
        request = validate(request)
        if request['generation'] != self.generation or request['boot_id'] != self.boot_id:
            raise AuthorityError('Stale supervisor generation or boot.')
        if request['request_id'] in self.seen or len(self.seen) >= 4096:
            raise AuthorityError('Request replay or generation capacity exhausted.')
        self.seen.add(request['request_id'])
        action, data, launch_id = request['action'], request['data'], request['launch_id']
        if action == 'OPEN_ADMISSION':
            if not self.ordinary_admission and not self.host_only:
                raise AuthorityError('Successor ordinary admission is disabled.')
            if self.admission is None or not self.ready:
                raise AuthorityError('Fresh operational reconciliation required.')
            if self.host_only:
                if data['session_digest'] != self.admission.session:
                    raise AuthorityError('Host-test operational session mismatch.')
                self.admission.begin_host_tests(tuple(p.execution_id for p in self.plans.values()), lambda: None)
            else:
                self.admission.open(data['session_digest'])
            return self._reply(request, 'ADMISSION_EVIDENCE', dict(session_digest=self.admission.session))
        if action == 'RECONCILE':
            from .operational_enrollment import AdmissionState
            if self.admission is not None and self.admission.state != AdmissionState.RECONCILING:
                raise AuthorityError('Reconciliation requires fresh enrollment.')
            self.disconnect(close_admission=False)
            clean = self.backend.reconcile_unknown() is True
            self.ready = clean and all(e['state'] == 'TERMINAL' for e in self.launches.values())
            self.last_heartbeat = self.elapsed()
            if self.ready and self.admission is not None:
                self.admission.reconciled()
            return self._reply(request, 'CLEANUP_EVIDENCE', dict(empty=self.ready, exit_code=None))
        if action == 'HEARTBEAT':
            self.last_heartbeat = self.elapsed()
            if data['ready'] is not True:
                self.disconnect()
            return self._reply(request, 'HEARTBEAT', dict(ready=self.ready))
        if action == 'PREPARE_LAUNCH':
            if self.admission is not None:
                if self.host_only:
                    self.admission.run_host(data['execution_id'], lambda: None)
                else:
                    self.admission.require_open()
            if not self.ready or launch_id in self.launches or any(e['state'] != 'TERMINAL' for e in self.launches.values()):
                raise AuthorityError('Admission closed, launch replay or concurrency limit.')
            plan = self.plans.get(data['plan_id'])
            if (plan is None or plan.execution_id != data['execution_id'] or
                    plan.anchor.boot_id != self.boot_id or
                    payload_digest(plan.record) != data['plan_digest'] or
                    digest(list(plan.workspace_identity)) != data['workspace_digest']):
                raise AuthorityError('Unknown or substituted installed plan.')
            if plan.filesystem is not None:
                if (request['version'] != 2 or self.inspector is None or
                        data['root_id'] != plan.filesystem.policy['root_id'] or
                        data['filesystem_policy_digest'] != plan.filesystem.policy_digest):
                    raise AuthorityError('Pinned filesystem policy required; no legacy fallback.')
            elif request['version'] != 1:
                raise AuthorityError('No installed filesystem plan.')
            remaining = min(plan.limits.duration_seconds, plan.record.timeout_seconds,
                            data['elapsed_deadline_ns'] / 1e9 - self.elapsed())
            deadline = ExecutionDeadline.arm(data['expires_at'], now=self.now(),
                                             elapsed=self.elapsed(), timeout_seconds=remaining)
            deadline = replace(deadline, elapsed_deadline=min(deadline.elapsed_deadline,
                               data['elapsed_deadline_ns'] / 1e9))
            record = replace(plan.record, authorization_digest=data['authorization_digest'],
                             expires_at=data['expires_at'], timeout_seconds=remaining,
                             elapsed_deadline=deadline.elapsed_deadline)
            launch = dict(launch_id=launch_id, execution_id=plan.execution_id,
                          request_id=request['request_id'], supervisor_generation=self.generation,
                          boot_id=self.boot_id, cgroup_name='launch-' + launch_id,
                          authorization_digest=record.authorization_digest, deadline=record.expires_at,
                          binding=canonical_json(dict(workspace=list(plan.workspace_identity),
                              repository=None if plan.filesystem is None else plan.filesystem.policy['repository_identity'], profile_digest=plan.profile_id,
                              supervisor_anchor=asdict(plan.anchor))))
            entry = dict(launch=launch, record=record, deadline=deadline, state='PREPARING',
                         workspace_digest=data['workspace_digest'], release_id=None, preparing=True)
            self.launches[launch_id] = entry  # Remember failures too; never reuse a launch ID.
            try:
                self.backend.arm_deadline(launch_id, deadline)
                filesystem_data = {}
                if plan.filesystem is not None:
                    handle = self.inspector.prepare(data['root_id'], data['filesystem_policy_digest'],
                                                    launch_id, self.generation)
                    proof = handle.evidence()
                    plan.filesystem.accept(proof, launch_id, self.generation)
                    # The backend must consume this handle's FD plan, never reopen paths.
                    process = self.backend.prepare_pinned(launch, record, handle)
                    handle.verify(launch_id)
                    entry['filesystem_digest'] = proof['evidence_digest']
                    filesystem_data['filesystem_evidence'] = proof
                    self.inspector.close(launch_id)  # setup completed; gate/payload inherits no pin FDs
                else:
                    process = self.backend.prepare(launch, record)
                if (entry['state'] != 'PREPARING' or not self.ready or
                        type(process) is not ProcessIdentity or process.boot_id != self.boot_id or
                        deadline.expired(now=self.now(), elapsed=self.elapsed())):
                    raise AuthorityError('Invalid or expired preparation evidence.')
                entry.update(state='PREPARED', process=process, preparing=False)
                return self._reply(request, 'PREPARED_EVIDENCE',
                    dict(authorization_digest=record.authorization_digest,
                         workspace_digest=data['workspace_digest'], process=asdict(process), **filesystem_data))
            except BaseException:
                entry['preparing'] = False
                self.ready = False
                self._cleanup(entry)
                raise
        entry = self.launches.get(launch_id)
        if entry is None:
            raise AuthorityError('Unknown prepared launch; reconciliation required.')
        if action == 'STATUS_LAUNCH':
            if 'process' not in entry:
                raise AuthorityError('No authenticated prepared process evidence.')
            extra = {}
            if request['version'] == 3:
                from .service_evidence import recent_service_events
                extra['service_events'] = recent_service_events()
                extra['lifecycle'] = dict(resources_verified=self.backend.resource_evidence(entry['launch']),
                    exec_confirmed=entry.get('exec_confirmed') is True,
                    cleanup_confirmed=entry['state'] == 'TERMINAL')
            return self._reply(request, 'STATUS_EVIDENCE', dict(**extra,
                exited=entry['state'] == 'TERMINAL' or self.backend.exited(entry['launch']) is True,
                process=asdict(entry['process']),
                output=self.backend.output_evidence(entry['launch']) if hasattr(self.backend,'output_evidence')
                    else {s:dict(retained=0,truncated=False) for s in ('stdout','stderr')}))
        if action == 'STOP_LAUNCH':
            if entry['state'] == 'TERMINAL':
                return self._reply(request, 'CLEANUP_EVIDENCE', dict(empty=True, exit_code=entry.get('exit_code')))
            return self._reply(request, 'CLEANUP_EVIDENCE', self._cleanup(entry))
        if action != 'RELEASE_LAUNCH':
            raise AuthorityError('Evidence cannot authorize execution.')
        if (not self.ready or entry['state'] != 'PREPARED' or
                ('filesystem_digest' in entry and (request['version'] != 2 or
                    data['filesystem_evidence_digest'] != entry['filesystem_digest'])) or
                data['authorization_digest'] != entry['record'].authorization_digest or
                entry['deadline'].expired(now=self.now(), elapsed=self.elapsed())):
            self._cleanup(entry)
            raise AuthorityError('Invalid, duplicate or expired release.')
        # Consume before delivery. An exception never permits retry, even with another token.
        entry.update(state='RELEASE_PENDING', release_id=data['release_id'])
        try:
            if self.admission is None:
                proof = self.backend.release(entry['launch'], entry['record'])
            else:
                if self.host_only:
                    proof = self.admission.run_host(entry['launch']['execution_id'],
                        self.backend.release, entry['launch'], entry['record'])
                else:
                    proof = self.admission.run(self.backend.release, entry['launch'], entry['record'])
            from .exec_start import ExecStart
            if type(proof) is not ExecStart:
                raise AuthorityError('Release delivery is not execution-start proof.')
            proof.verify(entry['launch'], entry['record'])
            entry['exec_confirmed'] = True
            if self.witness is not None and entry['record'].argv[-1] in ('controller_crash','reboot_reconciliation','watchdog'):
                self.witness.inspect(launch_id,entry['process'],self.controller_process)
            entry['state'] = 'RUNNING'
            return self._reply(request, 'RUNNING_EVIDENCE',
                dict(authorization_digest=entry['record'].authorization_digest,
                     release_id=data['release_id'], process=asdict(entry['process'])))
        except BaseException:
            self.ready = False
            self._cleanup(entry)
            raise


class OfflineTransport:
    """Synthetic transport only; serializes both directions to exercise the wire contract.

    Production requires actual-sender kernel enrollment and bounded channel ownership.
    Neither endpoint object is sent over the wire.
    """
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.sent = []
        self.connected = True

    def exchange(self, request):
        if not self.connected:
            raise AuthorityError('Supervisor disconnected.')
        self.sent.append(parse_json(canonical_json(request)))
        reader = FrameReader(now=0)
        decoded = reader.feed(frame(request), now=0, eof=True)
        reply = self.endpoint.handle(decoded)
        reader = FrameReader(now=0)
        return reader.feed(frame(reply), now=0, eof=True)

    def disconnect(self):
        self.connected = False
        self.endpoint.disconnect()


class RemoteProcessBackend:
    """Controller-owned facade: strips all privileged parameters before transport."""
    def __init__(self, transport, plan_ids, *, generation, boot_id, filesystem_expectations=None):
        self.transport, self.plan_ids = transport, dict(plan_ids)
        self.generation, self.boot_id = generation, boot_id
        self.deadlines, self.evidence, self.cleanup = {}, {}, {}
        self.filesystem_expectations = dict(filesystem_expectations or {})
        self.prepared_filesystems = {}
        self.results = {}

    def _call(self, action, launch_id, data, response, *, version=1):
        request = message(action, launch_id, self.generation, self.boot_id, data, version=version)
        reply = validate(self.transport.exchange(request))
        if (reply['action'] != response or any(reply[k] != request[k] for k in
                ('version', 'request_id', 'launch_id', 'generation', 'boot_id'))):
            raise AuthorityError('Mismatched supervisor evidence.')
        return reply['data']

    def arm_deadline(self, launch_id, deadline):
        if launch_id in self.deadlines:
            raise AuthorityError('Deadline already armed.')
        self.deadlines[launch_id] = deadline

    def prepare(self, launch, record):
        binding = parse_json(launch['binding'])
        deadline = self.deadlines[launch['launch_id']]
        expected = self.filesystem_expectations.get(launch['execution_id'])
        extra = {}
        if expected is not None:
            if (expected.policy['identity'] != binding['workspace'] or
                    expected.policy['repository_identity'] != binding['repository'] or
                    expected.policy['identity'][2:] != [record.worker.uid,record.worker.gid] or
                    expected.policy['profile_digest'] != record.profile_digest):
                raise AuthorityError('Filesystem expectations differ from durable launch authority.')
            extra = dict(root_id=expected.policy['root_id'], filesystem_policy_digest=expected.policy_digest)
        evidence = self._call('PREPARE_LAUNCH', launch['launch_id'],
            dict(plan_id=self.plan_ids[launch['execution_id']], execution_id=launch['execution_id'],
                 authorization_digest=record.authorization_digest,
                 plan_digest=payload_digest(record),
                 workspace_digest=digest(binding['workspace']), expires_at=deadline.expires_at.isoformat(),
                 elapsed_deadline_ns=int(deadline.elapsed_deadline * 1e9), **extra), 'PREPARED_EVIDENCE',
                 version=2 if expected is not None else 1)
        if (evidence['authorization_digest'] != record.authorization_digest or
                evidence['workspace_digest'] != digest(binding['workspace'])):
            raise AuthorityError('Substituted preparation evidence.')
        if expected is not None:
            expected.accept(evidence['filesystem_evidence'],launch['launch_id'],self.generation)
            self.prepared_filesystems[launch['launch_id']] = expected
        process = ProcessIdentity(**evidence['process'])
        self.evidence[launch['launch_id']] = evidence
        return process

    def release(self, launch, record):
        release_id = str(uuid4())
        original = self.prepared_filesystems.get(launch['launch_id'])
        extra = {}
        if original is not None:
            if self.filesystem_expectations.get(launch['execution_id']) != original:
                raise AuthorityError('Filesystem authority replaced after preparation.')
            value = original.accept(self.evidence[launch['launch_id']]['filesystem_evidence'],
                                    launch['launch_id'],self.generation)
            extra = dict(filesystem_evidence_digest=value)
        elif launch['execution_id'] in self.filesystem_expectations:
            raise AuthorityError('No original filesystem evidence.')
        evidence = self._call('RELEASE_LAUNCH', launch['launch_id'],
            dict(authorization_digest=record.authorization_digest, release_id=release_id, **extra), 'RUNNING_EVIDENCE',
            version=2 if original is not None else 1)
        prepared = self.evidence[launch['launch_id']]
        if (evidence['release_id'] != release_id or evidence['authorization_digest'] != record.authorization_digest or
                evidence['process'] != prepared['process']):
            raise AuthorityError('Substituted running evidence; stop without replay.')
        from .exec_start import ExecStart
        return ExecStart(launch['launch_id'],self.generation,record.authorization_digest)

    def kill(self, launch):
        self.cleanup[launch['launch_id']] = self._call('STOP_LAUNCH', launch['launch_id'],
            dict(reason=launch.get('reason') or 'INTERRUPTED'), 'CLEANUP_EVIDENCE')

    def empty(self, launch):
        return self.cleanup.get(launch['launch_id'], {}).get('empty') is True

    def finish(self, launch):
        if not self.empty(launch):
            raise AuthorityError('Cleanup remains uncertain.')
        return self.cleanup[launch['launch_id']]['exit_code']

    def exited(self, launch):
        prepared = self.evidence.get(launch['launch_id'])
        if prepared is None:
            return False
        status = self._call('STATUS_LAUNCH', launch['launch_id'], {}, 'STATUS_EVIDENCE')
        if status['process'] != prepared['process']:
            raise AuthorityError('Stale process exit evidence; reconciliation required.')
        self.results[launch['launch_id']] = status['output']
        return status['exited']

    def service_deadlines(self, *, now, elapsed):
        # Controller poll enforces durable authority; supervisor has its own deadline.
        return None

    def reconcile_unknown(self):
        evidence = self._call('RECONCILE', str(uuid4()), {}, 'CLEANUP_EVIDENCE')
        return evidence['empty'] is True

    def heartbeat(self):
        return self._call('HEARTBEAT', str(uuid4()), dict(ready=True), 'HEARTBEAT')['ready']


class ControllerRuntime:
    """Sole database writer; the existing Supervisor is used as a local sequencer.

    No production backend or privilege-changing primitive is supplied here. The
    authorization object remains the proposal-only Controller, including its exact
    grant/lease/task/profile snapshot and rollback-resistant deadline caches.
    """
    def __init__(self, runtime, authorization, remote, *, generation, boot_id, admission=None):
        self.admission = admission
        self.runtime, self.authorization, self.remote = runtime, authorization, remote
        self.proposals = {}
        self.sequencer = Supervisor(runtime, remote, generation=generation, boot_id=boot_id,
            authorize=self._authorize, now=authorization.clock, elapsed=authorization.elapsed)

    def _authorize(self, execution_id, request_id):
        enrollment, proposal = self.proposals[(execution_id, request_id)]
        record = self.authorization._check(enrollment, proposal)
        binding = self.authorization.store.load(execution_id)
        policy_digest = getattr(binding.root, 'filesystem_policy_digest', None)
        expected = self.remote.filesystem_expectations.get(execution_id)
        if policy_digest != (None if expected is None else expected.policy_digest):
            raise AuthorityError('Remote filesystem policy differs from original authorization.')
        return record

    @staticmethod
    def _correlation(raw):
        from .protocol import bounded_json
        from .schema import valid_format
        # Untrusted IDs are correlation only. Never log raw proposal/arguments.
        try:
            data = bounded_json(raw)
        except (ValueError, ValidationError, TypeError):
            data = {}
        if type(data) is not dict: data = {}
        request = data.get('request_id')
        execution = data.get('execution_id')
        if not valid_format('uuid', request): request = str(uuid4())
        if not valid_format('uuid', execution): execution = None
        return request,execution

    def reject(self, raw, reason):
        """Bounded evidence for transport/intake denial before registration."""
        request,execution=self._correlation(raw)
        self._audit('MODEL_PROPOSAL_RECEIVED',request,'RECEIVED',execution)
        self._audit('OPERATION_DENIED',request,reason,execution)

    def register(self, raw, enrollment):
        request,execution=self._correlation(raw)
        self._audit('MODEL_PROPOSAL_RECEIVED', request, 'RECEIVED', execution)
        try:
            if len(self.proposals)>=4096:
                raise AuthorityError('Proposal admission capacity exhausted.')
            if self.admission is not None:
                launch = self.admission.run(self._register, raw, enrollment)
            else:
                launch = self._register(raw, enrollment)
        except BaseException as error:
            from .execution import RoutingDenied
            reason = error.reason if isinstance(error, RoutingDenied) else 'INVALID_PROPOSAL'
            self._audit('OPERATION_DENIED', request, reason, execution)
            raise
        self._audit('OPERATION_AUTHORIZED', request, 'AUTHORIZED', execution, launch)
        return launch

    def _audit(self, kind, request, reason, execution=None, launch=None):
        from .execution import RoutingEvent
        self.authorization.audit(RoutingEvent(kind, request, reason, execution, launch))

    def _launch_audit(self, kind, launch_id, reason):
        launch = self.runtime.launch(launch_id)
        self._audit(kind, launch['request_id'], reason, launch['execution_id'], launch_id)

    def _register(self, raw, enrollment):
        proposal = ModelProposal.parse(raw)
        key = (proposal.execution_id, proposal.request_id)
        if key in self.proposals:
            raise AuthorityError('Proposal replay.')
        self.proposals[key] = (enrollment, proposal)
        record = self._authorize(*key)
        binding = self.authorization.store.load(proposal.execution_id)
        state = self.runtime.runtime(proposal.execution_id)
        # register_launch's BEGIN IMMEDIATE serializes global admission. Any authority
        # change since _check is rejected again before preparation and release.
        launch_id = self.runtime.register_launch(proposal.execution_id, proposal.request_id,
            record.authorization_digest, self.sequencer.generation, self.sequencer.boot_id,
            dict(workspace=list(binding.root.identity), repository=binding.repository_identity,
                 profile_digest=state['profile_digest']), exclusive=True)
        return launch_id

    def prepare(self, launch_id):
        self._launch_audit('CONFINEMENT_SETUP_STARTED', launch_id, 'SETUP')
        try:
            if self.admission is not None:
                self.admission.require_execution(self.runtime.launch(launch_id)['execution_id'])
            return self.sequencer.prepare(launch_id)
        except BaseException:
            self._launch_audit('CONFINEMENT_SETUP_FAILED', launch_id, 'SETUP_FAILED')
            raise

    def release(self, launch_id):
        try:
            if self.admission is not None:
                with self.admission.lock:
                    self.admission.require_execution(self.runtime.launch(launch_id)['execution_id'])
                    result = self.sequencer.release(launch_id)
            else:
                result = self.sequencer.release(launch_id)
            self._launch_audit('WORKER_STARTED', launch_id, 'STARTED')
            return result
        except BaseException:
            try:
                self.sequencer.stop(launch_id, 'INTERRUPTED')
            finally:
                # Lost supervisor acknowledgement must not suppress controller
                # evidence merely because cleanup is also still uncertain.
                self._launch_audit('OPERATION_DENIED', launch_id, 'AUTHORITY_CHANGED')
            raise

    def stop(self, launch_id, reason='CANCELLED'):
        previous = self.runtime.launch(launch_id)['state']
        result = self.sequencer.stop(launch_id, reason)
        if previous != 'TERMINAL' and result['state'] == 'TERMINAL':
            self._launch_audit('WORKER_EXITED', launch_id, 'EXITED')
        return result

    def tick(self, *, controller_alive=True):
        if not controller_alive and self.admission is not None:
            self.admission.close()
        rows = self.runtime.db.execute("SELECT launch_id FROM launch_attempts WHERE state!='TERMINAL'").fetchall()
        for row in rows:
            result = self.sequencer.poll(row[0], controller_alive=controller_alive)
            if result['state'] == 'TERMINAL':
                self._launch_audit('WORKER_EXITED', row[0], 'EXITED')

    def reconcile(self):
        # Global supervisor evidence comes first: an intent can exist in SQLite even
        # when the supervisor never received PREPARE. No unknown launch is resumed.
        if self.remote.reconcile_unknown() is not True:
            raise AuthorityError('Supervisor cleanup uncertain; admission remains blocked.')
        result = []
        rows = self.runtime.db.execute("SELECT launch_id FROM launch_attempts WHERE state!='TERMINAL'").fetchall()
        for row in rows:
            launch = self.runtime.launch(row[0])
            if launch['state'] != 'STOPPING':
                launch = self.runtime.transition(row[0], launch['revision'], 'STOPPING', reason='INTERRUPTED')
            result.append(self.runtime.transition(row[0], launch['revision'], 'TERMINAL', cleanup=True))
        return result
