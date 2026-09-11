import unittest
from copy import deepcopy

from fixtures import (U, T, LATER, ARCH, FE, BE, QA, FOUNDER, CONTEXTS,
                      blank, task_data, candidate, approval_data, evidence_data,
                      event_data, record_data)
from tools.agent_control.authority import AuthenticatedContext, authorize_resource
from tools.agent_control.lifecycle import TRANSITIONS, transition_task, validate_transition, revise_spec
from tools.agent_control.paths import PathRule, overlaps, permits_write
from tools.agent_control.records import (Task, AgentRecord, ExecutionGrant, Reservation,
    Record, IntegrationCandidate, Approval, TestEvidence, AuditEvent, CandidateEvent, task_spec_digest)
from tools.agent_control.serialization import canonical_json, digest, parse_json
from tools.agent_control.schema import document
from tools.agent_control.types import TaskState, Role, ValidationError


class LifecycleTests(unittest.TestCase):
    def test_every_declared_edge_and_role(self):
        for (source, target), roles in TRANSITIONS.items():
            for ctx in CONTEXTS:
                with self.subTest(source=source, target=target, role=ctx.role):
                    if ctx.role in roles:
                        validate_transition(source, target, ctx)
                    else:
                        with self.assertRaises(ValidationError):
                            validate_transition(source, target, ctx)

    def test_every_undeclared_edge_rejected(self):
        for source in TaskState:
            for target in TaskState:
                if (source, target) not in TRANSITIONS:
                    with self.subTest(source=source, target=target), self.assertRaises(ValidationError):
                        validate_transition(source, target, FOUNDER)

    def test_all_legal_operations_require_and_accept_bound_inputs(self):
        for (source, target), roles in TRANSITIONS.items():
            for ctx in CONTEXTS:
                if ctx.role not in roles or ctx == BE:
                    continue
                with self.subTest(source=source, target=target, actor=ctx.actor_id):
                    d = task_data(source.value)
                    if source == TaskState.INSPECTING and target == TaskState.ASSIGNED:
                        d.update(spec_frozen=True, founder_approval=U, approved_by=FOUNDER.actor())
                    t = Task(d)
                    c = candidate(t)
                    action = ('APPROVE_INTEGRATION' if target in {TaskState.FOUNDER_APPROVED_FOR_INTEGRATION,TaskState.INTEGRATED}
                              else 'APPROVE_PUSH' if target == TaskState.PUSHED else 'APPROVE_SPEC')
                    a = Approval(approval_data(t, action, c if action != 'APPROVE_SPEC' else None), context=FOUNDER)
                    qstate = 'CHANGES_REQUESTED' if target == TaskState.CHANGES_REQUESTED else 'QA_PASSED'
                    q = CandidateEvent(event_data(c, qstate), context=QA)
                    e = TestEvidence(evidence_data(c), context=QA)
                    r = Record(record_data(), context=ARCH)
                    result = transition_task(t,target,ctx,now=LATER,approval=a,candidate=c,
                                             qa_event=q,evidence=[e],recovery=r,reason='Synthetic transition')
                    self.assertEqual(result['state'], target.value)
                    self.assertEqual(t['state'], source.value)
                    self.assertEqual(result['record_revision'],t['record_revision']+1)

    def test_founder_declaration_is_not_transition_authority(self):
        for ctx in (None, {'actor_id':'FOUNDER'}, FE, QA):
            with self.subTest(context=type(ctx).__name__), self.assertRaises(ValidationError):
                transition_task(Task(task_data()),'FOUNDER_APPROVED',ctx,now=LATER)

    def test_engineer_cannot_self_approve(self):
        with self.assertRaises(ValidationError):
            transition_task(Task(task_data('QA_REVIEW')),'QA_PASSED',FE,now=LATER)

    def test_qa_requires_evidence_of_current_candidate(self):
        t=Task(task_data('QA_REVIEW')); c=candidate(t); q=CandidateEvent(event_data(c),context=QA)
        for evidence in ([], [TestEvidence(dict(evidence_data(c),tested_commit='e'*40),context=QA)]):
            with self.assertRaises(ValidationError):
                transition_task(t,'QA_PASSED',QA,now=LATER,candidate=c,qa_event=q,evidence=evidence)

    def test_recovery_cannot_skip_reconciliation(self):
        for state in ('BLOCKED','CONTRACT_CONFLICT','INTERRUPTED'):
            with self.subTest(state=state),self.assertRaises(ValidationError):
                transition_task(Task(task_data(state)),'INSPECTING',ARCH,now=LATER)

    def test_spec_revision_resets_approval_and_changes_digest(self):
        t=Task(task_data('CHANGES_REQUESTED'))
        changed=revise_spec(t,{'objective':'Revised synthetic objective'},ARCH,now=LATER)
        self.assertEqual(changed['spec_version'],2)
        self.assertIsNone(changed['founder_approval'])
        self.assertFalse(changed['spec_frozen'])
        self.assertNotEqual(changed['spec_digest'],t['spec_digest'])
        for ctx in (FE,BE,QA):
            with self.assertRaises(ValidationError):
                revise_spec(t,{'objective':'Unauthorized'},ctx,now=LATER)

    def test_closed_only_from_pushed(self):
        self.assertEqual([s for s,t in TRANSITIONS if t == TaskState.CLOSED],[TaskState.PUSHED])
        with self.assertRaises(ValidationError):
            transition_task(Task(task_data('PUSHED')),'CLOSED',FOUNDER,now=LATER)


