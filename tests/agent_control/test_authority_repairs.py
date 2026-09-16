"""Synthetic regression for successor policy, canaries and interruption evidence."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import io
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from test_founder_root import ROOT
from tools.agent_control import successor_config as sc
from tools.agent_control.authority_installation import InstallationBinding
from tools.agent_control.host_test_canary import main
from tools.agent_control.host_test_catalog import CATALOG, CATALOG_DIGEST, VERSION
from tools.agent_control.installation_bundle import identities
from tools.agent_control.integration_policy import IntegrationPolicy
from tools.agent_control.operational_enrollment import installation_spec, InstallationIdentity
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import AuthorityError, ValidationError


def successor_fixture():
    policy=dict(version=1,installation_generation=2,founder_enabled=True,root_id=ROOT.key_id,
        root_digest=ROOT.identity,root_generation=ROOT.generation,algorithm='Ed25519',
        purposes=list(sc.PURPOSES),openssl=deepcopy(sc.OPENSSL),host_tests_enabled=True,
        catalog_version=VERSION,catalog_digest=CATALOG_DIGEST,audit='CONTROLLER_DURABLE_OUTBOX_REQUIRED',
        receipt='EXACT_VERIFIED_INSTALLATION_REQUIRED',activation=False,interruption=deepcopy(sc.INTERRUPTION))
    configs={name:dict(version=3,service=installation_spec(name,generation=2),authority=deepcopy(policy),
        **(dict(founder_uid=1000,founder=None,proposal=None,executions=[]) if name=='controller' else dict(roots=[],plans=[])))
        for name in ('controller','supervisor')}
    ids=identities();ids['provisioning_generation']=2
    for row in ids['accounts']:row['provisioning_generation']=2
    candidate=dict(version=5,source_commit='a'*40,provisioning_generation=2,approved=False,activation=False,
        integration_services_approved=False,files={name:'a'*64 for name in sc.files()},
        configuration_digests={name:digest(data) for name,data in configs.items()},
        identity_map_digest=digest(ids),resource_digest=IntegrationPolicy().policy_digest,authority_digest=digest(policy))
    candidate['bundle_digest']=digest(candidate)
    approved=dict(candidate,approved=True)
    approved['bundle_digest']=digest({k:v for k,v in approved.items() if k!='bundle_digest'})
    sha=lambda v:hashlib.sha256(canonical_json(v).encode()).hexdigest()
    binding=InstallationBinding('a'*40,sha(candidate),candidate['bundle_digest'],sha(approved),'e'*64,2)
    receipt=dict(version=1,binding=binding.data(),installation_id=str(uuid4()),activation=False,
        verified_artifacts_digest=binding.approved_inventory_digest)
    attest=dict(version=1,provisioning_generation=2,binding=binding.data(),receipt_digest=digest(receipt),
        files=candidate['files'],configuration_digests=candidate['configuration_digests'],
        identity_map_digest=digest(ids),resource_digest=candidate['resource_digest'],approved=True,
        activation=False,integration_services_approved=True,authority_digest=digest(policy),filesystem_digest=digest([]))
    attest['bundle_digest']=digest(attest)
    return configs,attest,ids,receipt,candidate,approved


class SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.configs,self.attest,self.ids,self.receipt,self.candidate,self.approved=successor_fixture()

    def validate(self):
        return sc.validate(self.configs['controller'],self.attest,self.ids,self.receipt,ROOT,component='controller')

    def test_explicit_successor_accepted(self):
        self.assertEqual(self.validate().binding.provisioning_generation,2)

    def test_unknown_fields(self):
        self.configs['controller']['provider']='anything'
        with self.assertRaises(ValidationError):self.validate()

    def test_policy_mutations_rejected(self):
        for key,value in dict(installation_generation=1,algorithm='RSA',root_id='caller',root_digest='f'*64,
                purposes=['FOUNDER_ACTIVATION_APPROVAL'],catalog_digest='f'*64,catalog_version=2,
                audit=False,receipt=False,activation=True,openssl={'path':'/tmp/openssl'}).items():
            with self.subTest(field=key):
                old=self.configs['controller']['authority'][key]
                self.configs['controller']['authority'][key]=value
                with self.assertRaises((AuthorityError,ValidationError)):self.validate()
                self.configs['controller']['authority'][key]=old

    def test_missing_root_configuration(self):
        del self.configs['controller']['authority']['root_id']
        with self.assertRaises(ValidationError):self.validate()

    def test_no_implicit_enable(self):
        self.configs['controller']['authority']['founder_enabled']=False
        with self.assertRaises(AuthorityError):self.validate()

    def test_receipt_mismatch(self):
        self.receipt['binding']['provisioning_generation']=1
        with self.assertRaises(AuthorityError):self.validate()

    def test_missing_dependency(self):
        self.attest['files'].pop(next(iter(self.attest['files'])))
        self.attest['bundle_digest']=digest({k:v for k,v in self.attest.items() if k!='bundle_digest'})
        with self.assertRaises(AuthorityError):self.validate()

    def test_generation_one_cannot_parse_successor_identity(self):
        value=dict(installation_spec('controller',generation=2),bundle_digest='a'*64,configuration_digest='b'*64)
        with self.assertRaises(AuthorityError):InstallationIdentity.parse(value)
        self.assertEqual(InstallationIdentity.parse(value,generation=2).provisioning_generation,2)

    def test_historical_validator_rejects_extensions(self):
        from pathlib import Path
        from tools.agent_control.serialization import parse_json
        from tools.agent_control.installed_config import validate_activation
        from tools.agent_control.installation_bundle import configurations
        root=Path(__file__).resolve().parents[2]/'docs/agent-control/review/m3-generation-1/payload/etc/bonup-agent-control'
        manifest=parse_json((root/'approved-installation.json').read_text())
        config=configurations()['controller'];config['authority']=self.configs['controller']['authority']
        with self.assertRaises((AuthorityError,ValidationError)):
            validate_activation(manifest,identities(),config,component='controller')


class CapabilityTests(unittest.TestCase):
    def run_status(self, changed=None, missing=None):
        values={key:'0' for key in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')}
        values['NoNewPrivs']='1'
        values.update(changed or {})
        if missing:del values[missing]
        with patch('builtins.open',return_value=io.StringIO('\n'.join(k+':\t'+v for k,v in values.items()))):
            main(['capability_bounds'])

    def test_all_zero(self):self.run_status()
    def test_each_nonzero(self):
        for key in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'):
            with self.subTest(key=key),self.assertRaises(AssertionError):self.run_status({key:'1'})
    def test_malformed(self):
        for value in ('not-hex','+0','-0',''):
            with self.subTest(value=value),self.assertRaises(AssertionError):self.run_status({'CapBnd':value})
    def test_duplicate_status_field(self):
        with patch('builtins.open',return_value=io.StringIO('CapBnd:\t1\nCapBnd:\t0\n')),self.assertRaises(AssertionError):
            main(['capability_bounds'])
    def test_missing(self):
        with self.assertRaises(KeyError):self.run_status(missing='CapBnd')
    def test_supervisor_not_worker(self):
        with self.assertRaises(AssertionError):self.run_status({'CapBnd':'e4','CapEff':'e4','CapPrm':'e4'})


class InterruptionTests(unittest.TestCase):
    def setUp(self):
        from tools.agent_control.host_test_runtime import HostTests
        from tools.agent_control.authority_installation import InstalledReceipt
        from tools.agent_control.operational_enrollment import Admission,AdmissionState
        self.context=dict(boot_id=str(uuid4()),controller_generation=str(uuid4()),supervisor_generation=str(uuid4()))
        self.binding=InstallationBinding('a'*40,'b'*64,'c'*64,'d'*64,'e'*64,2)
        self.controller=Mock();self.controller.admission=Admission()
        self.controller.admission.state=AdmissionState.HOST_TEST_ONLY
        self.controller.admission.session='a'*64
        self.controller.remote._call.side_effect=lambda action,launch,data,response,**kw: dict(
            {k:v for k,v in data.items() if k!='reason'},closed=True,cleanup_confirmed=False)
        self.controller.runtime.db.execute.return_value.fetchone.return_value=None
        self.runner=Mock();self.founder=Mock();self.journal=Mock()
        self.host=HostTests(self.founder,InstalledReceipt(self.binding,'f'*64,str(uuid4())),
            self.controller,self.runner,self.journal,lambda:dict(self.context))
        self.host.session='1'*64;self.host.verify=lambda:None
        self.host.initial_context=dict(self.context);self.host.accepted_contexts=[dict(self.context)]
        self.launch=str(uuid4());self.host.launches['reboot_reconciliation']=self.launch
        self.armed=dict(launch_id=self.launch,process=dict(boot_id=self.context['boot_id'],pid=123,start_ticks=9),
            target=dict(boot_id=self.context['boot_id'],pid=124,start_ticks=10),cgroup_name='launch-'+self.launch,
            cgroup_identity=[1,2],phase='INTERRUPTION_ARMED',armed_boottime_ns=1,prior_service_events=[])
        self.runner.arm_interruption.return_value=self.armed

    def prepare(self):
        self.host.prepare_reboot()
        self.pending=next(call.args[2] for call in self.journal.record.call_args_list if call.args[0]=='HOST_TEST_REBOOT_PENDING')
        self.journal.load.return_value=dict(event='HOST_TEST_REBOOT_PENDING',evidence=self.pending)
        self.controller.runtime.launch.return_value=dict(state='TERMINAL',cleanup_confirmed=True,
            cgroup_name=self.armed['cgroup_name'],process_identity=canonical_json(self.armed['process']))
        self.witness={k:v for k,v in self.armed.items() if k not in ('armed_boottime_ns','prior_service_events','phase')}
        self.witness.update(phase='TARGET_INTERRUPTED',worker_alive=True,observed_boottime_ns=2)
        self.runner.interruption_evidence.return_value=self.witness

    def fresh(self):
        self.context.update(boot_id=str(uuid4()),controller_generation=str(uuid4()),supervisor_generation=str(uuid4()))
        self.host.session='2'*64;self.host.verify=lambda:None
        self.host.initial_context=dict(self.context);self.host.accepted_contexts=[dict(self.context)]

    def test_arm_does_not_stop_canary(self):
        self.prepare();self.controller.stop.assert_not_called()
        self.assertIsNone(self.host.session)
        self.founder.revoke_all.assert_called_once()

    def test_valid_boundary_and_cleanup(self):
        self.prepare();self.fresh()
        self.assertEqual(self.host.reconcile_reboot()['result'],'PASS')
        self.controller.release.assert_not_called()

    def test_pre_stopped_rejected(self):
        self.runner.arm_interruption.side_effect=AuthorityError('Not running')
        with self.assertRaises(AuthorityError):self.host.prepare_reboot()
        self.journal.record.assert_not_called()

    def test_identity_and_boundary_mutations(self):
        self.prepare();self.fresh()
        for field,value in dict(launch_id=str(uuid4()),process={},target={},cgroup_identity=[1,3],
                cgroup_name='launch-other',worker_alive=False,observed_boottime_ns=0).items():
            with self.subTest(field=field):
                old=self.witness[field];self.witness[field]=value
                with self.assertRaises(AuthorityError):self.host.reconcile_reboot()
                self.witness[field]=old

    def test_fresh_enrollment_required(self):
        self.prepare()
        with self.assertRaises(AuthorityError):self.host.reconcile_reboot()

    def test_cleanup_uncertainty(self):
        self.prepare();self.fresh();self.controller.runtime.launch.return_value['cleanup_confirmed']=False
        with self.assertRaises(AuthorityError):self.host.reconcile_reboot()

    def test_survivor_cannot_pass(self):
        self.prepare();self.fresh();self.controller.runtime.db.execute.return_value.fetchone.return_value=(1,)
        with self.assertRaises(AuthorityError):self.host.reconcile_reboot()

    def test_same_supervisor_generation_rejected(self):
        self.prepare();old=self.context['supervisor_generation'];self.fresh();self.context['supervisor_generation']=old
        self.host.initial_context=dict(self.context)
        with self.assertRaises(AuthorityError):self.host.reconcile_reboot()


class InstalledSuccessorTests(unittest.TestCase):
    def test_production_factories_load_successor_and_remain_closed(self):
        import socket
        from pathlib import Path
        from test_operational_enrollment import InstalledStartupTests
        from tools.agent_control import installed_runtime as ir, installed_config as ic
        from tools.agent_control.host_test_catalog import PROFILE, ROOT_ID
        from tools.agent_control.filesystem_evidence import FilesystemInspector
        from tools.agent_control.operational_enrollment import AdmissionState
        fixture=InstalledStartupTests('test_first_start_factories_enroll_reconcile_then_open')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        configs,attest,ids,receipt,candidate,approved=successor_fixture()
        root=dict(logical_id=ROOT_ID,host_root='/srv/bonup-agent-work/bonup-fe01/workspace',
            identity=[1,2,3002,3002],generation=2,
            exports=[dict(logical_id=str(uuid4()),relative='frontend/example.ts',identity=[1,3,3002,3002],kind='FILE',writable=False)],
            profile=asdict(PROFILE),storage=dict(mount_id=1,mode='EPHEMERAL_TMPFS_WORKSPACE',bytes=134217728,inodes=16384),
            repository_id=None,repository_identity=None)
        # JSON transport normalization, as the installed reader supplies.
        from tools.agent_control.serialization import parse_json
        import json
        roots=json.loads(json.dumps([root]))
        attest['filesystem_digest']=digest(roots)
        attest['bundle_digest']=digest({k:v for k,v in attest.items() if k!='bundle_digest'})
        fixture.documents={ir.CONTROLLER:configs['controller'],ir.SUPERVISOR:configs['supervisor'],
            ic.MANIFEST:approved,sc.ATTESTATION:attest,ic.IDENTITIES:ids,sc.RECEIPT:receipt,
            '/etc/bonup-agent-control/installation-candidate.json':candidate,
            '/etc/bonup-agent-control/installation-approved.json':approved,
            '/etc/bonup-agent-control/host-test-roots.json':roots}
        for effect in (fixture.cio,fixture.sio):
            effect.founder_root=lambda:ROOT
            effect.verify_crypto=Mock()
            effect.witness=lambda component:Mock(watches={})
            effect.inspector=lambda roots:FilesystemInspector(roots,storage_probe=lambda fd,p:p.data())
        def listener(name,gid):
            sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            sock.bind(str(Path(fixture.temp.name)/'successor-founder.sock'));sock.listen(1)
            return sock
        fixture.cio._listener_socket=listener
        fixture.start_services()
        self.assertEqual(fixture.ca.admission.state,AdmissionState.READY_CLOSED)
        self.assertEqual(fixture.sa.admission.state,AdmissionState.READY_CLOSED)
        self.assertIsNotNone(fixture.ca.driver.founder_factory)
        self.assertEqual(len(fixture.sa.driver.endpoint.plans),18)
        self.assertTrue(fixture.sa.driver.endpoint.host_only)
        with self.assertRaises(AuthorityError):fixture.ca.admission.require_open()
        # The factory-created intake, real signature verifier and durable audit
        # require a receipt plus a distinct host-test purpose before admission.
        import base64
        from test_founder_root import sign
        from tools.agent_control.identity import PeerIdentity,ProcessIdentity
        intake=fixture.ca.driver.founder_factory(lambda:(PeerIdentity(1000,1000,103),fixture.cio.process(103)))
        self.addCleanup(intake.close)
        def request(action,**arguments):
            return intake.request(dict(version=1,request_id=str(uuid4()),action=action,arguments=arguments))['result']
        challenge=request('REQUEST_FOUNDER_CHALLENGE',purpose='FOUNDER_HOST_TEST_AUTHORIZATION')
        session=request('SUBMIT_FOUNDER_SIGNATURE',challenge_id=digest(challenge),
            signature=base64.b64encode(sign(canonical_json(challenge).encode())).decode())['session']
        request('BEGIN_HOST_TEST_SESSION',session=session)
        self.assertEqual(fixture.ca.admission.state,AdmissionState.HOST_TEST_ONLY)
        self.assertEqual(fixture.sa.admission.state,AdmissionState.HOST_TEST_ONLY)
        with self.assertRaises(AuthorityError):fixture.ca.admission.run(lambda:None)
        request('END_HOST_TEST_SESSION')
        self.assertEqual(fixture.ca.admission.state,AdmissionState.CLOSED)
        self.assertEqual(fixture.sa.admission.state,AdmissionState.CLOSED)
        for args in ({'test_id':'unknown'},{'test_id':'uid_gid_drop','argv':['secret-canary']}):
            with self.assertRaises(AuthorityError):request('ENROLL_HOST_TEST_CASE',**args)
        with self.assertRaises(AuthorityError):fixture.ca.admission.open(fixture.ca.admission.session)


class HostAuditTests(unittest.TestCase):
    def test_rpc_maintenance_cannot_reenter_founder_dispatch(self):
        from tools.agent_control.founder_transport import FounderTransport
        from tools.agent_control.installed_transport import Packet,packet
        transport=object.__new__(FounderTransport)
        transport.dispatching=False
        transport.now=lambda:0
        transport.conn=Mock()
        transport.reader=Packet(0)
        transport.observe=Mock()
        transport.outgoing=b''
        transport.intake=Mock()
        request=dict(version=1,request_id=str(uuid4()),action='RUN_HOST_TEST_CASE',arguments={'test_id':'uid_gid_drop'})
        raw=packet(request)
        transport.conn.recv.side_effect=[raw[:4],raw[4:]]
        def dispatch(value):
            transport.poll()  # DuplexClient maintenance on the same thread.
            return {'accepted':True}
        transport.intake.request.side_effect=dispatch
        transport.poll();transport.poll()
        transport.intake.request.assert_called_once_with(request)
        self.assertEqual(transport.conn.recv.call_count,2)
        self.assertEqual(transport.outgoing,packet({'accepted':True}))
        self.assertFalse(transport.dispatching)

    def test_dispatch_audit_order_and_correlation(self):
        from tools.agent_control.host_test_launch import CatalogLaunches
        from types import SimpleNamespace
        runner=object.__new__(CatalogLaunches)
        runner.witness=None
        c=runner.controller=Mock()
        events=[]
        c.admission.run_host.side_effect=lambda eid,callback:callback()
        c._register.side_effect=lambda *args:events.append('VALIDATED') or 'launch'
        c._audit.side_effect=lambda *args:events.append(args)
        runner.run(CATALOG['uid_gid_drop'],SimpleNamespace(execution_id='execution'),request_id='request')
        self.assertEqual(events[0],'VALIDATED')
        self.assertEqual(events[1],('OPERATION_AUTHORIZED','request','AUTHORIZED','execution','launch'))
        c.prepare.assert_called_once_with('launch');c.release.assert_called_once_with('launch')

    def test_dispatch_denied_never_authorized(self):
        from tools.agent_control.host_test_launch import CatalogLaunches
        from types import SimpleNamespace
        runner=object.__new__(CatalogLaunches);runner.witness=None
        c=runner.controller=Mock();c.admission.run_host.side_effect=lambda eid,callback:callback()
        c._register.side_effect=AuthorityError('invalid grant')
        with self.assertRaises(AuthorityError):runner.run(CATALOG['uid_gid_drop'],SimpleNamespace(execution_id='execution'),request_id='request')
        self.assertEqual(c._audit.call_args.args[0],'OPERATION_DENIED')
        c.prepare.assert_not_called();c.release.assert_not_called()

    def test_setup_failure_follows_authorization(self):
        from tools.agent_control.host_test_launch import CatalogLaunches
        from types import SimpleNamespace
        runner=object.__new__(CatalogLaunches);runner.witness=None
        c=runner.controller=Mock();c.admission.run_host.side_effect=lambda eid,callback:callback()
        c._register.return_value='launch';c.prepare.side_effect=AuthorityError('setup')
        with self.assertRaises(AuthorityError):runner.run(CATALOG['uid_gid_drop'],SimpleNamespace(execution_id='execution'),request_id='request')
        self.assertEqual(c._audit.call_args.args[0],'OPERATION_AUTHORIZED')
        c.release.assert_not_called()


class EnrollmentStressTests(unittest.TestCase):
    def test_repeated_start_with_validation_latency(self):
        from test_operational_enrollment import InstalledStartupTests
        from tools.agent_control.operational_enrollment import AdmissionState
        for repetition in range(8):
            with self.subTest(repetition=repetition):
                fixture=InstalledStartupTests('test_first_start_factories_enroll_reconcile_then_open')
                fixture.setUp()
                original=fixture.cio.open_registry
                first=True
                def delayed_validation(path):
                    nonlocal first
                    if first:
                        first=False
                        self.assertTrue(fixture.enrollment_entered['supervisor'].wait(10))
                        # Model registry work taking longer than the security
                        # handshake timeout, before the actual connect boundary.
                        fixture.elapsed+=2
                    return original(path)
                fixture.cio.open_registry=delayed_validation
                try:
                    fixture.test_first_start_factories_enroll_reconcile_then_open()
                    self.assertEqual(fixture.ca.admission.state,AdmissionState.ADMISSION_OPEN)
                finally:fixture.doCleanups()


class WitnessTests(unittest.TestCase):
    def test_cleanup_precedes_persistence_even_when_evidence_fails(self):
        from tools.agent_control.interruption import Witness
        witness=Witness('controller');order=[]
        witness.capture=lambda launch:order.append('capture') or {'launch_id':launch}
        def persist(event):
            order.append('persist')
            raise OSError('evidence unavailable')
        witness.persist=persist
        with self.assertRaises(OSError):
            witness.observe(str(uuid4()),cleanup=lambda:order.append('cleanup'))
        self.assertEqual(order,['capture','cleanup','persist'])
        order.clear()
        witness.capture=Mock(side_effect=AuthorityError('uncertain'))
        with self.assertRaises(AuthorityError):
            witness.observe(str(uuid4()),cleanup=lambda:order.append('cleanup'))
        self.assertEqual(order,['cleanup'])

    def test_readonly_witness_storage_denied(self):
        import os,tempfile
        from types import SimpleNamespace
        from tools.agent_control.interruption import Witness
        with tempfile.TemporaryDirectory() as directory:
            witness=Witness('controller')
            witness._directory=lambda component:os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
            with patch('tools.agent_control.interruption.os.fstatvfs',return_value=SimpleNamespace(f_flag=os.ST_RDONLY)),self.assertRaises(AuthorityError):
                witness.preflight()

    def test_kernel_boundary_requires_dead_target_and_live_worker(self):
        import os,tempfile,stat
        from pathlib import Path
        from types import SimpleNamespace
        from tools.agent_control.interruption import Witness
        with tempfile.TemporaryDirectory() as directory:
            launch=str(uuid4())
            row=dict(launch_id=launch,process=dict(boot_id=str(uuid4()),pid=123,start_ticks=2),
                target=dict(boot_id=str(uuid4()),pid=124,start_ticks=3),
                cgroup_name='launch-'+launch,cgroup_identity=[1,2])
            witness=Witness('controller');witness.watches[launch]=(row,80,81)
            witness._directory=lambda component:os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
            with patch('tools.agent_control.interruption.dead',return_value=False):
                self.assertFalse(witness.observe(launch))
            with patch('tools.agent_control.interruption.dead',side_effect=[True,True]):
                self.assertFalse(witness.observe(launch))
            self.assertFalse(list(Path(directory).iterdir()))
            with patch('tools.agent_control.interruption.dead',side_effect=[True,False,False]), \
                 patch('tools.agent_control.interruption.live_canary'), \
                 patch('tools.agent_control.interruption.os.stat',return_value=SimpleNamespace(st_dev=1,st_ino=2)):
                self.assertTrue(witness.observe(launch))
            from tools.agent_control.serialization import parse_json
            evidence=parse_json((Path(directory)/(launch+'.json')).read_text())
            self.assertTrue(evidence['worker_alive'])
            self.assertEqual(evidence['phase'],'TARGET_INTERRUPTED')
            self.assertEqual(evidence['process'],row['process'])

    def test_stopped_canary_rejected(self):
        from tools.agent_control.interruption import live_canary
        process=Mock();process.pid=123
        for state in ('T','t','Z','X'):
            with self.subTest(state=state),patch('pathlib.Path.read_text',return_value='123 (canary) '+state+' 1'),self.assertRaises(AuthorityError):
                live_canary(process)


class CompletionTests(unittest.TestCase):
    def setUp(self):
        from tools.agent_control.host_test_runtime import HostTests
        from tools.agent_control.authority_installation import InstalledReceipt
        self.context=dict(boot_id=str(uuid4()),controller_generation=str(uuid4()),supervisor_generation=str(uuid4()))
        binding=InstallationBinding('a'*40,'b'*64,'c'*64,'d'*64,'e'*64,2)
        self.host=HostTests(Mock(),InstalledReceipt(binding,'f'*64,str(uuid4())),Mock(),Mock(),Mock(),lambda:dict(self.context))
        self.host.session='1'*64;self.host.verify=lambda:None;self.host.initial_context=dict(self.context)
        self.host.controller.admission.session='a'*64
        self.host.controller.remote._call.side_effect=lambda action,launch,data,response,**kw: dict(
            {k:v for k,v in data.items() if k!='reason'},closed=True,cleanup_confirmed=True)
        self.host.controller.runtime.db.execute.return_value.fetchall.return_value=[]
        self.host.accepted_contexts=[dict(self.context)]
        self.host.results={name:dict(receipt='f'*64,binding=binding.data(),catalog_version=VERSION,
            catalog_digest=CATALOG_DIGEST,test_id=name,launch_id=str(uuid4()),worker=list(case.worker),
            **self.context,evidence_digest='a'*64,result='PASS',correlation={}) for name,case in CATALOG.items()}

    def test_complete_is_evidence_only(self):
        self.assertEqual(self.host.complete()['activation'],False)
        self.host.controller.admission.open.assert_not_called()

    def test_missing_fails(self):
        self.host.results.pop('capability_bounds')
        with self.assertRaises(AuthorityError):self.host.complete()

    def test_wrong_evidence_fails(self):
        row=self.host.results['capability_bounds']
        for field,value in dict(result='FAIL',receipt='a'*64,binding={},catalog_version=2,
                catalog_digest='a'*64,worker=['root'],boot_id=str(uuid4()),test_id='uid_gid_drop').items():
            with self.subTest(field=field):
                old=row[field];row[field]=value
                with self.assertRaises(AuthorityError):self.host.complete()
                row[field]=old

    def test_duplicate_launch_fails(self):
        self.host.results['capability_bounds']['launch_id']=self.host.results['uid_gid_drop']['launch_id']
        with self.assertRaises(AuthorityError):self.host.complete()

    def test_caller_pass_is_not_an_operation(self):
        with self.assertRaises(AuthorityError):self.host.collect({'test_id':'uid_gid_drop','result':'PASS'})


class ServiceEventTests(unittest.TestCase):
    def test_exact_unit_prefix_only(self):
        from tools.agent_control.service_evidence import event_reason,UNITS
        message="Failed with result 'watchdog'."
        for unit in UNITS:
            self.assertEqual(event_reason(unit,message),'WATCHDOG')
            self.assertEqual(event_reason(unit,unit+': '+message),'WATCHDOG')
            self.assertIsNone(event_reason(unit,'other.service: '+message))
            self.assertIsNone(event_reason(unit,message+' arbitrary'))
        with self.assertRaises(AuthorityError):event_reason('application.service',message)
