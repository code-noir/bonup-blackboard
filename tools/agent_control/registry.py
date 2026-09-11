"""Transactional registry. No scheduler, OS authentication or agent execution.

AuthenticatedContext parameters must come from a trusted future adapter. Only
unapproved proposal intake may omit a context; its audit attribution is marked
as an unauthenticated declaration, never founder authorization.
"""
import hashlib
import sqlite3
from uuid import uuid4

from .authority import AuthenticatedContext, require_context, validate_actor
from .lifecycle import transition_task, revise_spec
from .records import (Task, AgentRecord, ExecutionGrant, Record, Approval,
                      IntegrationCandidate, TestEvidence, CandidateEvent, AuditEvent,
                      SPEC_FIELDS, task_spec_digest)
from .schema import document, validate_schema, valid_format
from .serialization import canonical_json, digest, parse_json
from .storage import DB_VERSION, DDL, RegistryBlocked, connect, create_database, external_path, utc_now
from .types import Role, ValidationError, AuthorityError
from .publication import GitHistory


TABLES = {'ExecutionGrant':('executions','execution_id'), 'Record':('records','record_id'),
          'Approval':('approvals','approval_id'), 'IntegrationCandidate':('candidates','candidate_id'),
          'TestEvidence':('evidence','evidence_id'), 'CandidateEvent':('candidate_events','event_id')}
CLASSES = {c.__name__:c for c in (ExecutionGrant,Record,Approval,IntegrationCandidate,TestEvidence,CandidateEvent)}


def context_data(context):
    if context is None:return None
    require_context(context)
    return dict(context.actor(), authenticated_unix_uid=context.authenticated_unix_uid)


def stored_context(data):
    """Revalidate controller-owned persisted provenance, never authenticate a request."""
    if data is None:return None
    return AuthenticatedContext(data['actor_id'],Role(data['role']),data['authenticated_unix_uid'])


def public_payload(kind, data):
    # Publish schema-limited metadata, never executable argv or process/session identifiers.
    omitted={'argv','unix_identity','session_ids','session_id','process_scope',
             'process_start_identity','boot_id','authenticated_unix_uid'}
    def project(value):
        if isinstance(value,dict):return {k:project(v) for k,v in value.items() if k not in omitted}
        if isinstance(value,list):return [project(v) for v in value]
        return value
    return {'record_type':kind,'record':project(data)}


def disabled_agent(agent_id, role):
    policy=document('policy.json')
    return AgentRecord(dict(schema_version=1,agent_id=agent_id,role=role,status='DISABLED',
        capabilities=policy['roles'][role]['capabilities'],default_read_scope=[],default_write_scope=[],
        max_concurrency=1,current_task=None,session_ids=[],usage_budget=dict(budget_id=str(uuid4()),
        allowed_models=[],max_executions=1,max_execution_seconds=1,max_tokens=0,max_cost=None),
        last_seen=None,unix_identity='UNASSIGNED',policy_version=policy['policy_version']))