class AuthorityTests(unittest.TestCase):
    def grant(self,ctx):
        d=blank('ExecutionGrant')
        d.update(agent_id=ctx.actor_id,role=ctx.role.value,spec_digest=Task(task_data())['spec_digest'])
        return d

    def test_all_agent_push_merge_escalations_rejected(self):
        for ctx in (ARCH,FE,BE,QA):
            for flag in ('can_push','can_merge'):
                with self.subTest(actor=ctx.actor_id,flag=flag),self.assertRaises(ValidationError):
                    ExecutionGrant(dict(self.grant(ctx),**{flag:True}))

    def test_qa_architect_application_write_rejected(self):
        for ctx in (ARCH,QA):
            with self.subTest(actor=ctx.actor_id),self.assertRaises(ValidationError):
                ExecutionGrant(dict(self.grant(ctx),can_write=[{'kind':'FILE','path':'backend/application.py'}]))

    def test_local_commit_and_spec_authority(self):
        for ctx in (FE,BE):
            ExecutionGrant(dict(self.grant(ctx),can_commit_local=True))
            with self.assertRaises(ValidationError):
                ExecutionGrant(dict(self.grant(ctx),can_change_task_spec=True))
        ExecutionGrant(dict(self.grant(ARCH),can_change_task_spec=True))
        with self.assertRaises(ValidationError):
            ExecutionGrant(dict(self.grant(QA),can_commit_local=True))

    def test_grant_is_bound_to_assigned_scope_and_spec(self):
        t=Task(task_data('IN_PROGRESS')); d=self.grant(FE)
        d.update(can_write=[{'kind':'FILE','path':'frontend/example.ts'}])
        ExecutionGrant(d).assert_task_binding(t)
        for changes in ({'spec_digest':'e'*64},{'worktree':'/synthetic/other'},
                        {'can_write':[{'kind':'FILE','path':'frontend/other.ts'}]}):
            with self.assertRaises(ValidationError):
                ExecutionGrant(dict(d,**changes)).assert_task_binding(t)

    def test_protected_paths_and_cross_domain_rejected(self):
        for path in ('backend/application.py','frontend/.env','AGENTS.md','docs/agent-control/policy.json'):
            with self.subTest(path=path),self.assertRaises(ValidationError):
                ExecutionGrant(dict(self.grant(FE),can_write=[{'kind':'FILE','path':path}]))

    def test_agent_registry_role_policy(self):
        for ctx in (ARCH,FE,BE,QA):
            d=blank('AgentRecord');d.update(agent_id=ctx.actor_id,role=ctx.role.value,status='IDLE')
            AgentRecord(d)
            with self.assertRaises(ValidationError):
                AgentRecord(dict(d,capabilities=['PUSH']))
            with self.assertRaises(ValidationError):
                AgentRecord(dict(d,max_concurrency=2))
        with self.assertRaises(ValidationError):
            AgentRecord(dict(d,agent_id='FOUNDER',role='FOUNDER'))

    def test_reservation_schema_and_deployment_denial(self):
        for resource in document('policy.json')['resources']:
            d=blank('Reservation');d.update(resource_type=resource,lease_expires_at=LATER)
            if resource in {'GIT_INTEGRATION','PRODUCTION_DEPLOYMENT'}:
                for ctx in (ARCH,FE,BE,QA):
                    with self.assertRaises(ValidationError): Reservation(d,context=ctx)
            else:
                Reservation(d,context=BE)
            Reservation(d,context=FOUNDER)
        for changes in ({'units':0},{'units':2},{'mode':'CAPACITY'},{'lease_expires_at':T},{'fencing_epoch':0}):
            with self.assertRaises(ValidationError): Reservation(dict(d,**changes),context=FOUNDER)

    def test_decision_authority(self):
        Record(record_data(),context=ARCH)
        for typ in ('SCOPE','SECURITY','PRODUCT','PRIORITY','BUDGET'):
            d=record_data();d.update(type=typ,decision_scope='POLICY')
            with self.assertRaises(ValidationError): Record(d,context=ARCH)
            d.update(resolved_by=FOUNDER.actor())
            Record(d,context=FOUNDER)
        with self.assertRaises(ValidationError):
            Record(dict(record_data(),decision_scope='MAJOR_ARCHITECTURE'),context=ARCH)
        for ctx in (FE,BE):
            d=record_data(ctx);d['decision_scope']='IMPLEMENTATION';Record(d,context=ctx)
        with self.assertRaises(ValidationError): Record(record_data(QA),context=QA)

    def test_future_roles_recommendation_only(self):
        ctx=AuthenticatedContext('MKT-01',Role.MARKETING,3000)
        Record(record_data(ctx,'FINDING',False),context=ctx)
        with self.assertRaises(ValidationError):Record(record_data(ctx),context=ctx)
        with self.assertRaises(ValidationError):ExecutionGrant(self.grant(ctx))


