"""Synthetic authority observations; no installed services or privileged launches."""
import base64
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from test_founder_root import ROOT, BOOT, sign
from tools.agent_control.authority_installation import InstallationBinding, verify_receipt
from tools.agent_control.authority_journal import AuthorityJournal
from tools.agent_control.founder_intake import FounderIntake, FounderPolicy
from tools.agent_control.host_test_catalog import CATALOG, CATALOG_DIGEST, IDS, select
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.operational_enrollment import Admission, AdmissionState
from tools.agent_control.registry import Registry
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import AuthorityError, ValidationError


BINDING = InstallationBinding('a'*40, 'b'*64, 'c'*64, 'd'*64, 'e'*64, 2)


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name)
        self.registry = Registry.initialize(path/'control.sqlite3', path/'history.git', operation_id=str(uuid4()))
        self.addCleanup(self.registry.close)
        self.journal = AuthorityJournal(self.registry)
        self.admission = Admission()
        self.admission.starting()
        self.admission.enrolled('f'*64, lambda: None)
        self.admission.reconciled()
        self.peer = PeerIdentity(1000,1000,1234)
        self.process = ProcessIdentity(BOOT,1234,42)
        self.now = datetime(2026,9,15,tzinfo=timezone.utc)
        self.ticks = 0
        self.receipt = dict(version=1,binding=BINDING.data(),installation_id=str(uuid4()),
                            activation=False,verified_artifacts_digest=BINDING.approved_inventory_digest)
        self.policy = FounderPolicy(True,BINDING,ROOT.identity,digest(self.receipt))
        class Controller:
            pass
        self.controller = Controller()
        self.controller.admission = self.admission
        self.intake = self.make()

    def make(self, policy=None):
        return FounderIntake(policy or self.policy, ROOT, lambda: (self.peer,self.process), self.journal,
            controller=self.controller,runner=None,runtime_context=lambda: dict(boot_id=BOOT),
            receipt_reader=lambda: canonical_json(self.receipt).encode(),candidate_reader=lambda: (b'',b''),
            clock=lambda: self.now,boottime=lambda: self.ticks)

    def request(self, action, **arguments):
        return self.intake.request(dict(version=1,request_id=str(uuid4()),action=action,arguments=arguments))['result']

    def challenge(self, purpose='FOUNDER_INSTALLATION_APPROVAL'):
        return self.request('REQUEST_FOUNDER_CHALLENGE',purpose=purpose)

    def submit(self, challenge):
        return self.request('SUBMIT_FOUNDER_SIGNATURE',challenge_id=digest(challenge),
            signature=base64.b64encode(sign(canonical_json(challenge).encode())).decode())

    def test_disabled_policy(self):
        with self.assertRaises(AuthorityError):self.make(replace(self.policy,enabled=False))

    def test_enabled_challenge_and_durable_audit(self):
        challenge=self.challenge()
        self.assertEqual(challenge['binding']['provisioning_generation'],2)
        event=self.journal.load(digest(challenge))
        self.assertEqual(event['event'],'FOUNDER_CHALLENGE_ISSUED')
        self.assertTrue(self.registry.db.execute('SELECT 1 FROM outbox').fetchone())

    def test_valid_signature_and_audit(self):
        challenge=self.challenge()
        self.assertEqual(self.submit(challenge)['session'],digest(challenge))
        self.assertEqual(self.journal.load(digest(challenge))['event'],'FOUNDER_SESSION_CREATED')

    def test_uid_without_signature(self):
        challenge=self.challenge()
        with self.assertRaises(AuthorityError):
            self.request('SUBMIT_FOUNDER_SIGNATURE',challenge_id=digest(challenge),signature=base64.b64encode(bytes(64)).decode())
        self.assertEqual(self.journal.load(digest(challenge))['event'],'FOUNDER_SIGNATURE_DENIED')

    def test_root_denied(self):
        self.peer=PeerIdentity(0,0,1234)
        with self.assertRaises(AuthorityError):self.challenge()

    def test_forged_identity_fields(self):
        for field in ('pid','uid','role','boot_id','public_key'):
            with self.subTest(field=field),self.assertRaises(AuthorityError):
                self.request('REQUEST_FOUNDER_CHALLENGE',purpose='FOUNDER_INSTALLATION_APPROVAL',**{field:'forged'})

    def test_process_start_change(self):
        challenge=self.challenge()
        self.process=ProcessIdentity(BOOT,1234,43)
        with self.assertRaises(AuthorityError):self.submit(challenge)

    def test_boot_change(self):
        challenge=self.challenge()
        self.process=ProcessIdentity(str(uuid4()),1234,42)
        with self.assertRaises(AuthorityError):self.submit(challenge)

    def test_replay(self):
        challenge=self.challenge();self.submit(challenge)
        with self.assertRaises(AuthorityError):self.submit(challenge)

    def test_expired(self):
        challenge=self.challenge();self.ticks=61
        with self.assertRaises(AuthorityError):self.submit(challenge)

    def test_activation_disabled(self):
        with self.assertRaises(AuthorityError):self.challenge('FOUNDER_ACTIVATION_APPROVAL')

    def test_missing_receipt(self):
        self.intake.receipt_reader=lambda: b'{}'
        with self.assertRaises(AuthorityError):self.challenge('FOUNDER_HOST_TEST_AUTHORIZATION')

    def test_wrong_receipt_generation(self):
        self.receipt['binding']['provisioning_generation']=1
        with self.assertRaises(AuthorityError):self.challenge('FOUNDER_HOST_TEST_AUTHORIZATION')

    def test_wrong_receipt_inventory(self):
        self.receipt['verified_artifacts_digest']='a'*64
        with self.assertRaises(AuthorityError):self.challenge('FOUNDER_HOST_TEST_AUTHORIZATION')

    def test_host_challenge_requires_reconciliation(self):
        self.admission.state=AdmissionState.RECONCILING
        with self.assertRaises(AuthorityError):self.challenge('FOUNDER_HOST_TEST_AUTHORIZATION')

    def test_receipt_does_not_create_founder_session(self):
        verify_receipt(canonical_json(self.receipt).encode(),BINDING,digest(self.receipt))
        self.assertFalse(self.intake.founder.sessions)

    def test_audit_no_private_material(self):
        self.submit(self.challenge())
        from test_founder_root import SEED
        records=''.join(r[0] for r in self.registry.db.execute('SELECT payload FROM audit_events'))
        self.assertNotIn(SEED.hex(),records)

    def test_host_denial_audit_received_then_denied(self):
        from tools.agent_control.serialization import parse_json
        for action,args in (('RUN_HOST_TEST_CASE',{'test_id':'uid_gid_drop'}),
                ('PREPARE_INTERRUPTION_TEST',{'test_id':'controller_crash'}),
                ('RECONCILE_REBOOT_TEST',{}),
                ('ENROLL_HOST_TEST_CASE',{'test_id':'unknown'}),
                ('ENROLL_HOST_TEST_CASE',{'test_id':'uid_gid_drop','argv':['synthetic-secret-value']})):
            request_id=str(uuid4())
            with self.subTest(action=action,args=args),self.assertRaises(AuthorityError):
                self.intake.request(dict(version=1,request_id=request_id,action=action,arguments=args))
            events=[parse_json(row[0]) for row in self.registry.db.execute('SELECT payload FROM audit_events ORDER BY sequence')]
            events=[row for row in events if row.get('routing',{}).get('request_id')==request_id]
            self.assertEqual([row['event_type'] for row in events],['HOST_TEST_REQUEST_RECEIVED','HOST_TEST_AUTHORIZATION_DENIED'])
            self.assertNotIn('synthetic-secret-value',canonical_json(events))

    def test_installation_purpose_cannot_authorize_host_tests(self):
        from unittest.mock import Mock
        self.controller.runtime=Mock()
        self.controller.runtime.db.execute.return_value.fetchone.return_value=None
        session=self.submit(self.challenge())['session']
        with self.assertRaises(AuthorityError):self.request('BEGIN_HOST_TEST_SESSION',session=session)
        records=''.join(row[0] for row in self.registry.db.execute('SELECT payload FROM audit_events'))
        self.assertNotIn('HOST_TEST_AUTHORIZED',records)


