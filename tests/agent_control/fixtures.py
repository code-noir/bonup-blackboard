"""Synthetic metadata only; no application imports or runtime resources."""
from tools.agent_control.authority import AuthenticatedContext
from tools.agent_control.schema import document
from tools.agent_control.serialization import digest
from tools.agent_control.records import Task, IntegrationCandidate, task_spec_digest
from tools.agent_control.types import Role

U = '00000000-0000-4000-8000-000000000001'
T = '2026-09-11T00:00:00Z'
LATER = '2026-09-11T00:01:00Z'
ARCH = AuthenticatedContext('ARCH-01', Role.ARCHITECT, 2000)
FE = AuthenticatedContext('FE-01', Role.FRONTEND_ENGINEERING, 2001)
BE = AuthenticatedContext('BE-01', Role.BACKEND_ENGINEERING, 2002)
QA = AuthenticatedContext('QA-01', Role.INTEGRATION_QA, 2003)
FOUNDER = AuthenticatedContext('FOUNDER', Role.FOUNDER, 1000)
CONTEXTS = (ARCH, FE, BE, QA, FOUNDER)


def blank(name):
    """Populate structural defaults; each fixture supplies its semantic values."""
    defs = document('schemas.json')['$defs']
    def build(s):
        if '$ref' in s:
            return build(defs[s['$ref'].split('/')[-1]])
        if 'anyOf' in s:
            return None if {'type': 'null'} in s['anyOf'] else build(s['anyOf'][0])
        if 'const' in s:
            return s['const']
        if 'enum' in s:
            return s['enum'][0]
        kind = s['type']
        if kind == 'object':
            return {k: build(v) for k, v in s.get('properties', {}).items()}
        if kind == 'array':
            return [build(s['items']) for _ in range(s.get('minItems', 0))]
        if kind == 'boolean':
            return False
        if kind == 'integer':
            return max(0, s.get('minimum', 0))
        return {'uuid': U, 'utc-time': T, 'sha256': 'a'*64,
                'git-oid': 'a'*40, 'task-id': 'ATS-0001',
                'agent-id': 'FE-01', 'candidate-id': 'IC-ATS-0001-01',
                'record-id': 'FINDING-0001', 'money': '0',
                'relative-path': 'frontend/example.ts', 'absolute-path': '/synthetic/work',
                'branch': 'agent/ATS-0001/frontend', 'resource-key': 'synthetic'}.get(s.get('format'), 'synthetic')
    return build(defs[name])


def task_data(state='SPEC_READY'):
    d = blank('Task')
    d.update(task_id='ATS-0001', task_uuid=U, title='Synthetic task', objective='Validate pure metadata',
             requested_by=FOUNDER.actor(), architect_agent='ARCH-01', qa_agent='QA-01',
             owner_agents=['FE-01'], state=state, spec_frozen=state not in {'PROPOSED','INSPECTING'},
             policy_digest=digest(document('policy.json')),
             allowed_write_paths=[{'kind':'FILE','path':'frontend/example.ts'}],
             assignments=[{'owner_agent':'FE-01','workstream':'frontend',
               'allowed_write_paths':[{'kind':'FILE','path':'frontend/example.ts'}],
               'branch':'agent/ATS-0001/frontend','worktree':'/synthetic/work'}],
             branch={'FE-01':'agent/ATS-0001/frontend'}, worktree={'FE-01':'/synthetic/work'},
             commits=[{'agent_id':'FE-01','commit':'d'*40}],
             integration_candidates=['IC-ATS-0001-01'],
             required_tests=[{'test_id':'unit','command_id':'unit','definition_digest':'f'*64,
                              'required':True,'baseline_evidence':None}])
    if state not in {'PROPOSED','INSPECTING','SPEC_READY'}:
        d.update(approved_by=FOUNDER.actor(), founder_approval=U)
    if state in {'FOUNDER_APPROVED_FOR_INTEGRATION','INTEGRATED','PUSHED','CLOSED'}:
        d['integration_approval'] = U
    if state == 'CLOSED':
        d['close_reason'] = 'Verified terminal path'
    d['spec_digest'] = task_spec_digest(d)
    return d


def candidate(task=None):
    task = task or Task(task_data('QA_REVIEW'))
    d = blank('IntegrationCandidate')
    for k in ('task_id','spec_version','spec_digest','policy_digest','source_base_commit','required_tests'):
        d[k] = task[k]
    i = blank('Implementation')
    i.update(agent_id='FE-01', role=FE.role.value, tip_commit='d'*40, commit_ids=['d'*40])
    d.update(implementations=[i], created_by=ARCH.actor(), prepared_integration_commit='b'*40, prepared_tree='c'*40)
    del d['manifest_digest']
    return IntegrationCandidate.finalize(d)


def approval_data(task=None, action='APPROVE_SPEC', c=None):
    task = task or Task(task_data())
    d = blank('Approval')
    d.update(action=action, task_id=task['task_id'],spec_version=task['spec_version'],
             spec_digest=task['spec_digest'], authenticated_unix_uid=1000, scope=['synthetic'])
    if c:
        d.update(candidate_id=c['candidate_id'],candidate_digest=c['manifest_digest'],
                 expected_target_commit=c['expected_target_commit'],approved_result_commit=c['prepared_integration_commit'])
    return d


def evidence_data(c=None):
    c = c or candidate()
    d = blank('TestEvidence')
    d.update(candidate_id=c['candidate_id'],task_id=c['task_id'],tested_commit=c['prepared_integration_commit'],
             tested_tree=c['prepared_tree'],spec_digest=c['spec_digest'],test_definition_digest='f'*64,
             command_id='unit', result='PASS', exit_code=0, recorded_by=QA.actor())
    return d


def event_data(c=None, state='QA_PASSED'):
    c = c or candidate()
    d = blank('CandidateEvent')
    d.update(candidate_id=c['candidate_id'],candidate_digest=c['manifest_digest'], task_id=c['task_id'],
             state=state,actor=QA.actor(),evidence=[U])
    return d


def record_data(context=ARCH, kind='DECISION', resolved=True):
    d = blank('Record')
    d.update(record_id=kind+'-0001', kind=kind, task_id='ATS-0001',raised_by=context.actor(),owner=context.actor(),
             type='TECHNICAL',decision_scope='ORDINARY_TECHNICAL',ats_revision_impact='NONE',status='OPEN')
    if resolved:
        d.update(status='RESOLVED',resolution='Inspected synthetic state',resolved_by=context.actor(),resolved_at=T)
    return d