class PathTests(unittest.TestCase):
    def test_normalization_and_invalid_paths(self):
        self.assertEqual(PathRule('DIRECTORY','frontend/src/').path,'frontend/src')
        for path in ('/absolute','../escape','a/../b','a/./b','a//b','a\\b','a\x00b','a\nb','a%2fb',' a','a ','C:foo','e\u0301'):
            with self.subTest(path=repr(path)),self.assertRaises(ValidationError): PathRule('FILE',path)

    def test_overlap_file_directory_and_globs(self):
        cases=[(('FILE','a/b'),('FILE','a/b'),True), (('FILE','a/b'),('FILE','a/c'),False),
               (('DIRECTORY','a'),('FILE','a/b'),True),(('DIRECTORY','a'),('DIRECTORY','a/b'),True),
               (('DIRECTORY','a'),('DIRECTORY','ab'),False),
               (('GLOB','a/**/*.py'),('FILE','a/deep/b.py'),True),
               (('GLOB','a/*.py'),('GLOB','a/*.ts'),True),
               (('GLOB','a/*.py'),('DIRECTORY','b'),False)]
        for a,b,expected in cases:
            with self.subTest(a=a,b=b):
                self.assertEqual(overlaps(PathRule(*a),PathRule(*b)),expected)
                self.assertEqual(overlaps(PathRule(*b),PathRule(*a)),expected)

    def test_glob_matching_and_unsupported_syntax(self):
        g=PathRule('GLOB','frontend/**/*.ts')
        self.assertTrue(g.matches('frontend/a.ts'));self.assertTrue(g.matches('frontend/src/a.ts'))
        self.assertFalse(g.matches('backend/a.ts'))
        for path in ('a/?','a/[ab]','a/{b,c}','a/**x','a/*/b','a/**/**/b'):
            with self.subTest(path=path),self.assertRaises(ValidationError):PathRule('GLOB',path)

    def test_deny_before_allow(self):
        allow=[PathRule('DIRECTORY','frontend')];deny=[PathRule('FILE','frontend/private.ts')]
        self.assertTrue(permits_write('frontend/a.ts',allow,[],[]))
        self.assertFalse(permits_write('frontend/private.ts',allow,[],deny))
        self.assertFalse(permits_write('frontend/private.ts',allow,deny,[]))
        self.assertFalse(permits_write('backend/a.py',allow,[],[]))


