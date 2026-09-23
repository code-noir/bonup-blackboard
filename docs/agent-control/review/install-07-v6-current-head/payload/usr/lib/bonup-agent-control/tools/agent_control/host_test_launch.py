"""Fixed catalog enrollment into the existing durable controller launch flow."""
from dataclasses import asdict
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

from .authority import AuthenticatedContext
from .execution import CommandPolicy, Enrollment, RoutingEvent
from .host_test_catalog import CATALOG, PROFILE, ROOT_ID
from .identity import PeerIdentity, WorkerIdentity
from .protocol import Operation
from .records import Approval, ExecutionGrant, Task, task_spec_digest
from .serialization import canonical_json, digest
from .types import AuthorityError, Role


def execution_id(generation, case):
    return str(uuid5(NAMESPACE_URL, 'bonup-host-test:' + generation + ':' + case.test_id))


def supervisor_catalog(root, generation, anchor):
    """Supervisor resolves installed logical storage and constructs its own plans."""
    from .composition import ApprovedPlan
    from .execution import LaunchRecord
    from .runtime import profile_record
    if root.logical_id != ROOT_ID or root.profile != PROFILE or root.object_identity[2:] != (3002,3002):
        raise AuthorityError('Installed closed host-test root required.')
    result = []
    for case in CATALOG.values():
        eid = execution_id(generation, case)
        worker = WorkerIdentity('FE-01', Role.FRONTEND_ENGINEERING, 'bonup-fe01', 3002,3002)
        command = CommandPolicy(case.test_id, Operation.RUN_TEST, case.argv)
        record = LaunchRecord(Operation.RUN_TEST,case.argv,'/work',PROFILE.environment(),30,65536,
            PROFILE.profile_digest,worker,canonical_json({'command_id':case.test_id}), '0'*64,
            '1970-01-01T00:00:00Z')
        result.append(ApprovedPlan(eid,eid,record,root.object_identity,
            digest(profile_record(PROFILE,(command,))),anchor,filesystem=root.expectation()))
    return tuple(result)