class CatalogAdmissionTests(unittest.TestCase):
    def test_exact_catalog(self):
        self.assertEqual(len(IDS),18)
        self.assertEqual(set(CATALOG),set(IDS))
        self.assertEqual(CATALOG_DIGEST,digest([CATALOG[n].data() for n in IDS]))

    def test_catalog_immutable(self):
        with self.assertRaises(TypeError):CATALOG['unknown']=None
        with self.assertRaises(Exception):CATALOG[IDS[0]].argv=('/usr/bin/false',)

    def test_unknown_case(self):
        with self.assertRaises(AuthorityError):select({'test_id':'unknown'})

    def test_no_overrides(self):
        for field in ('executable','argv','path','uid','gid','capability','environment','resources','network'):
            with self.subTest(field=field),self.assertRaises(AuthorityError):
                select(dict(test_id=IDS[0],**{field:'override'}))

    def test_host_mode_never_opens_normal_admission(self):
        admission=Admission();admission.starting();admission.enrolled('a'*64,lambda:None);admission.reconciled()
        admission.begin_host_tests(('execution',),lambda:None)
        self.assertEqual(admission.state,AdmissionState.HOST_TEST_ONLY)
        with self.assertRaises(AuthorityError):admission.require_open()
        with self.assertRaises(AuthorityError):admission.open('a'*64)
        self.assertEqual(admission.run_host('execution',lambda:'bounded'),'bounded')
        with self.assertRaises(AuthorityError):admission.run_host('arbitrary',lambda:None)
        admission.end_host_tests()
        self.assertEqual(admission.state,AdmissionState.CLOSED)
        with self.assertRaises(AuthorityError):admission.open('a'*64)