class RecordTests(unittest.TestCase):
    def test_candidate_deep_immutability_and_digest_stability(self):
        c=candidate(); d=c.to_dict()
        d['implementations'][0]['tip_commit']='e'*40
        self.assertEqual(c['implementations'][0]['tip_commit'],'d'*40)
        with self.assertRaises(ValidationError):c.state='QA_PASSED'
        with self.assertRaises(ValidationError):c._payload='{}'
        with self.assertRaises(ValidationError):IntegrationCandidate(d)
        reordered=dict(reversed(list(c.to_dict().items())))
        self.assertEqual(IntegrationCandidate(reordered).canonical_json(),c.canonical_json())
        c.assert_unchanged(IntegrationCandidate(reordered))
        d=c.to_dict();del d['manifest_digest'];d['prepared_tree']='f'*40
        with self.assertRaises(ValidationError):c.assert_unchanged(IntegrationCandidate.finalize(d))
        with self.assertRaises(ValidationError):IntegrationCandidate.finalize(c.to_dict())

    def test_forged_founder_context_rejected(self):
        d=approval_data()
        for ctx in (None,{'actor_id':'FOUNDER','authenticated_unix_uid':1000},FE,QA):
            with self.subTest(context=type(ctx).__name__),self.assertRaises(ValidationError):Approval(d,context=ctx)
        Approval(d,context=FOUNDER)
        with self.assertRaises(ValidationError):Approval(dict(d,authenticated_unix_uid=999),context=FOUNDER)

    def test_approval_exact_binding(self):
        t=Task(task_data('QA_REVIEW'));c=candidate(t);d=approval_data(t,'APPROVE_INTEGRATION',c)
        Approval(d,context=FOUNDER).assert_binding(t,action='APPROVE_INTEGRATION',candidate=c)
        for field,value in {'spec_version':2,'spec_digest':'e'*64,'candidate_digest':'e'*64,
                            'expected_target_commit':'e'*40,'approved_result_commit':'e'*40,
                            'candidate_id':'IC-ATS-0001-02','task_id':'ATS-0002'}.items():
            with self.subTest(field=field),self.assertRaises(ValidationError):
                Approval(dict(d,**{field:value}),context=FOUNDER).assert_binding(t,action='APPROVE_INTEGRATION',candidate=c)
        with self.assertRaises(ValidationError):Approval(dict(d,candidate_digest=None),context=FOUNDER)
        with self.assertRaises(ValidationError):Approval(dict(approval_data(),action='REVOKE'),context=FOUNDER)

    def test_evidence_exact_binding_and_unknown_counts(self):
        d=evidence_data();e=TestEvidence(d,context=QA)
        keys=('task_id','candidate_id','tested_commit','tested_tree','spec_digest','test_definition_digest','execution_id','environment_profile_digest')
        expected={k:d[k] for k in keys}; e.assert_binding(**expected)
        self.assertEqual(e['counts'],{'passed':None,'failed':None,'errors':None,'skipped':None})
        for k in keys:
            with self.subTest(field=k),self.assertRaises(ValidationError):e.assert_binding(**dict(expected,**{k:'different'}))
        with self.assertRaises(ValidationError):TestEvidence(dict(d,exit_code=1),context=QA)
        with self.assertRaises(ValidationError):TestEvidence(d,context=FE)

    def test_audit_event_integrity_authority(self):
        d=blank('AuditEvent');d.update(actor=ARCH.actor());del d['event_digest']
        event=AuditEvent.finalize(d,context=ARCH)
        tampered=event.to_dict();tampered['sequence']=2
        with self.assertRaises(ValidationError):AuditEvent(tampered,context=ARCH)
        for typ in ('TASK_APPROVED','FOUNDER_APPROVED','PUSHED','INTEGRATED','QA_PASSED'):
            with self.assertRaises(ValidationError):AuditEvent.finalize(dict(d,event_type=typ),context=ARCH)

    def test_invalid_enums_ids_types_and_unknown_fields(self):
        for field,value in {'task_id':'ATS-1','task_uuid':'invalid','state':'DONE','priority':'P9',
                            'schema_version':2,'record_revision':True,'created_at':'yesterday',
                            'spec_digest':'bad','extra':'unrecognized'}.items():
            with self.subTest(field=field),self.assertRaises(ValidationError):Task(dict(task_data(),**{field:value}))
        d=task_data();del d['objective']
        with self.assertRaises(ValidationError):Task(d)

    def test_canonical_serialization_rejects_ambiguous_json(self):
        self.assertEqual(canonical_json({'z':None,'a':[True,2]}),'{"a":[true,2],"z":null}')
        self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}))
        for value in ({'a':1.0},{'a':float('nan')},{1:'x'}, {'a':object()}):
            with self.assertRaises(ValidationError):canonical_json(value)
        with self.assertRaises(ValidationError):parse_json('{"a":1,"a":2}')