class CatalogLaunches:
    def __init__(self, controller, binding, filesystem, anchor, *, peer, witness=None, own_process=None, elapsed=None):
        if filesystem.policy['root_id'] != ROOT_ID or filesystem.policy['profile_digest'] != PROFILE.profile_digest:
            raise AuthorityError('Exact host-test filesystem policy required.')
        if tuple(filesystem.policy['identity'][2:]) != (3002, 3002):
            raise AuthorityError('Exact enrolled host-test worker required.')
        self.controller, self.binding, self.filesystem = controller, binding, filesystem
        self.anchor, self.peer = anchor, peer
        self.used = set()
        self.witness,self.own_process,self.elapsed=witness,own_process,elapsed

    def execution_ids(self):
        return tuple(execution_id(self.controller.sequencer.generation, case) for case in CATALOG.values())

    def enroll(self, case, verify):
        if CATALOG.get(case.test_id) is not case or case.test_id in self.used:
            raise AuthorityError('Closed catalog enrollment only, without replay.')
        verify()
        self.used.add(case.test_id)
        c, rr = self.controller, self.controller.runtime
        registry = rr.registry
        eid = execution_id(c.sequencer.generation, case)
        # This context is confined to these fixed operations and never returned.
        # Its sole authority is the just-validated signed HOST_TEST delegation.
        context = AuthenticatedContext('FOUNDER', Role.FOUNDER, 1000)
        task = registry.create_task(dict(title='M3 synthetic host test ' + case.test_id,
            objective='Closed catalog integration canary only', source_base_commit=self.binding.source_commit,
            allowed_write_paths=[]), operation_id=str(uuid4()), context=context)
        approval_id = str(uuid4())
        root = self.filesystem.root_view('/srv/bonup-agent-work/bonup-fe01/workspace')
        branch = 'agent/' + task['task_id'] + '/host-test'
        def approve(now, changed):
            verify()
            data = task.to_dict()
            assignment = dict(owner_agent='FE-01', workstream='frontend', allowed_write_paths=[],
                              branch=branch, worktree=root.path)
            data.update(state='ASSIGNED', spec_version=2, spec_frozen=True, record_revision=2,
                owner_agents=['FE-01'], assignments=[assignment], branch={'FE-01': branch},
                worktree={'FE-01': root.path}, founder_approval=approval_id,
                approved_by=context.actor(), updated_at=now)
            data['spec_digest'] = task_spec_digest(data)
            approved_task = Task(data)
            registry._save_task(approved_task, changed)
            approval = Approval(dict(schema_version=1, approval_id=approval_id, action='APPROVE_SPEC',
                task_id=data['task_id'], spec_version=2, spec_digest=data['spec_digest'], candidate_id=None,
                candidate_digest=None, expected_target_commit=None, approved_result_commit=None,
                scope=['M3_HOST_INTEGRATION_TEST:' + case.test_id], actor_id='FOUNDER',
                authenticated_unix_uid=1000, created_at=now, reason='SIGNED_HOST_TEST_DELEGATION', supersedes=None),
                context=context)
            row = approval.to_dict()
            registry.db.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?,?)',
                (approval_id, data['task_id'], None, 2, canonical_json(row), digest(row),
                 canonical_json(dict(context.actor(), authenticated_unix_uid=1000))))
            changed.append(('Approval', approval_id, 'approvals/' + approval_id + '.json', row))
            return data, data['task_id']
        event = RoutingEvent('HOST_TEST_CASE_ENROLLED', str(uuid4()), 'AUTHORIZED', eid)
        data = registry._operation(str(uuid4()), 'host-test.freeze', {'test_id': case.test_id},
                                   None, approve, event.event_type, routing=event)
        verify()
        worker = WorkerIdentity('FE-01', Role.FRONTEND_ENGINEERING, 'bonup-fe01', 3002, 3002)
        existing = rr.db.execute("SELECT enrollment_id FROM identity_enrollments WHERE agent_id='FE-01'").fetchone()
        if existing:
            enrollment_id = existing[0]
            if rr.enrollment(enrollment_id) != worker:
                raise AuthorityError('Host-test worker enrollment mismatch.')
        else:
            enrollment_id = rr.enroll(worker, 1, self.binding.candidate_bundle_digest, context=context)
        command = CommandPolicy(case.test_id, Operation.RUN_TEST, case.argv)
        profile_id = rr.put_profile(PROFILE, (command,), context=context)
        expires = min(rr.now() + timedelta(seconds=30), datetime.fromisoformat(verify.expires_at)).isoformat().replace('+00:00', 'Z')
        grant = ExecutionGrant(dict(schema_version=1, execution_id=eid, agent_id='FE-01',
            role=worker.role.value, task_id=data['task_id'], spec_version=2, spec_digest=data['spec_digest'],
            session_id=None, branch=branch, worktree=root.path,
            can_read=[dict(kind='FILE', path='frontend/example.ts')], can_write=[],
            can_commit_local=False, can_push=False, can_merge=False, can_change_task_spec=False,
            reserved_resources=[], fencing_epoch=1, process_scope='pid:' + str(self.anchor.pid),
            boot_id=self.anchor.boot_id, process_start_identity=str(self.anchor.start_ticks), expires_at=expires))
        rr.issue_grant(grant, context=context, operation_id=str(uuid4()))
        rr.bind_execution(eid, enrollment_id, profile_id, context=context)
        c.authorization._grant_deadlines[digest(grant.to_dict())] = verify.elapsed_deadline
        verify()
        enrollment = Enrollment(self.peer, self.anchor, eid)
        c.authorization.enrollments += (enrollment,)
        c.authorization.store.roots[eid] = root
        c.authorization.store.repositories[eid] = None
        c.remote.filesystem_expectations[eid] = self.filesystem
        c.remote.plan_ids[eid] = eid
        return enrollment

    def run(self, case, enrollment, *, request_id=None, authorized=None):
        c = self.controller
        request_id=request_id or str(uuid4())
        raw = canonical_json(dict(version=1, request_id=request_id, execution_id=enrollment.execution_id,
            operation='RUN_TEST', arguments={'command_id': case.test_id})).encode()
        def launch():
            try:
                lid = c._register(raw, enrollment)
            except BaseException:
                c._audit('OPERATION_DENIED',request_id,'AUTHORITY_CHANGED',enrollment.execution_id)
                raise
            if authorized is not None:authorized(lid)
            c._audit('OPERATION_AUTHORIZED',request_id,'AUTHORIZED',enrollment.execution_id,lid)
            c.prepare(lid)
            c.release(lid)
            if self.witness is not None and case.test_id=='supervisor_crash':
                from .identity import ProcessIdentity
                self.witness.inspect(lid,ProcessIdentity(**c.remote.evidence[lid]['process']),self.anchor)
            return lid
        return c.admission.run_host(enrollment.execution_id, launch)

    def collect(self, case, launch_id):
        c = self.controller
        c.tick()
        row = c.runtime.launch(launch_id)
        if row['state'] != 'TERMINAL' or not row['cleanup_confirmed']:
            return None
        # EXIT 0 is necessary, never sufficient for cases requiring interruption
        # or additional host observations. Those cannot be asserted by intake.
        if case.service_interruption:
            return None
        output = c.remote.results.get(launch_id)
        if output is None:
            return None
        from .host_test_observation import verify_canary
        status = c.remote._call('STATUS_LAUNCH', launch_id, {}, 'STATUS_EVIDENCE', version=3)
        if status['process'] != c.remote.evidence[launch_id]['process']:
            raise AuthorityError('Stale process evidence.')
        return dict(passed=verify_canary(case, row, output, status['lifecycle']), launch_id=launch_id,
                    generation=c.sequencer.generation, cleanup=True, output_digest=digest(output))

    def status(self, launch_id):
        c = self.controller
        row = c.runtime.launch(launch_id)
        if row['execution_id'] not in self.execution_ids():
            raise AuthorityError('Only this runtime catalog may be observed.')
        status = c.remote._call('STATUS_LAUNCH',launch_id,{},'STATUS_EVIDENCE',version=3)
        if status['process'] != c.remote.evidence[launch_id]['process']:
            raise AuthorityError('Stale process evidence.')
        return status

    def arm_interruption(self, case, launch):
        from .identity import ProcessIdentity
        if self.witness is None: raise AuthorityError('Kernel interruption witness required.')
        row=self.controller.runtime.launch(launch)
        status=self.status(launch)
        if row['state']!='RUNNING' or status['exited'] or not status['lifecycle']['exec_confirmed']:
            raise AuthorityError('Confirmed running canary required.')
        target=self.anchor if case.test_id=='supervisor_crash' else self.own_process
        identity=self.witness.inspect(launch,ProcessIdentity(**status['process']),target)
        return dict(identity,phase='INTERRUPTION_ARMED',armed_boottime_ns=int(self.elapsed()*1e9),
                    prior_service_events=status['service_events'])

    def interruption_evidence(self, case, pending):
        if self.witness is None:raise AuthorityError('Kernel interruption witness required.')
        component='controller' if case.test_id=='supervisor_crash' else 'supervisor'
        return self.witness.read(component,pending['launch_id'])

    def observe_interruption(self, *, cleanup):
        events=[]
        try:
            if self.witness is not None:
                events=[self.witness.capture(launch) for launch in tuple(self.witness.watches)]
        finally:cleanup()
        for event in events:self.witness.persist(event)

    def close(self):
        if self.witness is not None:self.witness.close()
