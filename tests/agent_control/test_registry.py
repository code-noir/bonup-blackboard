"""Bounded synthetic SQLite/Git tests. No application settings or network."""
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fixtures import ARCH,FE,QA,FOUNDER,record_data,blank
from tools.agent_control.__main__ import main
from tools.agent_control.registry import Registry
from tools.agent_control.serialization import digest,canonical_json,parse_json
from tools.agent_control.storage import RegistryBlocked
from tools.agent_control.types import ValidationError


def op():return str(uuid4())
def proposal(title='Synthetic task'):
    return {'title':title,'objective':'Check synthetic durable state','source_base_commit':'a'*40}


def worker_task(args):
    path,key,title=args
    with Registry(path) as registry:
        return registry.create_task(proposal(title),operation_id=key)['task_id']


def worker_record(args):
    path,key,kind,task_id=args
    with Registry(path) as registry:
        d=record_data(ARCH,kind,False);d.pop('record_id');d['task_id']=task_id
        return registry.create_record(d,operation_id=key,context=ARCH)['record_id']


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='bonup-control-test-')
        self.root=Path(self.temp.name);self.path=self.root/'state.sqlite3';self.history=self.root/'history.git'
        self.init_op=op();self.registry=Registry.initialize(self.path,self.history,operation_id=self.init_op)
    def tearDown(self):
        self.registry.close();self.temp.cleanup()
    def task(self):return self.registry.create_task(proposal(),operation_id=op(),context=ARCH)

    def test_initialize_version_reopen_and_disabled_agents(self):
        r=self.registry
        self.assertEqual(r.db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(r.db.execute('PRAGMA journal_mode').fetchone()[0],'wal')
        self.assertEqual(r.db.execute('SELECT version FROM schema_versions').fetchone()[0],1)
        self.assertEqual(len(r.list_agents()),4)
        self.assertTrue(all(a['status']=='DISABLED' for a in r.list_agents()))
        self.assertEqual(r.verify()['status'],'DEGRADED')
        with Registry.initialize(self.path,self.history,operation_id=self.init_op) as reopened:
            self.assertEqual(reopened.meta('registry_id'),r.meta('registry_id'))
        self.assertEqual(self.path.stat().st_mode&0o777,0o600)

    def test_unsupported_schema_is_rejected(self):
        self.registry.db.execute('UPDATE schema_versions SET version=99')
        self.assertEqual(self.registry.verify()['status'],'BLOCKED')
        with self.assertRaises(RegistryBlocked):Registry(self.path)

    def test_sequential_ids_reload_and_idempotency(self):
        key=op();a=self.registry.create_task(proposal(),operation_id=key)
        events=self.registry.db.execute('SELECT count(*) FROM audit_events').fetchone()[0]
        outbox=self.registry.publication_status()
        self.assertEqual(self.registry.create_task(proposal(),operation_id=key).to_dict(),a.to_dict())
        self.assertEqual(self.registry.publication_status(),outbox)
        self.assertEqual(self.registry.db.execute('SELECT count(*) FROM audit_events').fetchone()[0],events)
        with self.assertRaises(ValidationError):self.registry.create_task(proposal('Other'),operation_id=key)
        b=self.task();self.assertEqual([a['task_id'],b['task_id']],['ATS-0001','ATS-0002'])
        with Registry(self.path) as reopened:self.assertEqual(reopened.get_task(a['task_id']).to_dict(),a.to_dict())
        # A reserved gap is allowed; no allocation walks backward or derives from Git.
        self.registry.db.execute("UPDATE sequences SET value=10 WHERE name='ATS'")
        self.assertEqual(self.task()['task_id'],'ATS-0011')

    def test_concurrent_allocation_and_racing_retries(self):
        ctx=multiprocessing.get_context('spawn')
        with ProcessPoolExecutor(max_workers=4,mp_context=ctx) as pool:
            ids=list(pool.map(worker_task,[(str(self.path),op(),f'task-{i}') for i in range(8)]))
            key=op();retries=list(pool.map(worker_task,[(str(self.path),key,'same')]*4))
        self.assertEqual(len(set(ids)),8);self.assertEqual(set(ids),{f'ATS-{i:04d}' for i in range(1,9)})
        self.assertEqual(len(set(retries)),1)
        self.assertEqual(len(self.registry.list_tasks()),9)
        self.assertNotEqual(self.registry.verify(check_history=False)['status'],'BLOCKED')

    def test_concurrent_record_allocation(self):
        tid=self.task()['task_id'];ctx=multiprocessing.get_context('spawn')
        args=[(str(self.path),op(),kind,tid) for kind in ('FINDING','CONFLICT','DECISION') for _ in range(4)]
        with ProcessPoolExecutor(max_workers=4,mp_context=ctx) as pool:ids=list(pool.map(worker_record,args))
        self.assertEqual(len(set(ids)),12)
        for kind in ('FINDING','CONFLICT','DECISION'):
            self.assertEqual({x for x in ids if x.startswith(kind)},{f'{kind}-{i:04d}' for i in range(1,5)})
        self.assertEqual(len(self.registry.list_records(tid,True)),12)

    def test_legal_transitions_and_founder_protection(self):
        r=self.registry;t=self.task();tid=t['task_id']
        t=r.transition(tid,'INSPECTING',operation_id=op(),context=ARCH)
        t=r.freeze_spec(tid,operation_id=op(),context=ARCH)
        self.assertTrue(r.get_task(tid)['spec_frozen'])
        for ctx in (FE,QA,None,{'actor_id':'FOUNDER'}):
            with self.assertRaises(ValidationError):r.transition(tid,'FOUNDER_APPROVED',operation_id=op(),context=ctx)
        with self.assertRaises(ValidationError):r.transition(tid,'CLOSED',operation_id=op(),context=FOUNDER)
        from fixtures import approval_data
        a=r.put_metadata('Approval',approval_data(t),operation_id=op(),context=FOUNDER)
        t=r.transition(tid,'FOUNDER_APPROVED',operation_id=op(),context=FOUNDER,approval_id=a['approval_id'])
        self.assertEqual(r.get_task(tid)['state'],'FOUNDER_APPROVED')

    def test_revision_dependencies_and_checkpoint(self):
        r=self.registry;a=self.task();b=self.task()
        revised=r.attach_dependencies(a['task_id'],[{'task_id':b['task_id'],'required_state':'CLOSED','accepted_candidate_id':None}],operation_id=op(),context=ARCH)
        self.assertEqual(revised['spec_version'],2)
        with self.assertRaises(ValidationError):
            r.attach_dependencies(b['task_id'],[{'task_id':a['task_id'],'required_state':'CLOSED','accepted_candidate_id':None}],operation_id=op(),context=ARCH)
        h=blank('Handoff');h['current']=['Inspect synthetic data']
        t=r.checkpoint(a['task_id'],h,operation_id=op(),context=ARCH)
        self.assertEqual(r.get_task(a['task_id'])['handoff'],h)
        self.assertEqual(r.db.execute('SELECT count(*) FROM task_specs WHERE task_id=?',(a['task_id'],)).fetchone()[0],2)
        with self.assertRaises(ValidationError):r.revise_task(a['task_id'],{'objective':'Unauthorized'},operation_id=op(),context=QA)

    def test_findings_resolution_and_founder_decisions(self):
        r=self.registry;tid=self.task()['task_id']
        d=record_data(ARCH,'CONFLICT',False);d.pop('record_id');d['task_id']=tid
        key=op();record=r.create_record(d,operation_id=key,context=ARCH)
        self.assertEqual(r.create_record(d,operation_id=key,context=ARCH).to_dict(),record.to_dict())
        r.resolve_record(record['record_id'],'Within approved scope',operation_id=op(),context=ARCH)
        d.update(kind='DECISION',type='SECURITY',decision_scope='POLICY')
        decision=r.create_record(d,operation_id=op(),context=ARCH)
        with self.assertRaises(ValidationError):r.resolve_record(decision['record_id'],'Policy change',operation_id=op(),context=ARCH)
        r.resolve_record(decision['record_id'],'Explicit policy decision',operation_id=op(),context=FOUNDER)
        self.assertEqual(r.list_records(tid,True),[])

    def test_atomic_mutation_event_outbox_rollback(self):
        r=self.registry;before=r.publication_status();key=op()
        with patch.object(r,'_enqueue',side_effect=RuntimeError('Synthetic outbox fault')):
            with self.assertRaises(RuntimeError):r.create_task(proposal(),operation_id=key)
        self.assertEqual(r.list_tasks(),[]);self.assertEqual(before,r.publication_status())
        self.assertEqual(r.create_task(proposal(),operation_id=key)['task_id'],'ATS-0001')
        self.assertEqual(r.verify()['status'],'DEGRADED')

    def test_sqlite_commit_before_publication_and_retry(self):
        self.task();r=self.registry;head=r.history.head()
        self.assertGreater(r.publication_status()['pending'],0)
        self.assertEqual(r.history.head(),head)
        key=op();report=r.reconcile(operation_id=key)
        self.assertEqual(report['status'],'HEALTHY')
        tip=r.history.head();r.reconcile(operation_id=key)
        self.assertEqual(tip,r.history.head());self.assertEqual(r.verify()['status'],'HEALTHY')
        self.assertEqual(r.history._git('remote').stdout,b'')

    def test_git_commit_before_acknowledgement_recovers(self):
        r=self.registry;r.reconcile(operation_id=op());self.task();before=r.history.head()
        seen=[]
        def crash(item,oid):seen.append((item,oid));raise RuntimeError('Synthetic crash before acknowledgement')
        with self.assertRaises(RuntimeError):r.reconcile(operation_id=op(),after_publish=crash)
        self.assertNotEqual(before,r.history.head());self.assertEqual(r.verify()['status'],'DEGRADED')
        item,oid=seen[0];r.reconcile(operation_id=op())
        ack=r.db.execute('SELECT git_commit FROM publications WHERE outbox_id=?',(item['outbox_id'],)).fetchone()
        self.assertEqual(ack[0],oid)
        self.assertEqual(len(r.history._git('log','--format=%H','--',item['path']).stdout.splitlines()),1)
        self.assertEqual(r.verify()['status'],'HEALTHY')

    def test_publication_failure_keeps_authoritative_state(self):
        self.task();r=self.registry;before=r.publication_status()
        with patch('tools.agent_control.publication.GitHistory.publish',side_effect=RegistryBlocked('Synthetic failure')):
            with self.assertRaises(RegistryBlocked):r.reconcile(operation_id=op())
        self.assertEqual(r.publication_status(),before);self.assertEqual(len(r.list_tasks()),1)
        r.reconcile(operation_id=op());self.assertEqual(r.verify()['status'],'HEALTHY')

    def test_event_chain_update_and_delete_are_blocked_or_detected(self):
        r=self.registry;self.task()
        with self.assertRaises(sqlite3.IntegrityError):r.db.execute('DELETE FROM audit_events WHERE sequence=1')
        r.db.execute('DROP TRIGGER immutable_audit_events_update')
        r.db.execute("UPDATE audit_events SET event_digest=? WHERE sequence=1",('e'*64,))
        self.assertEqual(r.verify()['status'],'BLOCKED')
        with self.assertRaises(RegistryBlocked):self.task()

    def test_missing_event_detected(self):
        self.task();r=self.registry;r.db.execute('DROP TRIGGER immutable_audit_events_delete')
        r.db.execute('DELETE FROM audit_events WHERE sequence=1')
        self.assertEqual(r.verify()['status'],'BLOCKED')

    def test_acknowledgement_corruption_detected(self):
        r=self.registry;r.reconcile(operation_id=op())
        r.db.execute('DROP TRIGGER immutable_publications_update')
        r.db.execute("UPDATE publications SET git_commit=?",('f'*40,))
        self.assertEqual(r.verify()['status'],'BLOCKED')
        with self.assertRaises(RegistryBlocked):r.reconcile(operation_id=op())

    def test_history_identity_and_payload_mismatch_block(self):
        r=self.registry;r.reconcile(operation_id=op())
        original=r.meta('registry_id');r.db.execute("UPDATE metadata SET value=? WHERE key='registry_id'",(op(),))
        self.assertEqual(r.verify()['status'],'BLOCKED')
        r.db.execute("UPDATE metadata SET value=? WHERE key='registry_id'",(original,))
        item=dict(r.db.execute('SELECT * FROM outbox LIMIT 1').fetchone());item['payload']=canonical_json({'changed':True});item['payload_digest']=digest({'changed':True})
        with self.assertRaises(RegistryBlocked):r.history.publish(item)

    def test_backup_independently_opens_and_is_private(self):
        self.task();dest=self.root/'backup.sqlite3';key=op()
        self.registry.backup(dest,operation_id=key)
        self.assertEqual(dest.stat().st_mode&0o777,0o600)
        with Registry(dest) as backup:
            self.assertEqual(len(backup.list_tasks()),1)
            self.assertNotEqual(backup.verify()['status'],'BLOCKED')
        self.task()
        with Registry(dest) as backup:self.assertEqual(len(backup.list_tasks()),1)
        self.registry.backup(dest,operation_id=key)
        with self.assertRaises(ValidationError):self.registry.backup(self.root/'other.sqlite3',operation_id=key)

    def test_cli_registry_tasks_and_publication(self):
        def cli(*args,stdin=None):
            out=io.StringIO();err=io.StringIO()
            with redirect_stdout(out),redirect_stderr(err),patch('sys.stdin',io.StringIO(stdin or '')):
                result=main(['--state',str(self.path),*args])
            self.assertEqual(result,0,err.getvalue());return json.loads(out.getvalue())
        self.assertEqual(cli('registry','status')['status'],'DEGRADED')
        t=cli('task','create','--operation-id',op(),stdin=json.dumps(proposal()))
        self.assertEqual(cli('task','show',t['task_id'])['task_id'],t['task_id'])
        self.assertEqual(len(cli('task','list')),1)
        self.assertGreater(cli('publication','status')['pending'],0)
        cli('publication','reconcile','--operation-id',op())
        self.assertEqual(cli('history','verify')['status'],'HEALTHY')
        self.assertEqual(cli('finding','list'),[])


class MetadataTests(RegistryTests):
    # Separate scenarios use the same temporary fixture; inherited tests also
    # exercise this fixture but are excluded below via unittest discovery loader.
    def prepared(self):
        from fixtures import approval_data,candidate
        r=self.registry
        p=proposal();p.update(allowed_write_paths=[{'kind':'FILE','path':'frontend/example.ts'}],
            required_tests=[{'test_id':'unit','command_id':'unit','definition_digest':'f'*64,'required':True,'baseline_evidence':None}])
        t=r.create_task(p,operation_id=op(),context=ARCH);tid=t['task_id']
        r.assign_metadata(tid,[{'owner_agent':'FE-01','workstream':'frontend',
            'allowed_write_paths':[{'kind':'FILE','path':'frontend/example.ts'}],
            'branch':'agent/ATS-0001/frontend','worktree':'/synthetic/work'}],operation_id=op(),context=ARCH)
        r.transition(tid,'INSPECTING',operation_id=op(),context=ARCH)
        t=r.freeze_spec(tid,operation_id=op(),context=ARCH)
        ad=approval_data(t);ad['approval_id']=op();key=op()
        a=r.put_metadata('Approval',ad,operation_id=key,context=FOUNDER)
        self.assertEqual(r.put_metadata('Approval',ad,operation_id=key,context=FOUNDER).to_dict(),a.to_dict())
        r.transition(tid,'FOUNDER_APPROVED',operation_id=op(),context=FOUNDER,approval_id=a['approval_id'])
        r.transition(tid,'ASSIGNED',operation_id=op(),context=ARCH,approval_id=a['approval_id'])
        r.transition(tid,'IN_PROGRESS',operation_id=op(),context=FE)
        t=r.submit_commit_metadata(tid,'d'*40,operation_id=op(),context=FE)
        c=r.put_metadata('IntegrationCandidate',candidate(t).to_dict(),operation_id=op(),context=ARCH)
        return r.get_task(tid),c,a

    def test_candidate_immutable_evidence_and_full_qa_path(self):
        from fixtures import evidence_data,event_data,approval_data
        from tools.agent_control.records import IntegrationCandidate
        r=self.registry;t,c,a=self.prepared();tid=t['task_id']
        self.assertEqual(r.load('IntegrationCandidate',c['candidate_id']).to_dict(),c.to_dict())
        body=c.to_dict();del body['manifest_digest'];body['prepared_tree']='e'*40
        with self.assertRaises(ValidationError):
            r.put_metadata('IntegrationCandidate',IntegrationCandidate.finalize(body).to_dict(),operation_id=op(),context=ARCH)
        grant=blank('ExecutionGrant');grant.update(execution_id=op(),agent_id='QA-01',role='INTEGRATION_QA',
            task_id=tid,spec_version=t['spec_version'],spec_digest=t['spec_digest'])
        r.put_metadata('ExecutionGrant',grant,operation_id=op(),context=ARCH)
        ed=evidence_data(c);ed.update(evidence_id=op(),execution_id=grant['execution_id'])
        with self.assertRaises(ValidationError):
            r.put_metadata('TestEvidence',dict(ed,tested_commit='e'*40),operation_id=op(),context=QA)
        e=r.put_metadata('TestEvidence',ed,operation_id=op(),context=QA)
        qd=event_data(c);qd.update(event_id=op(),evidence=[e['evidence_id']])
        q=r.put_metadata('CandidateEvent',qd,operation_id=op(),context=QA)
        r.transition(tid,'READY_FOR_QA',operation_id=op(),context=FE)
        r.transition(tid,'QA_REVIEW',operation_id=op(),context=QA,candidate_id=c['candidate_id'])
        t=r.transition(tid,'QA_PASSED',operation_id=op(),context=QA,candidate_id=c['candidate_id'],qa_event_id=q['event_id'],evidence_ids=[e['evidence_id']])
        integration=approval_data(t,'APPROVE_INTEGRATION',c);integration['approval_id']=op()
        a=r.put_metadata('Approval',integration,operation_id=op(),context=FOUNDER)
        r.transition(tid,'FOUNDER_APPROVED_FOR_INTEGRATION',operation_id=op(),context=FOUNDER,
            candidate_id=c['candidate_id'],approval_id=a['approval_id'],qa_event_id=q['event_id'],evidence_ids=[e['evidence_id']])
        r.reconcile(operation_id=op())
        self.assertEqual(r.verify()['status'],'HEALTHY')
        self.assertTrue(all(x['status']=='DISABLED' for x in r.list_agents()))
        with self.assertRaises(ValidationError):r.transition(tid,'INTEGRATED',operation_id=op(),context=FOUNDER)

    def test_revoked_approval_and_old_candidate_rejected(self):
        from fixtures import approval_data
        r=self.registry;t,c,a=self.prepared();tid=t['task_id']
        revoke=approval_data(t);revoke.update(action='REVOKE',approval_id=op(),supersedes=a['approval_id'],reason='Synthetic revocation')
        r.put_metadata('Approval',revoke,operation_id=op(),context=FOUNDER)
        with self.assertRaises(ValidationError):r._active_approval(a)
        r.transition(tid,'CONTRACT_CONFLICT',operation_id=op(),context=FE,reason='Synthetic scope conflict')
        r.revise_task(tid,{'objective':'Revised synthetic scope'},operation_id=op(),context=ARCH)
        with self.assertRaises(ValidationError):r._active_candidate(c,r.get_task(tid))
        self.assertNotEqual(r.verify(check_history=False)['status'],'BLOCKED')

    def test_evidence_publication_excludes_argv(self):
        from tools.agent_control.registry import public_payload
        source={'argv':['synthetic-command','synthetic-private-argument'],'session_id':'synthetic-session',
                'tested_commit':'b'*40,'counts':{'passed':None}}
        published=public_payload('TestEvidence',source)
        self.assertNotIn('argv',published['record']);self.assertNotIn('session_id',published['record'])
        self.assertEqual(published['record']['counts']['passed'],None)

    def test_operation_ids_cannot_cross_domain_and_maintenance(self):
        key=op();self.registry.create_task(proposal(),operation_id=key)
        with self.assertRaises(ValidationError):self.registry.reconcile(operation_id=key)
        key=op();self.registry.reconcile(operation_id=key)
        with self.assertRaises(ValidationError):self.registry.create_task(proposal(),operation_id=key)

    def test_supersession_requires_explicit_replacement(self):
        r=self.registry;tid=self.task()['task_id'];d=record_data(ARCH,'FINDING',False);d.pop('record_id');d['task_id']=tid
        old=r.create_record(d,operation_id=op(),context=ARCH)
        with self.assertRaises(ValidationError):r.resolve_record(old['record_id'],'Replaced',operation_id=op(),context=ARCH,status='SUPERSEDED')
        d['supersedes']=[old['record_id']];new=r.create_record(d,operation_id=op(),context=ARCH)
        r.resolve_record(old['record_id'],'Replaced',operation_id=op(),context=ARCH,status='SUPERSEDED',superseded_by=new['record_id'])
        self.assertEqual(len(r.list_records(tid,True)),1)

    def test_publication_history_modification_is_blocked(self):
        r=self.registry;r.reconcile(operation_id=op());h=r.history
        leaves={}
        for entry in h._git('ls-tree','-rz',h.head()).stdout.split(b'\0'):
            if entry:
                meta,path=entry.split(b'\t',1);leaves[path.decode()]=tuple(meta.decode().split())
        item=dict(r.db.execute('SELECT * FROM outbox ORDER BY outbox_id LIMIT 1').fetchone())
        original=leaves[item['path']]
        # Append conflicting history in the synthetic repository, then restore
        # original bytes by appending another commit. Neither operation rewrites history.
        blob=h._git('hash-object','-w','--stdin',data=b'{"synthetic_conflict":true}\n').stdout.decode().strip()
        for value in [('100644','blob',blob),original]:
            parent=h.head();leaves[item['path']]=value
            oid=h._git('commit-tree',h._tree(leaves),'-p',parent,data=b'Synthetic corruption fixture\n').stdout.decode().strip()
            h._git('update-ref','refs/heads/control-history',oid,parent)
        self.assertEqual(r.verify()['status'],'BLOCKED')
        with self.assertRaises(RegistryBlocked):r.reconcile(operation_id=op())

    def test_outbox_source_corruption_blocks_reconciliation(self):
        r=self.registry;r.db.execute('DROP TRIGGER immutable_outbox_update')
        r.db.execute("UPDATE outbox SET payload='{}',payload_digest=? WHERE outbox_id=1",(digest({}),))
        self.assertEqual(r.verify()['status'],'BLOCKED')
        with self.assertRaises(RegistryBlocked):r.reconcile(operation_id=op())

    def test_record_idempotent_retry_races(self):
        tid=self.task()['task_id'];key=op();ctx=multiprocessing.get_context('spawn')
        with ProcessPoolExecutor(max_workers=4,mp_context=ctx) as pool:
            ids=list(pool.map(worker_record,[(str(self.path),key,'FINDING',tid)]*4))
        self.assertEqual(len(set(ids)),1);self.assertEqual(len(self.registry.list_records(tid)),1)

    def test_cli_explicit_init_and_repository_path_guard(self):
        from tools.agent_control.storage import external_path
        with self.assertRaises(RegistryBlocked):external_path(Path(__file__).resolve().parents[2]/'forbidden.sqlite3')
        with self.assertRaises(RegistryBlocked):
            external_path(Path(__file__).resolve().parents[2]/'missing-parent'/'..'/'forbidden.sqlite3')
        out=io.StringIO()
        with redirect_stdout(out):
            result=main(['--state',str(self.root/'cli.sqlite3'),'--history',str(self.root/'cli.git'),
                         'registry','init','--operation-id',op()])
        self.assertEqual(result,0);self.assertEqual(json.loads(out.getvalue())['status'],'DEGRADED')


def load_tests(loader, tests, pattern):
    suite=unittest.TestSuite(loader.loadTestsFromTestCase(RegistryTests))
    for name in MetadataTests.__dict__:
        if name.startswith('test_'):suite.addTest(MetadataTests(name))
    return suite


if __name__=='__main__':unittest.main()