class ConsistencyTests(unittest.TestCase):
    def test_overlapping_assignment_scopes_rejected(self):
        d=task_data();d['owner_agents'].append('BE-01')
        rule={'kind':'FILE','path':'docs/synthetic.md'}
        d['allowed_write_paths']=[rule]
        d['assignments'][0]['allowed_write_paths']=[rule]
        second=deepcopy(d['assignments'][0]);second.update(owner_agent='BE-01',workstream='backend',
            branch='agent/ATS-0001/backend',worktree='/synthetic/backend')
        d['assignments'].append(second)
        d['branch']['BE-01']=second['branch'];d['worktree']['BE-01']=second['worktree']
        d['spec_digest']=task_spec_digest(d)
        with self.assertRaises(ValidationError):Task(d)

    def test_change_metadata_cannot_omit_paths(self):
        c=candidate();d=c.to_dict();del d['manifest_digest']
        change=blank('PathChange')
        with self.assertRaises(ValidationError):IntegrationCandidate.finalize(dict(d,changed_files=[change]))
        change.update(status='ADD',new_path='frontend/example.ts',new_blob='e'*40,new_mode='100644')
        valid=IntegrationCandidate.finalize(dict(d,changed_files=[change]))
        valid.assert_task_binding(Task(task_data('QA_REVIEW')))
        change['new_path']='backend/foreign.py'
        with self.assertRaises(ValidationError):
            IntegrationCandidate.finalize(dict(d,changed_files=[change])).assert_task_binding(Task(task_data('QA_REVIEW')))

    def test_approval_pointer_and_identity_must_be_paired(self):
        for changes in ({'approved_by':None},{'founder_approval':None}):
            with self.assertRaises(ValidationError):Task(dict(task_data('IN_PROGRESS'),**changes))

    def test_schema_keyword_inventory_and_policy_detachment(self):
        supported={'$ref','anyOf','type','const','enum','minLength','maxLength','format','minimum',
                   'minItems','uniqueItems','items','properties','required','additionalProperties','propertyNames'}
        def visit(s):
            self.assertLessEqual(set(s),supported)
            for k in ('items','propertyNames'):
                if k in s:visit(s[k])
            if isinstance(s.get('additionalProperties'),dict):visit(s['additionalProperties'])
            for v in s.get('properties',{}).values():visit(v)
            for v in s.get('anyOf',[]):visit(v)
        for s in document('schemas.json')['$defs'].values():visit(s)
        d=document('policy.json');d['roles']['FRONTEND_ENGINEERING']['can_push']=True
        self.assertFalse(document('policy.json')['roles']['FRONTEND_ENGINEERING']['can_push'])


if __name__ == '__main__':
    unittest.main()