class NormalLifecycleTests(unittest.TestCase):
    def test_catalog_uses_installed_factory_normal_launch(self):
        from test_installed_runtime import FactoryCompositionTests
        from tools.agent_control.host_test_catalog import ROOT_ID
        from tools.agent_control.host_test_launch import CatalogLaunches, supervisor_catalog
        from tools.agent_control.filesystem_evidence import FilesystemInspector
        from types import MappingProxyType
        fixture=FactoryCompositionTests('test_full_production_factory_lifecycle')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        controller=fixture.driver.controller
        endpoint=fixture.sa.driver.endpoint
        # Only kernel effects are synthetic; all controller/authority/FD/gate code
        # comes from the installed production factories.
        original=next(iter(endpoint.inspector.mappings.values()))
        mapping=replace(original,logical_id=ROOT_ID)
        endpoint.inspector=FilesystemInspector((mapping,),storage_probe=lambda fd,p:p.data())
        anchor=ProcessIdentity(BOOT,100,10)
        endpoint.plans=MappingProxyType({p.plan_id:p for p in supervisor_catalog(mapping,endpoint.generation,anchor)})
        runner=CatalogLaunches(controller,BINDING,mapping.expectation(),anchor,peer=PeerIdentity(0,0,100))
        admission=Admission();admission.starting();admission.enrolled('a'*64,lambda:None);admission.reconciled()
        controller.admission=admission
        admission.begin_host_tests(runner.execution_ids(),lambda:None)
        case=CATALOG['uid_gid_drop']
        verify=lambda:None
        verify.expires_at='2026-09-15T00:00:00Z'
        verify.elapsed_deadline=30
        enrolled=runner.enroll(case,verify)
        launch=runner.run(case,enrolled)
        self.assertEqual(controller.runtime.launch(launch)['state'],'RUNNING')
        self.assertIn(launch,fixture.kernel.releases)
        self.assertTrue(fixture.kernel.gates[-1].used)
        self.assertEqual(controller.stop(launch)['state'],'TERMINAL')