class Registry:
    def __init__(self, state_path):
        self.path=external_path(state_path)
        if not self.path.is_file():raise RegistryBlocked('Registry is not initialized.')
        self.db=connect(self.path)
        try:
            self._version()
            self.startup_report=self.verify()
        except Exception:
            self.db.close()
            raise

    @classmethod
    def initialize(cls, state_path, history_path, *, operation_id):
        if not valid_format('uuid',operation_id):raise ValidationError('Operation ID must be a UUID.')
        state,history=external_path(state_path),external_path(history_path)
        if state == history or history in state.parents or state in history.parents:
            raise ValidationError('Database and history must have distinct storage paths.')
        if state.exists():
            registry=cls(state)
            if registry.meta('init_operation') != operation_id or registry.meta('history_path') != str(history):
                registry.close()
                raise RegistryBlocked('Conflicting initialization request.')
            if registry.startup_report['status']=='BLOCKED':
                registry.close()
                raise RegistryBlocked('Existing registry requires operator recovery.')
            registry.history.initialize()
            return registry
        path=create_database(state)
        db=connect(path)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            for sql in DDL:db.execute(sql)
            now=utc_now();rid=str(uuid4())
            db.execute('INSERT INTO schema_versions VALUES (?,?)',(DB_VERSION,now))
            db.executemany('INSERT INTO metadata VALUES (?,?)',[
                ('registry_id',rid),('history_path',str(history)),('init_operation',operation_id),
                ('policy_digest',digest(document('policy.json')))])
            db.executemany('INSERT INTO sequences VALUES (?,0)',[(n,) for n in ('ATS','FINDING','CONFLICT','DECISION','EVENT')])
        except Exception:
            db.rollback();db.close();raise
        registry=cls.__new__(cls)
        registry.path=path
        registry.db=db
        def bootstrap(now, changed):
            for agent_id,role in document('policy.json')['agents'].items():
                data=disabled_agent(agent_id,role).to_dict()
                registry.db.execute('INSERT INTO agents VALUES (?,?,?)',(agent_id,canonical_json(data),digest(data)))
                changed.append(('AgentRecord',agent_id,f'agents/{agent_id}.json',data))
            return {'registry_id':rid},None
        try:
            registry._operation(operation_id,'initialize',{},None,bootstrap,'REGISTRY_INITIALIZED',bootstrap=True)
            registry.history.initialize()
            registry.startup_report=registry.verify()
            return registry
        except Exception:
            registry.close()
            raise

    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def meta(self,key):
        row=self.db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
        if row is None:raise RegistryBlocked('Required registry metadata missing.')
        return row[0]

    @property
    def history(self):return GitHistory(self.meta('history_path'),self.meta('registry_id'))

    def _version(self):
        try:versions=[r[0] for r in self.db.execute('SELECT version FROM schema_versions ORDER BY version')]
        except sqlite3.DatabaseError:raise RegistryBlocked('Control schema is missing or invalid.') from None
        if versions != [DB_VERSION]:raise RegistryBlocked('Unsupported control database schema version.')

    def _next(self,kind):
        self.db.execute('UPDATE sequences SET value=value+1 WHERE name=?',(kind,))
        return self.db.execute('SELECT value FROM sequences WHERE name=?',(kind,)).fetchone()[0]

    def _operation(self, operation_id, kind, payload, context, action, event_type, *, bootstrap=False):
        if not valid_format('uuid',operation_id):raise ValidationError('Operation ID must be a UUID.')
        request_digest=digest({'kind':kind,'payload':payload,'context':context_data(context)})
        if not self.db.in_transaction:self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM maintenance_operations WHERE operation_id=?',(operation_id,)).fetchone():
                raise ValidationError('Operation ID already belongs to maintenance.')
            prior=self.db.execute('SELECT * FROM operations WHERE operation_id=?',(operation_id,)).fetchone()
            if not bootstrap and self.verify(check_history=False)['status']=='BLOCKED':
                raise RegistryBlocked('Registry consistency is blocked.')
            if prior:
                if prior['payload_digest'] != request_digest:raise ValidationError('Conflicting idempotency-key reuse.')
                self.db.commit();return parse_json(prior['result'])
            changed=[];now=utc_now()
            result,task_id=action(now,changed)
            sequence=self._next('EVENT')
            previous=self.db.execute('SELECT event_digest FROM audit_events ORDER BY sequence DESC LIMIT 1').fetchone()
            actor=context.actor() if context else {'actor_id':'ARCH-01','role':'ARCHITECT'}
            event=dict(schema_version=1,event_id=str(uuid4()),sequence=sequence,operation_id=operation_id,
                timestamp=now,actor=actor,event_type=event_type,task_id=task_id,execution_id=None,
                candidate_id=None,old_state=None,new_state=None,record_digests=[digest(x[3]) for x in changed],
                reason_code=None if context else 'UNAUTHENTICATED_LOCAL_INTAKE',
                previous_event_digest=previous[0] if previous else None)
            if context:event=AuditEvent.finalize(event,context=context).to_dict()
            else:
                event['event_digest']=digest(event)
                validate_schema('AuditEvent',event)
            self.db.execute('INSERT INTO audit_events VALUES (?,?,?,?,?)',
                (sequence,event['event_id'],operation_id,canonical_json(event),event['event_digest']))
            changed.append(('AuditEvent',event['event_id'],f'events/{sequence:012d}.json',event))
            for record_type,record_id,path,data in changed:
                self._enqueue(operation_id,record_type,record_id,path,data,now)
            self.db.execute('INSERT INTO operations VALUES (?,?,?,?)',
                (operation_id,request_digest,canonical_json(result),now))
            self.db.commit();return result
        except Exception:
            self.db.rollback();raise

    def _enqueue(self, operation_id, kind, record_id, path, data, now):
        payload=public_payload(kind,data)
        self.db.execute('INSERT INTO outbox(publication_id,operation_id,record_type,record_id,path,payload,payload_digest,created_at,source_payload,source_digest) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (str(uuid4()),operation_id,kind,record_id,path,canonical_json(payload),digest(payload),now,canonical_json(data),digest(data)))

    def get_task(self,task_id):
        row=self.db.execute('SELECT payload FROM tasks WHERE task_id=?',(task_id,)).fetchone()
        if row is None:raise ValidationError('Unknown task.')
        return Task(parse_json(row[0]))

    def list_tasks(self):return [Task(parse_json(r[0])) for r in self.db.execute('SELECT payload FROM tasks ORDER BY rowid')]
    def list_agents(self):return [AgentRecord(parse_json(r[0])) for r in self.db.execute('SELECT payload FROM agents ORDER BY agent_id')]

    def _save_task(self, task, changed):
        d=task.to_dict();tid=d['task_id']
        for dep in d['dependencies']:
            target=self.get_task(dep['task_id'])
            if dep['accepted_candidate_id']:
                c=self.load('IntegrationCandidate',dep['accepted_candidate_id'])
                if c['task_id'] != target['task_id']:raise ValidationError('Dependency candidate mismatch.')
        # No cycles, including transitive dependencies.
        def visit(tid,seen):
            if tid in seen:raise ValidationError('Cyclic task dependency.')
            children=d['dependencies'] if tid==d['task_id'] else self.get_task(tid)['dependencies']
            for dep in children:visit(dep['task_id'],seen|{tid})
        visit(tid,set())
        self.db.execute('INSERT INTO tasks VALUES (?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET payload=excluded.payload,payload_digest=excluded.payload_digest',
            (tid,d['task_uuid'],canonical_json(d),digest(d)))
        spec=self.db.execute('SELECT * FROM task_specs WHERE task_id=? AND version=?',(tid,d['spec_version'])).fetchone()
        if spec is None:
            self.db.execute('INSERT INTO task_specs VALUES (?,?,?,?,?)',
                (tid,d['spec_version'],d['spec_digest'],int(d['spec_frozen']),canonical_json(d)))
            changed.append(('TaskSpec',tid,f'tasks/{tid}/spec-v{d["spec_version"]:03d}/definition.json',
                            {k:d[k] for k in SPEC_FIELDS}|{'spec_digest':d['spec_digest']}))
        elif spec['spec_digest'] != d['spec_digest']:
            raise ValidationError('Existing specification versions are immutable.')
        elif spec['frozen'] and not d['spec_frozen']:
            raise ValidationError('Frozen specification cannot be unfrozen.')
        elif d['spec_frozen'] and not spec['frozen']:
            self.db.execute('UPDATE task_specs SET frozen=1 WHERE task_id=? AND version=?',(tid,d['spec_version']))
            changed.append(('SpecFreeze',tid,f'tasks/{tid}/spec-v{d["spec_version"]:03d}/frozen.json',
                            {'task_id':tid,'spec_version':d['spec_version'],'spec_digest':d['spec_digest'],'frozen':True}))
        changed.append(('Task',tid,f'tasks/{tid}/revisions/{d["record_revision"]:06d}.json',d))

    def create_task(self, proposal, *, operation_id, context=None):
        allowed={'title','objective','priority','source_base_commit','acceptance_criteria','allowed_write_paths',
                 'read_only_paths','forbidden_paths','required_tests','required_resources','budget','requested_by'}
        if not {'title','objective','source_base_commit'} <= set(proposal) or set(proposal)-allowed:
            raise ValidationError('Invalid proposal fields.')
        def create(now,changed):
            requested=proposal.get('requested_by',context.actor() if context else {'actor_id':'FOUNDER','role':'FOUNDER'})
            validate_actor(requested)
            d=dict(schema_version=1,task_id=f'ATS-{self._next("ATS"):04d}',task_uuid=str(uuid4()),record_revision=1,
                title=proposal['title'],objective=proposal['objective'],acceptance_criteria=[],priority='P2',state='PROPOSED',
                requested_by=requested,approved_by=None,created_at=now,updated_at=now,spec_version=1,spec_frozen=False,
                policy_digest=digest(document('policy.json')),source_base_commit=proposal['source_base_commit'],
                architect_agent='ARCH-01',owner_agents=[],qa_agent='QA-01',assignments=[],allowed_write_paths=[],
                read_only_paths=[],forbidden_paths=[],dependencies=[],blocked_by=[],required_resources=[],resource_reservations=[],
                branch={},worktree={},session_ids=[],required_tests=[],validation_results=[],changed_files=[],commits=[],
                integration_candidates=[],conflicts=[],findings=[],decisions=[],
                heartbeat={'last_supervisor_at':None,'last_progress_at':None,'execution_ids':[]},lease_expires_at=None,
                estimated_cost=None,actual_cost=None,token_usage={'input_tokens':None,'cached_input_tokens':None,
                'output_tokens':None,'quality':'UNKNOWN'},budget=dict(budget_id=str(uuid4()),allowed_models=[],
                max_executions=1,max_execution_seconds=1,max_tokens=0,max_cost=None),founder_approval=None,
                integration_approval=None,handoff=None,close_reason=None)
            d.update(proposal);d['spec_digest']=task_spec_digest(d)
            task=Task(d);self._save_task(task,changed)
            return task.to_dict(),task['task_id']
        return Task(self._operation(operation_id,'task.create',proposal,context,create,'TASK_CREATED'))

    def revise_task(self,task_id,changes,*,operation_id,context):
        require_context(context,roles={Role.ARCHITECT})
        def revise(now,published):
            task=revise_spec(self.get_task(task_id),changes,context,now=now)
            self.db.execute('UPDATE candidates SET invalidated=1 WHERE task_id=?',(task_id,))
            self._save_task(task,published);return task.to_dict(),task_id
        return Task(self._operation(operation_id,'task.revise',{'task_id':task_id,'changes':changes},context,revise,'SPEC_VERSION_CREATED'))

    def attach_dependencies(self,task_id,dependencies,*,operation_id,context):
        return self.revise_task(task_id,{'dependencies':dependencies},operation_id=operation_id,context=context)

    def assign_metadata(self,task_id,assignments,*,operation_id,context):
        require_context(context,roles={Role.ARCHITECT})
        def assign(now,changed):
            t=self.get_task(task_id);d=t.to_dict()
            if d['state'] not in {'PROPOSED','INSPECTING','SPEC_READY','FOUNDER_APPROVED'}:
                raise AuthorityError('Assignment changes require inspection before execution.')
            d.update(owner_agents=[a['owner_agent'] for a in assignments],assignments=assignments,
                     branch={a['owner_agent']:a['branch'] for a in assignments},
                     worktree={a['owner_agent']:a['worktree'] for a in assignments},
                     updated_at=now,record_revision=d['record_revision']+1)
            t=Task(d);self._save_task(t,changed);return t.to_dict(),task_id
        return Task(self._operation(operation_id,'task.assign_metadata',{'task_id':task_id,'assignments':assignments},context,assign,'AGENT_ASSIGNED'))

    def checkpoint(self,task_id,handoff,*,operation_id,context):
        require_context(context)
        def checkpoint(now,changed):
            t=self.get_task(task_id);d=t.to_dict()
            if context.actor_id not in d['owner_agents']+[d['architect_agent']]:raise AuthorityError('Checkpoint requires task ownership.')
            validate_schema('Handoff',handoff)
            d.update(handoff=handoff,updated_at=now,record_revision=d['record_revision']+1)
            t=Task(d);self._save_task(t,changed);return t.to_dict(),task_id
        return Task(self._operation(operation_id,'task.checkpoint',{'task_id':task_id,'handoff':handoff},context,checkpoint,'TASK_CHECKPOINT'))

    def transition(self,task_id,target,*,operation_id,context,approval_id=None,candidate_id=None,
                   qa_event_id=None,evidence_ids=(),recovery_id=None,reason=None):
        require_context(context)
        payload=dict(task_id=task_id,target=target,approval_id=approval_id,candidate_id=candidate_id,
                     qa_event_id=qa_event_id,evidence_ids=list(evidence_ids),recovery_id=recovery_id,reason=reason)
        event_type={'FOUNDER_APPROVED':'TASK_APPROVED','IN_PROGRESS':'WORK_STARTED','QA_PASSED':'QA_PASSED',
                    'FOUNDER_APPROVED_FOR_INTEGRATION':'FOUNDER_APPROVED','INTERRUPTED':'INTERRUPTED',
                    'INTEGRATED':'INTEGRATED','PUSHED':'PUSHED','SPEC_READY':'SPEC_FROZEN','INSPECTING':'RECOVERED',
                    'CONTRACT_CONFLICT':'SPEC_CONFLICT'}.get(target,'TASK_METADATA_UPDATED')
        def change(now,changed):
            if target in {'INTEGRATED','PUSHED'}:raise AuthorityError('Git integration/push receipts are not enabled in Milestone 2.')
            t=self.get_task(task_id)
            c=self.load('IntegrationCandidate',candidate_id) if candidate_id else None
            if c:self._active_candidate(c,t)
            a=self.load('Approval',approval_id) if approval_id else None
            if a:self._active_approval(a)
            q=self.load('CandidateEvent',qa_event_id) if qa_event_id else None
            e=[self.load('TestEvidence',i) for i in evidence_ids]
            r=self.load('Record',recovery_id) if recovery_id else None
            updated=transition_task(t,target,context,now=now,approval=a,candidate=c,qa_event=q,evidence=e,recovery=r,reason=reason)
            self._save_task(updated,changed);return updated.to_dict(),task_id
        return Task(self._operation(operation_id,'task.transition',payload,context,change,event_type))

    def freeze_spec(self,task_id,*,operation_id,context):
        return self.transition(task_id,'SPEC_READY',operation_id=operation_id,context=context)

    def load(self,kind,record_id):
        table,_=TABLES[kind]
        row=self.db.execute(f'SELECT * FROM {table} WHERE record_id=?',(record_id,)).fetchone()
        if row is None:raise ValidationError('Unknown control record.')
        return CLASSES[kind](parse_json(row['payload']),context=stored_context(parse_json(row['context'])))

    def _active_candidate(self,candidate,task):
        row=self.db.execute('SELECT invalidated FROM candidates WHERE record_id=?',(candidate['candidate_id'],)).fetchone()
        if row is None or row[0]:raise ValidationError('Candidate is invalidated.')
        candidate.assert_task_binding(task)
        self._active_approval(self.load('Approval',task['founder_approval']))

    def _active_approval(self,approval):
        for row in self.db.execute('SELECT payload FROM approvals WHERE task_id=?',(approval['task_id'],)):
            later=parse_json(row[0])
            if later['supersedes']==approval['approval_id']:raise AuthorityError('Approval has been superseded or revoked.')
        if approval['action'] not in {'APPROVE_SPEC','APPROVE_INTEGRATION','APPROVE_PUSH'}:
            raise AuthorityError('Record does not authorize approval.')

    def _approval_binding(self,approval):
        d=approval.to_dict()
        spec=self.db.execute('SELECT spec_digest,frozen FROM task_specs WHERE task_id=? AND version=?',(d['task_id'],d['spec_version'])).fetchone()
        if spec is None or spec[0]!=d['spec_digest'] or not spec[1]:raise ValidationError('Approval requires its exact frozen specification.')
        if d['candidate_id']:
            c=self.load('IntegrationCandidate',d['candidate_id'])
            for key,expected in {'task_id':c['task_id'],'spec_version':c['spec_version'],'spec_digest':c['spec_digest'],
                'candidate_digest':c['manifest_digest'],'expected_target_commit':c['expected_target_commit'],
                'approved_result_commit':c['prepared_integration_commit']}.items():
                if d[key]!=expected:raise ValidationError('Approval candidate binding mismatch.')
        if d['supersedes']:
            old=self.load('Approval',d['supersedes'])
            if any(old[k]!=d[k] for k in ('task_id','spec_version','spec_digest','candidate_id','candidate_digest')):
                raise ValidationError('Supersession belongs to another approval subject.')

    def put_metadata(self,kind,data,*,operation_id,context):
        if kind not in TABLES or kind=='Record':raise ValidationError('Use dedicated record operations.')
        require_context(context)
        def save(now,changed):
            obj=CLASSES[kind](data,context=context);d=obj.to_dict();t=self.get_task(d['task_id'])
            table,id_field=TABLES[kind];record_id=d[id_field]
            if self.db.execute(f'SELECT 1 FROM {table} WHERE record_id=?',(record_id,)).fetchone():
                raise ValidationError('Record ID already exists; retry its original operation ID.')
            if kind=='IntegrationCandidate':
                require_context(context,roles={Role.ARCHITECT},actor_id=t['architect_agent'])
                obj.assert_task_binding(t)
            elif kind=='Approval':
                self._approval_binding(obj)
                if d['action'].startswith('APPROVE_'):
                    if d['spec_digest']!=t['spec_digest']:raise ValidationError('Cannot approve a superseded specification.')
                    if d['candidate_id']:self._active_candidate(self.load('IntegrationCandidate',d['candidate_id']),t)
            elif kind=='ExecutionGrant':
                require_context(context,roles={Role.ARCHITECT},actor_id=t['architect_agent'])
                obj.assert_task_binding(t)
                self._active_approval(self.load('Approval',t['founder_approval']))
                if d['session_id'] is not None or d['reserved_resources']:
                    raise AuthorityError('Only dormant execution metadata is supported.')
            elif kind=='TestEvidence':
                grant=self.load('ExecutionGrant',d['execution_id'])
                if grant['task_id']!=t['task_id'] or grant['agent_id']!=context.actor_id or grant['spec_digest']!=d['spec_digest']:
                    raise AuthorityError('Evidence execution/spec/actor mismatch.')
                if d['candidate_id']:
                    c=self.load('IntegrationCandidate',d['candidate_id']);self._active_candidate(c,t)
                    obj.assert_binding(task_id=t['task_id'],candidate_id=c['candidate_id'],tested_commit=c['prepared_integration_commit'],
                        tested_tree=c['prepared_tree'],spec_digest=c['spec_digest'],test_definition_digest=d['test_definition_digest'],
                        execution_id=grant['execution_id'],environment_profile_digest=d['environment_profile_digest'])
                    if d['test_definition_digest'] not in {x['definition_digest'] for x in c['required_tests']}:
                        raise ValidationError('Evidence test definition is not required by the candidate.')
                elif d['spec_digest']!=t['spec_digest']:raise ValidationError('Evidence belongs to an old specification.')
            elif kind=='CandidateEvent':
                c=self.load('IntegrationCandidate',d['candidate_id']);self._active_candidate(c,t);obj.assert_binding(c)
                if d['actor']['actor_id'] not in {t['architect_agent'],t['qa_agent'],'FOUNDER'}:raise AuthorityError('Unassigned reviewer.')
                for eid in d['evidence']:
                    if self.load('TestEvidence',eid)['candidate_id']!=c['candidate_id']:raise ValidationError('QA evidence belongs to another candidate.')
                if d['approval_id']:
                    a=self.load('Approval',d['approval_id']);self._active_approval(a)
                    a.assert_binding(t,action='APPROVE_INTEGRATION',candidate=c)
            columns=['record_id','task_id','payload','payload_digest','context']
            values=[record_id,d['task_id'],canonical_json(d),digest(d),canonical_json(context_data(context))]
            extras={}
            if kind=='IntegrationCandidate':extras={'spec_version':d['spec_version']}
            if kind=='Approval':extras={'spec_version':d['spec_version'],'candidate_id':d['candidate_id']}
            if kind=='ExecutionGrant':extras={'agent_id':d['agent_id']}
            if kind=='TestEvidence':extras={'candidate_id':d['candidate_id'],'execution_id':d['execution_id']}
            if kind=='CandidateEvent':extras={'candidate_id':d['candidate_id']}
            columns+=list(extras);values+=list(extras.values())
            self.db.execute(f'INSERT INTO {table}({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',values)
            changed.append((kind,record_id,f'{table}/{record_id}.json',d))
            if kind=='IntegrationCandidate':
                td=t.to_dict();td['integration_candidates'].append(record_id)
                td.update(record_revision=td['record_revision']+1,updated_at=now);self._save_task(Task(td),changed)
            if kind=='CandidateEvent' and d['state']=='INVALIDATED':
                self.db.execute('UPDATE candidates SET invalidated=1 WHERE record_id=?',(d['candidate_id'],))
            return d,d['task_id']
        typ={'IntegrationCandidate':'CANDIDATE_CREATED','Approval':'FOUNDER_APPROVED','ExecutionGrant':'EXECUTION_RECORDED',
             'TestEvidence':'EVIDENCE_RECORDED','CandidateEvent':'CANDIDATE_REVIEWED'}[kind]
        result=self._operation(operation_id,'metadata.'+kind,data,context,save,typ)
        return CLASSES[kind](result,context=context)

    def create_record(self,body,*,operation_id,context):
        require_context(context)
        if 'record_id' in body:raise ValidationError('Record IDs are registry-allocated.')
        def create(now,changed):
            kind=body['kind']
            if kind not in {'FINDING','CONFLICT','DECISION'}:raise ValidationError('Invalid record kind.')
            d=dict(body,record_id=f'{kind}-{self._next(kind):04d}',created_at=now)
            if d['status']!='OPEN':raise AuthorityError('New records must begin as open recommendations.')
            r=Record(d,context=context)
            self.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?)',(d['record_id'],d['task_id'],kind,'OPEN',1,
                r.canonical_json(),digest(d),canonical_json(context_data(context))))
            changed.append(('Record',d['record_id'],f'{kind.lower()}s/{d["record_id"]}/v001.json',d))
            return d,d['task_id']
        return Record(self._operation(operation_id,'record.create',body,context,create,'RECORD_CREATED'),context=context)

    def resolve_record(self,record_id,resolution,*,operation_id,context,status='RESOLVED',superseded_by=None):
        require_context(context)
        if status not in {'RESOLVED','REJECTED','SUPERSEDED'}:raise ValidationError('Invalid resolution status.')
        def resolve(now,changed):
            old=self.load('Record',record_id);d=old.to_dict()
            if d['status']!='OPEN':raise ValidationError('Record is already resolved.')
            if status=='SUPERSEDED':
                if not superseded_by:raise ValidationError('Supersession requires its replacement record.')
                replacement=self.load('Record',superseded_by)
                if record_id not in replacement['supersedes'] or replacement['task_id']!=d['task_id']:
                    raise ValidationError('Replacement must explicitly supersede this task record.')
            d.update(status=status,resolution=resolution,resolved_by=context.actor(),resolved_at=now)
            obj=Record(d,context=context)
            rev=self.db.execute('SELECT revision FROM records WHERE record_id=?',(record_id,)).fetchone()[0]+1
            self.db.execute('UPDATE records SET status=?,revision=?,payload=?,payload_digest=?,context=? WHERE record_id=?',
                (status,rev,obj.canonical_json(),digest(d),canonical_json(context_data(context)),record_id))
            changed.append(('Record',record_id,f'{d["kind"].lower()}s/{record_id}/v{rev:03d}.json',d))
            return d,d['task_id']
        return Record(self._operation(operation_id,'record.resolve',dict(record_id=record_id,resolution=resolution,status=status,
            superseded_by=superseded_by),context,resolve,'RECORD_SUPERSEDED' if status=='SUPERSEDED' else 'RECORD_RESOLVED'),context=context)

    def list_records(self,task_id=None,unresolved=False):
        rows=self.db.execute('SELECT record_id FROM records WHERE (? IS NULL OR task_id=?) AND (?=0 OR status=?) ORDER BY rowid',
                             (task_id,task_id,int(unresolved),'OPEN'))
        return [self.load('Record',r[0]) for r in rows]

    def publication_status(self):
        total=self.db.execute('SELECT count(*) FROM outbox').fetchone()[0]
        ack=self.db.execute('SELECT count(*) FROM publications').fetchone()[0]
        return {'total':total,'acknowledged':ack,'pending':total-ack}

    def verify(self, *, check_history=True):
        """Read-only consistency report; never guesses through corruption."""
        owns_transaction=not self.db.in_transaction
        if owns_transaction:self.db.execute('BEGIN IMMEDIATE')
        try:
            self._version()
            if self.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RegistryBlocked('SQLite integrity check failed.')
            if self.db.execute('PRAGMA foreign_key_check').fetchall():raise RegistryBlocked('Foreign-key integrity failed.')
            if self.meta('policy_digest')!=digest(document('policy.json')):raise RegistryBlocked('Registry policy differs from installed policy.')
            tasks=self.list_tasks()
            agents=self.list_agents()
            if {a['agent_id'] for a in agents}!=set(document('policy.json')['agents']):raise RegistryBlocked('Phase I agent inventory mismatch.')
            if any(a['status']!='DISABLED' or a['session_ids'] or a['current_task'] for a in agents):
                raise RegistryBlocked('Milestone 2 cannot activate agents.')
            for table in ('tasks','agents',*(v[0] for v in TABLES.values())):
                for row in self.db.execute(f'SELECT * FROM {table}'):
                    data=parse_json(row['payload'])
                    if digest(data)!=row['payload_digest']:raise RegistryBlocked('Stored record digest mismatch.')
                    if table not in {'tasks','agents'}:
                        kind=next(k for k,v in TABLES.items() if v[0]==table)
                        obj=self.load(kind,row['record_id'])
                        if obj[TABLES[kind][1]]!=row['record_id'] or obj['task_id']!=row['task_id']:
                            raise RegistryBlocked('Record identity mismatch.')
                        if kind=='Approval':self._approval_binding(obj)
                        if kind=='Record' and (obj['kind']!=row['kind'] or obj['status']!=row['status']):
                            raise RegistryBlocked('Record status mismatch.')
                        if kind=='CandidateEvent':obj.assert_binding(self.load('IntegrationCandidate',obj['candidate_id']))
                        if kind=='TestEvidence':
                            g=self.load('ExecutionGrant',obj['execution_id'])
                            if g['task_id']!=obj['task_id'] or g['spec_digest']!=obj['spec_digest'] or g['agent_id']!=obj['recorded_by']['actor_id']:
                                raise RegistryBlocked('Evidence execution mismatch.')
                            if obj['candidate_id']:
                                c=self.load('IntegrationCandidate',obj['candidate_id'])
                                if any(obj[k]!=expected for k,expected in {'tested_commit':c['prepared_integration_commit'],
                                    'tested_tree':c['prepared_tree'],'task_id':c['task_id'],'spec_digest':c['spec_digest']}.items()):
                                    raise RegistryBlocked('Evidence candidate mismatch.')
                    # Latest durable snapshot must corroborate current mutable/immutable records.
                    kind = 'Task' if table=='tasks' else 'AgentRecord' if table=='agents' else kind
                    identifier=data['task_id'] if table=='tasks' else data['agent_id'] if table=='agents' else row['record_id']
                    snapshot=self.db.execute('SELECT source_digest FROM outbox WHERE record_type=? AND record_id=? ORDER BY outbox_id DESC LIMIT 1',(kind,identifier)).fetchone()
                    if snapshot is None or snapshot[0]!=digest(data):raise RegistryBlocked('Record differs from durable publication snapshot.')
            for row in self.db.execute('SELECT * FROM task_specs'):
                snapshot=Task(parse_json(row['payload']))
                if snapshot['task_id']!=row['task_id'] or snapshot['spec_version']!=row['version'] or snapshot['spec_digest']!=row['spec_digest']:
                    raise RegistryBlocked('Task specification digest mismatch.')
            for t in tasks:
                row=self.db.execute('SELECT * FROM task_specs WHERE task_id=? AND version=?',(t['task_id'],t['spec_version'])).fetchone()
                if row is None or row['spec_digest']!=t['spec_digest'] or bool(row['frozen'])!=t['spec_frozen']:
                    raise RegistryBlocked('Current task/spec mismatch.')
                for dependency in t['dependencies']:self.get_task(dependency['task_id'])
                for aid in (t['founder_approval'],t['integration_approval']):
                    if aid:
                        a=self.load('Approval',aid)
                        if a['task_id']!=t['task_id'] or a['spec_digest']!=t['spec_digest']:
                            raise RegistryBlocked('Task approval pointer mismatch.')
                for cid in t['integration_candidates']:
                    if self.load('IntegrationCandidate',cid)['task_id']!=t['task_id']:raise RegistryBlocked('Task candidate pointer mismatch.')
            for kind,table,column in [('ATS','tasks','task_id'),('FINDING','records','record_id'),('CONFLICT','records','record_id'),('DECISION','records','record_id')]:
                numbers=[int(r[0].rsplit('-',1)[-1]) for r in self.db.execute(f'SELECT {column} FROM {table} WHERE {column} LIKE ?',(kind+'-%',))]
                seq=self.db.execute('SELECT value FROM sequences WHERE name=?',(kind,)).fetchone()
                if seq is None or seq[0]<max(numbers,default=0):raise RegistryBlocked('Display ID sequence is behind durable records.')
            previous=None;events={}
            for expected,row in enumerate(self.db.execute('SELECT * FROM audit_events ORDER BY sequence'),1):
                event=parse_json(row['payload']);validate_schema('AuditEvent',event)
                body={k:v for k,v in event.items() if k!='event_digest'}
                if (row['sequence']!=expected or event['sequence']!=expected or event['event_id']!=row['event_id']
                    or event['operation_id']!=row['operation_id'] or event['previous_event_digest']!=previous
                    or digest(body)!=event['event_digest'] or row['event_digest']!=event['event_digest']):
                    raise RegistryBlocked('Audit event chain is broken.')
                previous=event['event_digest'];events[event['operation_id']]=event
            seq=self.db.execute('SELECT value FROM sequences WHERE name=?',('EVENT',)).fetchone()
            if seq is None or seq[0]!=len(events):raise RegistryBlocked('Audit sequence is missing events.')
            ops={r[0] for r in self.db.execute('SELECT operation_id FROM operations')}
            if ops!=set(events):raise RegistryBlocked('Operations and audit events differ.')
            items=[dict(r) for r in self.db.execute('SELECT * FROM outbox ORDER BY outbox_id')]
            if {i['operation_id'] for i in items}!=ops:raise RegistryBlocked('Operation is missing its outbox.')
            for item in items:
                payload,source=parse_json(item['payload']),parse_json(item['source_payload'])
                if (digest(payload)!=item['payload_digest'] or digest(source)!=item['source_digest']
                    or payload!=public_payload(item['record_type'],source)):
                    raise RegistryBlocked('Outbox publication digest mismatch.')
                event=events[item['operation_id']]
                if item['record_type']=='AuditEvent':
                    if source!=event:raise RegistryBlocked('Outbox audit event mismatch.')
                elif item['source_digest'] not in event['record_digests']:
                    raise RegistryBlocked('Outbox snapshot is not bound to its event.')
            for op,event in events.items():
                actual=[i['source_digest'] for i in items if i['operation_id']==op and i['record_type']!='AuditEvent']
                if actual!=event['record_digests'] or sum(i['operation_id']==op and i['record_type']=='AuditEvent' for i in items)!=1:
                    raise RegistryBlocked('Outbox snapshot/event cardinality mismatch.')
            acknowledgements={r['outbox_id']:dict(r) for r in self.db.execute('SELECT * FROM publications')}
            for item in items:
                ack=acknowledgements.get(item['outbox_id'])
                if ack and any(ack[k]!=item[k] for k in ('publication_id','record_type','record_id','payload_digest')):
                    raise RegistryBlocked('Publication acknowledgement binding mismatch.')
            if check_history:
                history=self.history
                if history.path.exists():
                    history.verify_identity();history.verify_paths([i['path'] for i in items])
                    for item in items:
                        ack=acknowledgements.get(item['outbox_id'])
                        if ack:history.verify_ack(item,ack)
                        else:history._existing(item['path'],parse_json(item['payload']))
                elif acknowledgements:raise RegistryBlocked('Acknowledged history repository is missing.')
            pending=len(items)-len(acknowledgements)
            return {'status':'DEGRADED' if pending else 'HEALTHY','pending_publications':pending,'issues':[]}
        except (RegistryBlocked,ValidationError,sqlite3.DatabaseError,KeyError,TypeError,ValueError,OSError) as error:
            # Do not echo SQL values, stderr, paths or user/customer input.
            message=str(error) if isinstance(error,RegistryBlocked) else 'Invalid durable control record.'
            return {'status':'BLOCKED','pending_publications':None,'issues':[message]}
        finally:
            if owns_transaction:self.db.rollback()

    def reconcile(self, *, operation_id, after_publish=None):
        """At-least-once publication; optional fault hook is for synthetic tests."""
        if not valid_format('uuid',operation_id):raise ValidationError('Operation ID must be a UUID.')
        request=digest({'action':'publication.reconcile','registry_id':self.meta('registry_id')})
        prior=self._claim_maintenance(operation_id,request)
        if prior is not None:
            if self.verify()['status']=='BLOCKED':raise RegistryBlocked('Publication consistency is blocked.')
            return prior
        report=self.verify()
        if report['status']=='BLOCKED':raise RegistryBlocked('Publication consistency is blocked.')
        self.history.initialize()
        items=[dict(r) for r in self.db.execute('SELECT o.* FROM outbox o LEFT JOIN publications p USING(outbox_id) WHERE p.outbox_id IS NULL ORDER BY o.outbox_id')]
        for item in items:
            oid=self.history.publish(item)
            if after_publish:after_publish(item,oid)
            self.db.execute('BEGIN IMMEDIATE')
            try:
                prior=self.db.execute('SELECT * FROM publications WHERE outbox_id=?',(item['outbox_id'],)).fetchone()
                if prior:
                    if prior['git_commit']!=oid or prior['payload_digest']!=item['payload_digest']:
                        raise RegistryBlocked('Conflicting publication acknowledgement.')
                else:
                    self.db.execute('INSERT INTO publications VALUES (?,?,?,?,?,?,?,?)',(item['publication_id'],item['outbox_id'],
                        item['record_type'],item['record_id'],item['payload_digest'],oid,utc_now(),'ACKNOWLEDGED'))
                self.db.commit()
            except Exception:self.db.rollback();raise
        result=self.verify()
        if result['status']=='BLOCKED':raise RegistryBlocked('Post-publication verification failed.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM operations WHERE operation_id=?',(operation_id,)).fetchone():
                raise ValidationError('Operation ID already belongs to a domain operation.')
            prior=self.db.execute('SELECT * FROM maintenance_operations WHERE operation_id=?',(operation_id,)).fetchone()
            if prior and prior['payload_digest']!=request:raise ValidationError('Conflicting maintenance operation ID.')
            self.db.execute('UPDATE maintenance_operations SET result=? WHERE operation_id=?',(canonical_json(result),operation_id))
            self.db.commit()
        except Exception:self.db.rollback();raise
        return result

    def backup(self,destination,*,operation_id):
        if not valid_format('uuid',operation_id):raise ValidationError('Operation ID must be a UUID.')
        destination=external_path(destination)
        if destination==self.path or self.history.path in destination.parents:
            raise ValidationError('Backup must have its own separate path.')
        if self.verify()['status']=='BLOCKED':raise RegistryBlocked('Do not back up blocked state as verified.')
        request=digest({'action':'backup','destination':str(destination)})
        prior=self._claim_maintenance(operation_id,request)
        if prior is not None:
            self._verify_backup(destination)
            if hashlib.sha256(destination.read_bytes()).hexdigest()!=prior['backup_digest']:
                raise RegistryBlocked('Backup content no longer matches its acknowledgement.')
            return prior
        # Refuse replacement, including a previous incomplete backup: never guess through it.
        create_database(destination)
        backup=sqlite3.connect(destination)
        try:self.db.backup(backup)
        finally:backup.close()
        self._verify_backup(destination)
        result={'status':'VERIFIED','operation_id':operation_id,'backup_digest':hashlib.sha256(destination.read_bytes()).hexdigest()}
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('UPDATE maintenance_operations SET result=? WHERE operation_id=?',(canonical_json(result),operation_id))
            self.db.commit()
        except Exception:self.db.rollback();raise
        return result

    def _verify_backup(self,path):
        db=connect(path)
        try:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
                raise RegistryBlocked('Backup integrity failed.')
            identity=db.execute("SELECT value FROM metadata WHERE key='registry_id'").fetchone()
            if identity is None or identity[0]!=self.meta('registry_id'):raise RegistryBlocked('Backup registry identity mismatch.')
        finally:db.close()

    def _claim_maintenance(self,operation_id,request):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM operations WHERE operation_id=?',(operation_id,)).fetchone():
                raise ValidationError('Operation ID already belongs to a domain operation.')
            prior=self.db.execute('SELECT * FROM maintenance_operations WHERE operation_id=?',(operation_id,)).fetchone()
            if prior and prior['payload_digest']!=request:raise ValidationError('Conflicting maintenance operation ID.')
            if not prior:
                self.db.execute('INSERT INTO maintenance_operations VALUES (?,?,?)',(operation_id,request,'null'))
            self.db.commit()
            return parse_json(prior['result']) if prior else None
        except Exception:
            self.db.rollback();raise

    def submit_commit_metadata(self,task_id,commit,*,operation_id,context):
        """Record an owner's submitted OID; does not execute or verify application Git."""
        require_context(context,roles={Role.FRONTEND_ENGINEERING,Role.BACKEND_ENGINEERING})
        if not valid_format('git-oid',commit):raise ValidationError('Expected an exact commit OID.')
        def submit(now,changed):
            t=self.get_task(task_id);d=t.to_dict()
            if context.actor_id not in d['owner_agents'] or d['state']!='IN_PROGRESS':
                raise AuthorityError('Commit metadata requires active task ownership.')
            d['commits']=[c for c in d['commits'] if c['agent_id']!=context.actor_id]+[{'agent_id':context.actor_id,'commit':commit}]
            d.update(record_revision=d['record_revision']+1,updated_at=now)
            self.db.execute('UPDATE candidates SET invalidated=1 WHERE task_id=?',(task_id,))
            self._save_task(Task(d),changed);return d,task_id
        return Task(self._operation(operation_id,'task.submit_metadata',dict(task_id=task_id,commit=commit),context,submit,'TASK_METADATA_UPDATED'))
