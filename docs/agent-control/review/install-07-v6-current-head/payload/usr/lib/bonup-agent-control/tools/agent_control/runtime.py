"""Durable controller-owned runtime state. No daemon, UID provisioning or OS launch.

This object is an internal authority adapter, never deserialized from IPC. Public
supervisor requests are authenticated separately. Enrollment/profile administration
requires the configured authenticated founder context.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .authority import require_context
from .confinement import ConfinementProfile
from .execution import CommandPolicy, ExecutionBinding, RequiredLease
from .identity import ProcessIdentity, WorkerIdentity
from .protocol import Operation, uuid_value
from .records import Reservation
from .runtime_schema import check_version
from .schema import timestamp, valid_format
from .serialization import canonical_json, digest, parse_json
from .storage import RegistryBlocked
from .types import AuthorityError, Role, ValidationError

STATES = {
    'REGISTERED': frozenset({'PREPARING', 'STOPPING'}),
    'PREPARING': frozenset({'PREPARED', 'STOPPING'}),
    'PREPARED': frozenset({'RELEASE_PENDING', 'STOPPING'}),
    'RELEASE_PENDING': frozenset({'RUNNING', 'STOPPING'}),
    'RUNNING': frozenset({'STOPPING'}),
    'STOPPING': frozenset({'TERMINAL'}), 'TERMINAL': frozenset(),
}
REASONS = frozenset({'DENIED','SETUP_FAILED','EXITED','TIMEOUT','REVOKED','CANCELLED','INTERRUPTED'})


def sha(value):
    if not valid_format('sha256', value):
        raise ValidationError('Digest required.')
    return value


def profile_record(profile, commands):
    if type(profile) is not ConfinementProfile or type(commands) is not tuple or not commands:
        raise ValidationError('Explicit immutable execution profile required.')
    data = asdict(profile)
    for key in ('readonly_roots','readable_paths','writable_paths'):
        data[key] = list(data[key])
    if any(type(c) is not CommandPolicy for c in commands):
        raise ValidationError('Fixed command policies required.')
    keys = [(c.operation, c.command_id) for c in commands]
    if len(keys) != len(set(keys)):
        raise ValidationError('Duplicate command policy.')
    environment = [list(x) for x in profile.environment()]
    return dict(version=1, confinement=data, confinement_digest=profile.profile_digest,
                environment=environment, environment_digest=digest(environment),
                commands=[dict(command_id=c.command_id, operation=c.operation.value,
                               argv=list(c.argv), required_reservations=list(c.required_reservations)) for c in commands])


class RuntimeRegistry:
    def __init__(self, registry, *, founder_uid, now=None):
        if type(founder_uid) is not int or founder_uid <= 0:
            raise AuthorityError('Explicit non-root founder required.')
        if check_version(registry.db) not in (2, 3):
            raise RegistryBlocked('Explicit v2 or v3 migration required.')
        self.registry, self.db, self.founder_uid = registry, registry.db, founder_uid
        self.now = now or (lambda:datetime.now(timezone.utc))

    def founder(self, context):
        require_context(context, roles={Role.FOUNDER}, actor_id='FOUNDER')
        if context.authenticated_unix_uid != self.founder_uid:
            raise AuthorityError('Founder UID mismatch.')

    @contextmanager
    def transaction(self, kind):
        if self.db.in_transaction:
            raise RegistryBlocked('Nested runtime transaction rejected.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.registry.verify(check_history=False)['status'] == 'BLOCKED':
                raise RegistryBlocked('Registry verification failed.')
            yield
            # Private operation journal, no command/environment payload or invented actor.
            self.db.execute('INSERT INTO maintenance_operations VALUES (?,?,?)',
                            (str(uuid4()), digest({'runtime_operation':kind}), canonical_json({'status':'COMMITTED'})))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def enroll(self, worker, generation, manifest_digest, *, context):
        self.founder(context)
        if type(worker) is not WorkerIdentity or worker.uid == self.founder_uid:
            raise AuthorityError('Worker enrollment rejected.')
        if type(generation) is not int or generation < 1:
            raise ValidationError('Positive generation required.')
        sha(manifest_digest)
        data = dict(agent_id=worker.agent_id, role=worker.role.value, username=worker.username,
                    uid=worker.uid, gid=worker.gid, generation=generation, manifest_digest=manifest_digest)
        enrollment_id = str(uuid4())
        with self.transaction('enroll'):
            previous = self.db.execute('SELECT max(generation) FROM identity_enrollments WHERE agent_id=?', (worker.agent_id,)).fetchone()[0]
            if generation != (previous or 0) + 1:
                raise AuthorityError('Stale or skipped provisioning generation.')
            if self.db.execute('''SELECT 1 FROM execution_runtime r JOIN identity_enrollments e USING(enrollment_id)
                                  WHERE e.agent_id=? AND (r.revoked=0 OR EXISTS
                                  (SELECT 1 FROM launch_attempts l WHERE l.execution_id=r.execution_id AND l.state!='TERMINAL'))''',
                               (worker.agent_id,)).fetchone():
                raise AuthorityError('Agent still owns active/uncertain execution.')
            self.db.execute('INSERT INTO identity_enrollments VALUES (?,?,?,?,?,?,?,?,?)',
                            (enrollment_id,worker.agent_id,worker.username,worker.uid,worker.gid,generation,
                             manifest_digest,canonical_json(data),digest(data)))
        return enrollment_id

    def put_profile(self, profile, commands, *, context):
        self.founder(context)
        data = profile_record(profile, commands)
        key = digest(data)
        with self.transaction('profile'):
            self.db.execute('INSERT INTO execution_profiles VALUES (?,?)', (key,canonical_json(data)))
        return key

    def enrollment(self, enrollment_id):
        row = self.db.execute('SELECT * FROM identity_enrollments WHERE enrollment_id=?', (enrollment_id,)).fetchone()
        if row is None:
            raise AuthorityError('Unknown enrollment.')
        data = parse_json(row['payload'])
        if digest(data) != row['payload_digest'] or any(data[k] != row[k] for k in ('agent_id','username','uid','gid','generation','manifest_digest')):
            raise RegistryBlocked('Enrollment corruption.')
        worker = WorkerIdentity(data['agent_id'], Role(data['role']), data['username'], data['uid'], data['gid'])
        latest = self.db.execute('SELECT max(generation) FROM identity_enrollments WHERE agent_id=?', (worker.agent_id,)).fetchone()[0]
        if data['generation'] != latest or worker.uid == self.founder_uid:
            raise AuthorityError('Stale worker enrollment.')
        return worker

    def profile(self, key):
        row = self.db.execute('SELECT payload FROM execution_profiles WHERE profile_digest=?', (key,)).fetchone()
        if row is None:
            raise AuthorityError('Unknown execution profile.')
        data = parse_json(row[0])
        if digest(data) != key:
            raise RegistryBlocked('Profile corruption.')
        cfg = dict(data['confinement'])
        for k in ('readonly_roots','readable_paths','writable_paths'):
            cfg[k] = tuple(cfg[k])
        profile = ConfinementProfile(**cfg)
        commands = tuple(CommandPolicy(c['command_id'],Operation(c['operation']),tuple(c['argv']),tuple(c['required_reservations'])) for c in data['commands'])
        if profile_record(profile,commands) != data:
            raise RegistryBlocked('Profile policy mismatch.')
        return profile, commands

    def issue_grant(self, grant, *, context, operation_id):
        """Explicit founder-authorized M3 grant issuance; M2 dormant API stays unchanged."""
        from .records import ExecutionGrant
        from .registry import context_data
        self.founder(context)
        if type(grant) is not ExecutionGrant:
            raise ValidationError('Validated immutable grant required.')
        def issue(now, changed):
            data = grant.to_dict()
            task = self.registry.get_task(data['task_id'])
            grant.assert_task_binding(task)
            self.registry._active_approval(self.registry.load('Approval',task['founder_approval']))
            if self.now()>=timestamp(data['expires_at']):
                raise AuthorityError('Cannot issue expired grant.')
            self.db.execute('INSERT INTO executions VALUES (?,?,?,?,?,?)',
                            (data['execution_id'],data['task_id'],data['agent_id'],canonical_json(data),
                             digest(data),canonical_json(context_data(context))))
            changed.append(('ExecutionGrant',data['execution_id'],f"executions/{data['execution_id']}.json",data))
            return data,data['task_id']
        return self.registry._operation(operation_id,'runtime.issue-grant',grant.to_dict(),context,issue,'EXECUTION_RECORDED')

    def bind_execution(self, execution_id, enrollment_id, profile_digest, *, context):
        self.founder(context)
        with self.transaction('bind'):
            grant = self.registry.load('ExecutionGrant', execution_id)
            task = self.registry.get_task(grant['task_id'])
            grant.assert_task_binding(task)
            self.registry._active_approval(self.registry.load('Approval',task['founder_approval']))
            worker = self.enrollment(enrollment_id)
            self.profile(profile_digest)
            if (grant['agent_id'],grant['role']) != (worker.agent_id,worker.role.value):
                raise AuthorityError('Execution enrollment mismatch.')
            self.db.execute('INSERT INTO execution_runtime VALUES (?,?,?,0,0,?)',
                            (execution_id,enrollment_id,profile_digest,grant['fencing_epoch']))

    def runtime(self, execution_id):
        row = self.db.execute('SELECT * FROM execution_runtime WHERE execution_id=?',(execution_id,)).fetchone()
        if row is None:
            raise AuthorityError('Unknown execution runtime.')
        return dict(row)

    def revoke(self, execution_id, revision, *, context):
        self.founder(context)
        with self.transaction('revoke'):
            changed = self.db.execute('''UPDATE execution_runtime SET revoked=1,authority_revision=authority_revision+1
                                         WHERE execution_id=? AND authority_revision=?''',(execution_id,revision)).rowcount
            if changed != 1:
                raise AuthorityError('Authority CAS mismatch.')

    def register_launch(self, execution_id, request_id, authorization_digest, generation, boot_id, binding, *, exclusive=False):
        for value in (execution_id,request_id,generation,boot_id):
            uuid_value(value)
        sha(authorization_digest)
        # Trusted binding metadata only; never store raw argv/environment or model prose here.
        if type(binding) is not dict or set(binding) != {'workspace','repository','profile_digest'}:
            raise ValidationError('Invalid launch binding.')
        canonical_json(binding)
        launch_id = str(uuid4())
        with self.transaction('register-launch'):
            if exclusive and self.db.execute("SELECT 1 FROM launch_attempts WHERE state!='TERMINAL'").fetchone():
                raise AuthorityError('Global launch concurrency limit or unresolved execution.')
            runtime = self.runtime(execution_id)
            if runtime['revoked']:
                raise AuthorityError('Revoked execution.')
            self.enrollment(runtime['enrollment_id'])
            if binding['profile_digest'] != runtime['profile_digest']:
                raise AuthorityError('Launch profile mismatch.')
            # Separate executions for one worker cannot overlap, even across reboot uncertainty.
            if self.db.execute('''SELECT 1 FROM launch_attempts l JOIN execution_runtime r USING(execution_id)
                                  WHERE r.enrollment_id=? AND l.state!='TERMINAL' ''',(runtime['enrollment_id'],)).fetchone():
                raise AuthorityError('Worker already has an unresolved launch.')
            grant = self.registry.load('ExecutionGrant',execution_id)
            if self.now() >= timestamp(grant['expires_at']):
                raise AuthorityError('Expired execution.')
            if grant['boot_id'] != boot_id or not grant['process_scope'].startswith('pid:'):
                raise AuthorityError('Supervisor anchor boot/process mismatch.')
            try:
                anchor = ProcessIdentity(boot_id,int(grant['process_scope'][4:]),int(grant['process_start_identity']))
                if anchor.pid<=0 or anchor.start_ticks<0:
                    raise ValueError()
            except ValueError:
                raise AuthorityError('Invalid supervisor anchor.') from None
            leases = self.required_leases(execution_id)
            if any(l.execution_id!=execution_id or not l.held or l.revoked or
                   l.fencing_epoch!=runtime['fencing_epoch'] for l in leases):
                raise AuthorityError('Required lease authority mismatch.')
            deadline = min([timestamp(grant['expires_at']), *(timestamp(l.expires_at) for l in leases)])
            if deadline <= self.now():
                raise AuthorityError('Expired required authority.')
            stored_binding = dict(binding, supervisor_anchor=asdict(anchor),
                                  required_leases=[asdict(l) for l in leases])
            self.db.execute('''INSERT INTO launch_attempts
                (launch_id,execution_id,request_id,state,revision,authorization_digest,authority_revision,
                 supervisor_generation,boot_id,cgroup_name,deadline,binding)
                VALUES (?,?,?,'REGISTERED',0,?,?,?,?,?,?,?)''',
                (launch_id,execution_id,request_id,authorization_digest,runtime['authority_revision'],generation,
                 boot_id,'launch-'+launch_id,deadline.isoformat(),canonical_json(stored_binding)))
        return launch_id

    def launch(self, launch_id):
        row = self.db.execute('SELECT * FROM launch_attempts WHERE launch_id=?',(launch_id,)).fetchone()
        if row is None or row['state'] not in STATES:
            raise AuthorityError('Unknown launch/state.')
        return dict(row)

    def transition(self, launch_id, revision, target, *, reason=None, cleanup=False, process=None, exit_code=None):
        with self.transaction('launch-transition'):
            row = self.launch(launch_id)
            if row['revision'] != revision or target not in STATES[row['state']]:
                raise AuthorityError('Invalid launch transition/CAS.')
            if target == 'STOPPING' and reason not in REASONS:
                raise ValidationError('Stop reason required.')
            if target == 'TERMINAL' and (cleanup is not True or row['reason'] not in REASONS):
                raise AuthorityError('Confirmed cleanup required.')
            if process is not None and type(process) is not ProcessIdentity:
                raise ValidationError('Verified process identity required.')
            metadata = None if process is None else canonical_json(asdict(process))
            self.db.execute('''UPDATE launch_attempts SET state=?, revision=revision+1,
                 reason=coalesce(?,reason),cleanup_confirmed=?,process_identity=coalesce(?,process_identity),exit_code=?
                 WHERE launch_id=? AND revision=?''',
                (target,reason,int(cleanup),metadata,exit_code,launch_id,revision))
            if target == 'TERMINAL':
                self.db.execute('UPDATE resource_leases SET held=0,revision=revision+1 WHERE execution_id=?',(row['execution_id'],))
        return self.launch(launch_id)

    def acquire_lease(self, execution_id, resource_key, fence, expires_at, now, *, reservation=None):
        if type(resource_key) is not str or not resource_key or len(resource_key)>256:
            raise ValidationError('Invalid resource key.')
        if timestamp(expires_at) <= max(now,self.now()):
            raise AuthorityError('Expired lease.')
        with self.transaction('lease'):
            runtime = self.runtime(execution_id)
            grant = self.registry.load('ExecutionGrant',execution_id)
            if (type(reservation) is not Reservation or reservation['owner_task']!=grant['task_id'] or
                    reservation['status']!='ACTIVE'):
                raise AuthorityError('Exact trusted resource reservation required.')
            resource_json=canonical_json(reservation.to_dict())
            RequiredLease(resource_key,execution_id,fence,expires_at,1,True,False,resource_json)
            if (runtime['revoked'] or fence != runtime['fencing_epoch'] or resource_key not in grant['reserved_resources']
                    or timestamp(expires_at)>timestamp(grant['expires_at'])):
                raise AuthorityError('Lease authority mismatch.')
            prior = self.db.execute('SELECT * FROM resource_leases WHERE resource_key=?',(resource_key,)).fetchone()
            # Expiry does not prove old descendants stopped. Never steal a held lease.
            if prior and (prior['held'] or fence <= prior['fencing_epoch']):
                raise AuthorityError('Lease held or stale fence.')
            self.db.execute('''INSERT INTO resource_leases VALUES (?,?,?,?,1,1,0,?,?)
                ON CONFLICT(resource_key) DO UPDATE SET execution_id=excluded.execution_id,
                fencing_epoch=excluded.fencing_epoch,expires_at=excluded.expires_at,held=1,
                revision=resource_leases.revision+1,revoked=0,
                resource_json=excluded.resource_json,resource_digest=excluded.resource_digest''',
                (resource_key,execution_id,fence,expires_at,resource_json,digest(reservation.to_dict())))

    def revoke_lease(self, resource_key, revision, *, context):
        self.founder(context)
        with self.transaction('revoke-lease'):
            cursor = self.db.execute('''UPDATE resource_leases SET revoked=1,revision=revision+1
                WHERE resource_key=? AND revision=? AND held=1''', (resource_key,revision))
            if cursor.rowcount != 1:
                raise AuthorityError('Stale lease revocation.')
        # held remains true until whole-launch cleanup; revocation is not release.

    def required_leases(self, execution_id):
        grant = self.registry.load('ExecutionGrant', execution_id)
        result = []
        for key in sorted(grant['reserved_resources']):
            row = self.db.execute('SELECT * FROM resource_leases WHERE resource_key=?', (key,)).fetchone()
            if row is None:
                raise AuthorityError('Required lease missing.')
            if digest(parse_json(row['resource_json'])) != row['resource_digest']:
                raise AuthorityError('Lease resource digest mismatch.')
            result.append(RequiredLease(row['resource_key'],row['execution_id'],row['fencing_epoch'],
                row['expires_at'],row['revision'],bool(row['held']),bool(row['revoked']),row['resource_json']))
        return tuple(result)


@dataclass
class DurableExecutionStore:
    runtime_registry: RuntimeRegistry
    roots: dict  # Controller-pinned TaskRoot objects, not paths supplied over IPC.
    repositories: dict

    def load(self, execution_id):
        rr = self.runtime_registry
        runtime = rr.runtime(execution_id)
        grant = rr.registry.load('ExecutionGrant',execution_id)
        task = rr.registry.get_task(grant['task_id'])
        rr.registry._active_approval(rr.registry.load('Approval',task['founder_approval']))
        profile, commands = rr.profile(runtime['profile_digest'])
        worker = rr.enrollment(runtime['enrollment_id'])
        try:
            pid = int(grant['process_scope'].removeprefix('pid:'))
            proc = ProcessIdentity(grant['boot_id'],pid,int(grant['process_start_identity']))
        except ValueError:
            raise AuthorityError('Invalid process binding.') from None
        leases = rr.required_leases(execution_id)
        # Lease expiry is checked by the supervisor/controller clock, never inferred from held alone.
        return ExecutionBinding(grant,task,worker,proc,self.roots[execution_id],profile,profile.profile_digest,
            commands,not runtime['revoked'],bool(runtime['revoked']),runtime['fencing_epoch'],
            frozenset(l.resource_key for l in leases if l.held and not l.revoked),
            self.repositories.get(execution_id),runtime['authority_revision'],leases)
