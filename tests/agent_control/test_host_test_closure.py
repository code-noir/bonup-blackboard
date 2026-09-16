"""Deterministic closure of both components; no host process is launched."""
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import unittest

from tools.agent_control.authority_installation import InstallationBinding,InstalledReceipt
from tools.agent_control.composition import ApprovedPlan,SupervisorEndpoint,OfflineTransport,RemoteProcessBackend,payload_digest,message
from tools.agent_control.confinement import ConfinementProfile
from tools.agent_control.execution import LaunchRecord
from tools.agent_control.host_test_catalog import CATALOG,CATALOG_DIGEST,VERSION
from tools.agent_control.host_test_runtime import HostTests
from tools.agent_control.identity import ProcessIdentity,WorkerIdentity
from tools.agent_control.operational_enrollment import Admission,AdmissionState
from tools.agent_control.protocol import Operation
from tools.agent_control.serialization import digest
from tools.agent_control.types import AuthorityError,Role,ValidationError


def admission():
    result=Admission();result.starting();result.enrolled('a'*64,lambda:None);result.reconciled()
    return result


class ClosureTests(unittest.TestCase):
    def setUp(self):
        self.boot=str(uuid4());self.generation=str(uuid4());self.eid=str(uuid4())
        self.binding=InstallationBinding('a'*40,'b'*64,'c'*64,'d'*64,'e'*64,2)
        profile=ConfinementProfile();worker=WorkerIdentity('FE-01',Role.FRONTEND_ENGINEERING,'bonup-fe01',3002,3002)
        process=ProcessIdentity(self.boot,123,42)
        self.record=LaunchRecord(Operation.RUN_TEST,('/usr/bin/true',),'/work',profile.environment(),30,65536,
            profile.profile_digest,worker,'{}','b'*64,'2026-09-15T00:00:30Z')
        self.plan=ApprovedPlan(str(uuid4()),self.eid,self.record,(1,2,3002,3002),'f'*64,process)
        self.backend=Mock();self.backend.prepare.return_value=process
        self.backend.empty.return_value=True;self.backend.finish.return_value=0
        self.endpoint=SupervisorEndpoint((self.plan,),self.backend,generation=self.generation,boot_id=self.boot,
            now=lambda:datetime(2026,9,15,tzinfo=timezone.utc),elapsed=lambda:0,admission=admission(),
            host_only=True,ordinary_admission=False,host_installation_digest=digest(self.binding.data()))
        self.endpoint.ready=True
        self.transport=OfflineTransport(self.endpoint)
        self.remote=RemoteProcessBackend(self.transport,{},generation=self.generation,boot_id=self.boot)
        self.controller=Mock();self.controller.admission=admission();self.controller.remote=self.remote
        self.controller.runtime.db.execute.return_value.fetchone.return_value=None
        self.controller.runtime.db.execute.return_value.fetchall.return_value=[]
        self.context=dict(boot_id=self.boot,controller_generation=str(uuid4()),supervisor_generation=self.generation)
        self.founder=Mock();self.founder.delegate.return_value=({'process':{'boot_id':self.boot}},'proof',lambda:None)
        self.runner=Mock();self.runner.execution_ids.return_value=(self.eid,)
        self.journal=Mock();self.saved={}
        self.journal.record.side_effect=lambda event,key,evidence:self.saved.update({event:evidence})
        self.host=HostTests(self.founder,InstalledReceipt(self.binding,'f'*64,str(uuid4())),self.controller,
                            self.runner,self.journal,lambda:dict(self.context))
        self.host.begin('1'*64)

    def evidence(self):
        self.host.results={name:dict(receipt='f'*64,binding=self.binding.data(),catalog_version=VERSION,
            catalog_digest=CATALOG_DIGEST,test_id=name,launch_id=str(uuid4()),worker=list(case.worker),
            **self.context,evidence_digest='a'*64,result='PASS',correlation={}) for name,case in CATALOG.items()}

    def prepare(self):
        launch=str(uuid4())
        data=dict(plan_id=self.plan.plan_id,execution_id=self.eid,authorization_digest='b'*64,
            workspace_digest=digest(list(self.plan.workspace_identity)),plan_digest=payload_digest(self.record),
            expires_at=self.record.expires_at,elapsed_deadline_ns=30_000_000_000)
        self.remote._call('PREPARE_LAUNCH',launch,data,'PREPARED_EVIDENCE')
        return launch

    def closed(self):
        self.assertEqual(self.controller.admission.state,AdmissionState.CLOSED)
        self.assertEqual(self.endpoint.admission.state,AdmissionState.CLOSED)
        self.assertIsNone(self.host.session);self.assertIsNone(self.host.verify)
        with self.assertRaises(AuthorityError):self.controller.admission.open('a'*64)
        with self.assertRaises(AuthorityError):self.prepare()
        with self.assertRaises(AuthorityError):
            self.remote._call('RELEASE_LAUNCH',str(uuid4()),dict(authorization_digest='b'*64,release_id=str(uuid4())),'RUNNING_EVIDENCE')
        self.backend.release.assert_not_called()

    def test_begin_opens_only_host_mode(self):
        for gate in (self.controller.admission,self.endpoint.admission):
            self.assertEqual(gate.state,AdmissionState.HOST_TEST_ONLY)
            with self.assertRaises(AuthorityError):gate.require_open()
        launch=self.prepare();self.assertEqual(self.endpoint.launches[launch]['state'],'PREPARED')

    def test_end_closes_both_and_denies_prepared_release(self):
        launch=self.prepare()
        self.assertEqual(self.host.end(),{'mode':'CLOSED','activation':False})
        self.closed()
        with self.assertRaises(AuthorityError):
            self.remote._call('RELEASE_LAUNCH',launch,dict(authorization_digest='b'*64,release_id=str(uuid4())),'RUNNING_EVIDENCE')
        self.assertEqual(self.endpoint.launches[launch]['state'],'TERMINAL')

    def test_completion_consumes_both_and_preserves_evidence(self):
        launch=self.prepare()
        self.evidence();expected=digest(self.host.results)
        result=self.host.complete();self.closed()
        with self.assertRaises(AuthorityError):
            self.remote._call('RELEASE_LAUNCH',launch,dict(authorization_digest='b'*64,release_id=str(uuid4())),'RUNNING_EVIDENCE')
        self.assertFalse(result['activation']);self.assertEqual(result['evidence_digest'],expected)
        self.assertEqual(self.saved['HOST_TEST_COMPLETION_ACCEPTED']['evidence_digest'],expected)
        self.assertEqual(self.saved['HOST_TEST_COMPLETION_ACCEPTED']['results'],self.host.results)
        self.founder.revoke_all.assert_called_once()
        events=list(self.saved)
        self.assertLess(events.index('HOST_TEST_SUPERVISOR_CLOSED'),events.index('HOST_TEST_COMPLETION_ACCEPTED'))
        self.assertLess(events.index('HOST_TEST_AUTHORITY_CONSUMED'),events.index('HOST_TEST_COMPLETION_ACCEPTED'))

    def test_consumed_delegation_denies_all_operations(self):
        self.evidence();self.host.complete()
        for name,args in (('complete',()),('end',()),('run',({'test_id':'uid_gid_drop'},)),
                ('enroll',({'test_id':'uid_gid_drop'},)),('collect',({'test_id':'uid_gid_drop'},))):
            with self.subTest(operation=name),self.assertRaises(AuthorityError):getattr(self.host,name)(*args)

    def test_new_request_id_cannot_reuse_completed_authority(self):
        from tools.agent_control.founder_intake import FounderIntake
        intake=object.__new__(FounderIntake)
        intake.tests=self.host;intake.seen=set();intake.journal=self.journal
        intake.policy=SimpleNamespace(receipt_digest='f'*64);intake._receipt=lambda:self.host.receipt
        self.evidence();self.host.complete()
        for action in ('COMPLETE_HOST_TESTS','END_HOST_TEST_SESSION','RUN_HOST_TEST_CASE','ENROLL_HOST_TEST_CASE','RECORD_HOST_TEST_EVIDENCE'):
            args={} if action in ('COMPLETE_HOST_TESTS','END_HOST_TEST_SESSION') else {'test_id':'uid_gid_drop'}
            with self.subTest(action=action),self.assertRaises(AuthorityError):
                intake.request(dict(version=1,request_id=str(uuid4()),action=action,arguments=args))

    def test_stale_host_session_cannot_reopen(self):
        binding=self.host._binding(self.host.session);self.host.end()
        for changed in (binding,dict(binding,host_session_digest='2'*64)):
            with self.assertRaises(AuthorityError):self.remote._call('OPEN_HOST_TEST_ADMISSION',str(uuid4()),changed,'HOST_TEST_ADMISSION_EVIDENCE',version=4)
        with self.assertRaises(AuthorityError):self.remote._call('OPEN_ADMISSION',str(uuid4()),{'session_digest':'a'*64},'ADMISSION_EVIDENCE')

    def test_closure_observation_is_idempotent_without_reopening(self):
        binding=self.host._binding(self.host.session);self.host.end()
        response=self.remote._call('CLOSE_HOST_TEST_ADMISSION',str(uuid4()),dict(binding,reason='END'),'HOST_TEST_ADMISSION_EVIDENCE',version=4)
        self.assertTrue(response['closed']);self.assertTrue(response['cleanup_confirmed']);self.closed()

    def test_wrong_closure_binding_denied(self):
        binding=self.host._binding(self.host.session)
        for field in binding:
            with self.subTest(field=field),self.assertRaises(AuthorityError):
                self.remote._call('CLOSE_HOST_TEST_ADMISSION',str(uuid4()),dict(binding,**{field:'9'*64},reason='END'),'HOST_TEST_ADMISSION_EVIDENCE',version=4)

    def test_missing_failed_evidence_never_completes(self):
        self.evidence();self.host.results['capability_bounds']['result']='FAIL'
        with self.assertRaises(AuthorityError):self.host.complete()
        self.assertNotIn('HOST_TEST_COMPLETION_ACCEPTED',self.saved)

    def test_local_authority_consumed_before_rpc(self):
        exchange=self.transport.exchange
        def observe(request):
            if request['action']=='CLOSE_HOST_TEST_ADMISSION':
                self.assertIsNone(self.host.session)
                self.assertEqual(self.controller.admission.state,AdmissionState.CLOSED)
                with self.assertRaises(AuthorityError):self.host.run({'test_id':'uid_gid_drop'})
            return exchange(request)
        self.transport.exchange=observe;self.host.end();self.closed()

    def test_uncertain_ack_invalidates_channel(self):
        self.evidence();exchange=self.transport.exchange
        def lost(request):
            exchange(request)
            raise AuthorityError('acknowledgement lost')
        self.transport.exchange=lost
        with self.assertRaises(AuthorityError):self.host.complete()
        self.assertFalse(self.transport.connected)
        self.assertIsNone(self.host.session)
        self.assertEqual(self.controller.admission.state,AdmissionState.CLOSED)
        self.assertNotEqual(self.endpoint.admission.state,AdmissionState.HOST_TEST_ONLY)
        self.assertNotIn('HOST_TEST_COMPLETION_ACCEPTED',self.saved)

    def test_unavailable_supervisor_fails_closed(self):
        self.transport.connected=False
        with self.assertRaises(AuthorityError):self.host.end()
        self.assertIsNone(self.host.session)
        self.assertEqual(self.controller.admission.state,AdmissionState.CLOSED)
        self.assertIn('HOST_TEST_CLOSURE_UNCERTAIN',self.saved)

    def test_wrong_generation_response_fails_closed(self):
        exchange=self.transport.exchange
        def wrong(request):
            response=exchange(request);response['generation']=str(uuid4());return response
        self.transport.exchange=wrong
        with self.assertRaises(AuthorityError):self.host.end()
        self.assertFalse(self.transport.connected);self.assertIsNone(self.host.session)

    def test_malformed_closure_response_fails_closed(self):
        exchange=self.transport.exchange
        def wrong(request):
            response=exchange(request);response['data']['extra']=True;return response
        self.transport.exchange=wrong
        with self.assertRaises(ValidationError):self.host.end()
        self.assertFalse(self.transport.connected);self.assertIsNone(self.host.session)

    def test_cleanup_uncertainty_blocks_completion(self):
        self.prepare();self.backend.empty.return_value=False;self.evidence()
        with self.assertRaises(AuthorityError):self.host.complete()
        self.assertNotIn('HOST_TEST_COMPLETION_ACCEPTED',self.saved)
        self.assertIsNone(self.host.session)

    def test_expiry_closes_both(self):
        self.host.verify=Mock(side_effect=AuthorityError('expired'))
        with self.assertRaises(AuthorityError):self.host.enroll({'test_id':'uid_gid_drop'})
        self.closed()

    def test_revocation_closes_both(self):
        self.host.abort('REVOKE');self.closed()

    def test_runtime_generation_change_closes_both(self):
        self.context['supervisor_generation']=str(uuid4())
        with self.assertRaises(AuthorityError):self.host.enroll({'test_id':'uid_gid_drop'})
        self.closed()

    def test_receipt_failure_closes_both(self):
        from tools.agent_control.founder_intake import FounderIntake
        intake=object.__new__(FounderIntake);intake.tests=self.host
        intake._receipt=Mock(side_effect=AuthorityError('receipt replaced'));intake.founder=self.founder
        with self.assertRaises(AuthorityError):intake.tick()
        self.closed()

    def test_audit_failure_cannot_retain_authority(self):
        self.journal.record.side_effect=OSError('audit unavailable')
        with self.assertRaises(OSError):self.host.end()
        self.assertIsNone(self.host.session);self.assertFalse(self.transport.connected)
        self.assertNotEqual(self.endpoint.admission.state,AdmissionState.HOST_TEST_ONLY)

    def test_supervisor_crash_during_closure_fails_closed(self):
        def crash(request):
            self.endpoint.disconnect();raise AuthorityError('supervisor crash')
        self.transport.exchange=crash
        with self.assertRaises(AuthorityError):self.host.end()
        self.assertFalse(self.transport.connected);self.assertIsNone(self.host.session)

    def test_controller_crash_during_closure_fails_closed(self):
        self.transport.exchange=Mock(side_effect=SystemExit('controller crash'))
        with self.assertRaises(SystemExit):self.host.end()
        self.assertFalse(self.transport.connected);self.assertIsNone(self.host.session)

    def test_fatal_request_failure_closes_both(self):
        from tools.agent_control.founder_intake import FounderIntake
        intake=object.__new__(FounderIntake);intake.tests=self.host;intake.seen=set();intake.journal=self.journal
        intake.policy=SimpleNamespace(receipt_digest='f'*64);intake._receipt=lambda:self.host.receipt
        self.host.enrolled['uid_gid_drop']=object()
        self.runner.run.side_effect=AuthorityError('setup failed')
        with self.assertRaises(AuthorityError):
            intake.request(dict(version=1,request_id=str(uuid4()),action='RUN_HOST_TEST_CASE',arguments={'test_id':'uid_gid_drop'}))
        self.closed()

    def test_completion_is_durable_after_authority_consumed(self):
        import tempfile
        from pathlib import Path
        from tools.agent_control.registry import Registry
        from tools.agent_control.authority_journal import AuthorityJournal
        with tempfile.TemporaryDirectory() as directory:
            registry=Registry.initialize(Path(directory)/'control.sqlite3',Path(directory)/'history.git',operation_id=str(uuid4()))
            try:
                journal=AuthorityJournal(registry);self.host.journal=journal
                self.evidence();self.host.complete()
                row=journal.load('1'*64)
                self.assertEqual(row['event'],'HOST_TEST_COMPLETION_ACCEPTED')
                self.assertEqual(row['evidence']['results'],self.host.results)
                self.assertIsNone(self.host.session)
                with self.assertRaises(AuthorityError):self.host.complete()
            finally:registry.close()

    def test_revocation_audit_failure_invalidates_retained_delegation(self):
        from tools.agent_control.founder_session import FounderSessions
        from tools.agent_control.identity import PeerIdentity
        from test_founder_root import ROOT
        sessions=FounderSessions(ROOT,observe=lambda:(PeerIdentity(1000,1000,123),ProcessIdentity(self.boot,123,42)),
            audit=Mock(),clock=lambda:datetime(2026,9,15,tzinfo=timezone.utc),boottime=lambda:0)
        challenge=sessions.issue_binding('FOUNDER_HOST_TEST_AUTHORIZATION',self.binding.data(),installation_receipt_digest='f'*64)
        # Synthetic already-verified session; this test isolates revocation.
        key=digest(challenge);sessions.sessions[key]=(challenge,60,'verified-test-decision')
        _,_,verify=sessions.delegate(key,'FOUNDER_HOST_TEST_AUTHORIZATION',self.binding.data(),installation_receipt_digest='f'*64)
        sessions.sessions['another']=(challenge,60,'verified-test-decision')
        sessions.audit=Mock(side_effect=OSError('audit failed'))
        with self.assertRaises(OSError):sessions.revoke_all()
        with self.assertRaises(AuthorityError):verify()
        self.assertFalse(sessions.sessions)

    def test_direct_founder_model_closure_operation_unsupported(self):
        from tools.agent_control.founder_intake import FounderIntake
        intake=object.__new__(FounderIntake);intake.tests=None
        with self.assertRaises(AuthorityError):intake._request('CLOSE_HOST_TEST_ADMISSION',{})
        binding=self.host._binding(self.host.session)
        with self.assertRaises(ValidationError):
            message('CLOSE_HOST_TEST_ADMISSION',str(uuid4()),self.generation,self.boot,dict(binding,reason='END',uid=0),version=4)

    def test_controller_shutdown_invalidates_channel_even_if_founder_close_fails(self):
        from tools.agent_control.installed_runtime import InstalledControllerDriver
        driver=object.__new__(InstalledControllerDriver)
        driver.controller=Mock();driver.listeners={};driver.client=Mock()
        driver.client.close.side_effect=self.transport.disconnect
        driver.founder_transport=Mock();driver.founder_transport.close.side_effect=AuthorityError('lost closure acknowledgement')
        with self.assertRaises(AuthorityError):driver.disconnect()
        self.assertFalse(self.transport.connected)
        self.assertNotEqual(self.endpoint.admission.state,AdmissionState.HOST_TEST_ONLY)

    def test_armed_interruption_closes_admission_without_prestopping_canary(self):
        from dataclasses import replace
        launch=self.prepare();entry=self.endpoint.launches[launch]
        entry.update(state='RUNNING',exec_confirmed=True)
        entry['record']=replace(entry['record'],argv=('/usr/bin/python3','controller_crash'))
        self.host.launches['controller_crash']=launch
        self.runner.arm_interruption.return_value={'phase':'INTERRUPTION_ARMED'}
        result=self.host.prepare_interruption({'test_id':'controller_crash'})
        self.assertTrue(result['pending']);self.assertIsNone(self.host.session)
        self.assertEqual(entry['state'],'RUNNING');self.backend.kill.assert_not_called()
        for gate in (self.controller.admission,self.endpoint.admission):self.assertEqual(gate.state,AdmissionState.CLOSED)
        with self.assertRaises(AuthorityError):self.prepare()

    def test_interruption_exception_cannot_preserve_ordinary_launch(self):
        launch=self.prepare();self.endpoint.launches[launch].update(state='RUNNING',exec_confirmed=True)
        with self.assertRaises(AuthorityError):self.host._close('INTERRUPTION')
        self.assertFalse(self.transport.connected);self.assertIsNone(self.host.session)


if __name__=='__main__':unittest.main()
