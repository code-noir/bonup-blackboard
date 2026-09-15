"""Per-start identities; deterministic race tests never sleep or create host state."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from uuid import uuid4

from tools.agent_control.operational_enrollment import (
    Admission, AdmissionState, Enrollment, InstallationIdentity, Observation,
    installation_pair, installation_spec)
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import AuthorityError, ValidationError

BOOT = '00000000-0000-4000-8000-000000000001'


def identity(component):
    return InstallationIdentity.parse(dict(installation_spec(component),
        bundle_digest='a'*64, configuration_digest=('b' if component=='controller' else 'c')*64))


class Pair:
    def __init__(self):
        self.time = 0
        self.identities = {n:identity(n) for n in ('controller','supervisor')}
        self.observations = {n:Observation(PeerIdentity(i.uid,i.gid,41+j),
            ProcessIdentity(BOOT,41+j,101+j),i.service)
            for j,(n,i) in enumerate(self.identities.items())}
        self.c = self.new('controller');self.s = self.new('supervisor')

    def new(self, name):
        peer = 'controller' if name == 'supervisor' else 'supervisor'
        return Enrollment(self.identities[name],self.identities[peer],
            local_observe=lambda:self.observations[name], observe=lambda:self.observations[peer],
            now=lambda:self.time)

    def exchange(self):
        self.begin=self.c.begin()
        self.challenge=self.s.receive(canonical_json(self.begin).encode())
        self.proof=self.c.receive(canonical_json(self.challenge).encode())
        self.accepted=self.s.receive(canonical_json(self.proof).encode())
        self.c.receive(canonical_json(self.accepted).encode())

    def opened(self):
        self.exchange()
        for s in (self.c,self.s):s.admission.reconciled();s.admission.open(s.session)


class IdentityTests(unittest.TestCase):
    def test_static_identity_has_no_process_fields(self):
        for role in ('controller','supervisor'):
            spec=installation_spec(role)
            self.assertFalse({'pid','start_ticks','boot_id','generation','runtime_generation'} & spec.keys())
            self.assertEqual(spec['uid'],3000 if role=='controller' else 0)

    def test_unknown_operational_fields_rejected(self):
        for field in ('pid','start_ticks','boot_id','generation','role'):
            data=dict(installation_spec('controller'),bundle_digest='a'*64,configuration_digest='b'*64)
            data[field]='forged'
            with self.assertRaises(ValidationError):InstallationIdentity.parse(data)

    def test_uid_gid_required_and_fixed(self):
        for field in ('uid','gid'):
            data=dict(installation_spec('controller'),bundle_digest='a'*64,configuration_digest='b'*64)
            data.pop(field)
            with self.assertRaises(ValidationError):InstallationIdentity.parse(data)
            data[field]=1000
            with self.assertRaises(AuthorityError):InstallationIdentity.parse(data)

    def test_capabilities_cannot_be_changed(self):
        data=dict(installation_spec('supervisor'),bundle_digest='a'*64,configuration_digest='b'*64)
        data['capabilities'].append('CAP_SYS_ADMIN')
        with self.assertRaises(AuthorityError):InstallationIdentity.parse(data)

    def test_manifest_pair_uses_only_static_fields(self):
        manifest=dict(bundle_digest='a'*64,configuration_digests=dict(controller='b'*64,supervisor='c'*64))
        local,peer=installation_pair(dict(service=installation_spec('controller')),manifest,'controller')
        self.assertEqual(local,identity('controller'));self.assertEqual(peer,identity('supervisor'))


class EnrollmentTests(unittest.TestCase):
    def setUp(self):self.p=Pair()

    def test_first_start_closed(self):
        for session in (self.p.c,self.p.s):
            self.assertEqual(session.admission.state,AdmissionState.ENROLLMENT_CLOSED)
            with self.assertRaises(AuthorityError):session.admission.require_open()

    def test_valid_handshake_then_reconciliation_then_open(self):
        self.p.exchange()
        self.assertEqual(self.p.c.session,self.p.s.session)
        for s in (self.p.c,self.p.s):
            self.assertEqual(s.admission.state,AdmissionState.RECONCILING)
            with self.assertRaises(AuthorityError):s.admission.open(s.session)
            s.admission.reconciled()
            self.assertEqual(s.admission.state,AdmissionState.READY_CLOSED)
            with self.assertRaises(AuthorityError):s.admission.require_open()
            s.admission.open(s.session)
            s.admission.require_open()

    def test_uid_only_cannot_open(self):
        with self.assertRaises(AuthorityError):self.p.s.admission.open('a'*64)

    def test_wrong_uid(self):
        self.p.observations['controller']=replace(self.p.observations['controller'],peer=PeerIdentity(1000,1000,41))
        with self.assertRaises(AuthorityError):self.p.s.receive(canonical_json(self.p.c._message('ENROLL_BEGIN',{})).encode())
        self.assertEqual(self.p.s.admission.state,AdmissionState.STOPPING)

    def test_wrong_service_cgroup(self):
        self.p.observations['controller']=replace(self.p.observations['controller'],service='application.service')
        with self.assertRaises(AuthorityError):self.p.s.verify()

    def test_start_identity_replacement(self):
        self.p.opened()
        o=self.p.observations['controller']
        self.p.observations['controller']=replace(o,process=replace(o.process,start_ticks=999))
        with self.assertRaises(AuthorityError):self.p.s.admission.require_open()
        self.assertEqual(self.p.s.admission.state,AdmissionState.STOPPING)

    def test_boot_change_closes_admission(self):
        self.p.opened()
        o=self.p.observations['supervisor']
        self.p.observations['supervisor']=replace(o,process=replace(o.process,boot_id=str(uuid4())))
        with self.assertRaises(AuthorityError):self.p.c.admission.require_open()

    def test_forged_pid_and_role_rejected(self):
        for field in ('pid','uid','gid','role','boot_id'):
            p=Pair();msg=p.c.begin();msg['data'][field]='forged'
            with self.assertRaises(ValidationError):p.s.receive(canonical_json(msg).encode())

    def test_wrong_bundle_claim_rejected(self):
        msg=self.p.c.begin();msg['data']['installation']='d'*64
        with self.assertRaises(AuthorityError):self.p.s.receive(canonical_json(msg).encode())

    def test_wrong_generation_challenge_rejected(self):
        begin=self.p.c.begin();reply=self.p.s.receive(canonical_json(begin).encode())
        reply['data']['controller']['generation']=str(uuid4())
        with self.assertRaises(AuthorityError):self.p.c.receive(canonical_json(reply).encode())

    def test_replayed_proof_rejected(self):
        self.p.exchange()
        with self.assertRaises(AuthorityError):self.p.s.receive(canonical_json(self.p.proof).encode())
        self.assertEqual(self.p.s.admission.state,AdmissionState.STOPPING)

    def test_reused_nonce_on_new_session_rejected(self):
        self.p.exchange();old=self.p.proof
        self.p.c=self.p.new('controller');self.p.s=self.p.new('supervisor')
        challenge=self.p.s.receive(canonical_json(self.p.c.begin()).encode())
        self.p.c.receive(canonical_json(challenge).encode())
        with self.assertRaises(AuthorityError):self.p.s.receive(canonical_json(old).encode())

    def test_handshake_deadline(self):
        msg=self.p.c.begin();self.p.time=1
        with self.assertRaises(AuthorityError):self.p.s.receive(canonical_json(msg).encode())

    def test_duplicate_unknown_and_invalid_json(self):
        for raw in (b'{"version":1,"version":1}',b'{}',b'\xff',b'x'*4097):
            p=Pair()
            with self.assertRaises((AuthorityError,ValidationError)):p.s.receive(raw)
            self.assertEqual(p.s.admission.state,AdmissionState.STOPPING)

    def test_controller_restart_requires_fresh_session(self):
        self.p.opened();old=self.p.c.session;self.p.c.disconnect();self.p.s.disconnect()
        self.p.c=self.p.new('controller');self.p.s=self.p.new('supervisor')
        self.p.exchange();self.assertNotEqual(old,self.p.c.session)
        self.assertEqual(self.p.c.admission.state,AdmissionState.RECONCILING)

    def test_supervisor_restart_changes_generation(self):
        self.p.opened();old=self.p.s.generation
        new=self.p.new('supervisor')
        self.assertNotEqual(new.generation,old)
        with self.assertRaises(AuthorityError):new.admission.require_open()

    def test_both_restart_no_previous_acceptance(self):
        self.p.exchange();old=self.p.accepted
        self.p.c=self.p.new('controller');self.p.s=self.p.new('supervisor')
        self.p.c.begin()
        with self.assertRaises((AuthorityError,ValidationError)):self.p.c.receive(canonical_json(old).encode())

    def test_disconnect_reconnect_does_not_reopen(self):
        self.p.opened();self.p.c.disconnect()
        with self.assertRaises(AuthorityError):self.p.c.admission.open(self.p.c.session)
        with self.assertRaises(AuthorityError):self.p.c.admission.reconciled()

    def test_enrollment_is_not_a_grant(self):
        self.p.opened()
        self.assertFalse(hasattr(self.p.c,'grant'))
        self.assertFalse(hasattr(self.p.c,'runtime'))
        self.assertFalse(hasattr(self.p.c,'founder'))


class AuthorityIntegrationTests(unittest.TestCase):
    def controller(self, admission):
        from tools.agent_control.composition import ControllerRuntime
        from unittest.mock import Mock
        from types import SimpleNamespace
        controller=object.__new__(ControllerRuntime)
        controller.admission=admission
        controller.sequencer=Mock()
        controller.authorization=SimpleNamespace(audit=Mock())
        controller.proposals={}
        controller.runtime=Mock()
        controller.runtime.launch.return_value=dict(request_id=str(uuid4()),execution_id=str(uuid4()))
        return controller

    def test_controller_register_prepare_release_all_closed(self):
        from tools.agent_control.composition import ControllerRuntime
        from unittest.mock import Mock
        admission=Admission();admission.starting()
        controller=self.controller(admission)
        for method,args in ((controller.register,(b'{}',None)),(controller.prepare,('launch',)),(controller.release,('launch',))):
            with self.assertRaises(AuthorityError):method(*args)
        controller.sequencer.prepare.assert_not_called()
        controller.sequencer.release.assert_not_called()

    def test_open_gate_retains_original_authorizer(self):
        from tools.agent_control.composition import ControllerRuntime
        from unittest.mock import Mock
        p=Pair();p.opened()
        controller=self.controller(p.c.admission)
        controller.sequencer.release.side_effect=AuthorityError('grant revoked')
        with self.assertRaises(AuthorityError):controller.release('launch')
        controller.sequencer.release.assert_called_once_with('launch')

    def test_controller_closed_after_preparation_cannot_release(self):
        from tools.agent_control.composition import ControllerRuntime
        from unittest.mock import Mock
        p=Pair();p.opened()
        controller=self.controller(p.c.admission)
        controller.prepare('launch');p.c.disconnect()
        with self.assertRaises(AuthorityError):controller.release('launch')
        controller.sequencer.release.assert_not_called()

    def test_closed_supervisor_never_prepares_even_if_ready(self):
        from tools.agent_control.composition import SupervisorEndpoint,message
        from unittest.mock import Mock
        p=Pair();p.exchange();backend=Mock()
        endpoint=SupervisorEndpoint((),backend,generation=p.s.generation,boot_id=BOOT,admission=p.s.admission)
        endpoint.ready=True
        data=dict(plan_id=str(uuid4()),execution_id=str(uuid4()),authorization_digest='a'*64,
            workspace_digest='a'*64,plan_digest='a'*64,expires_at='2030-01-01T00:00:00Z',elapsed_deadline_ns=123)
        with self.assertRaises(AuthorityError):endpoint.handle(message('PREPARE_LAUNCH',str(uuid4()),p.s.generation,BOOT,data))
        self.assertEqual(backend.mock_calls,[])


class InstalledStartupTests(unittest.TestCase):
    """Use both production factories; replace only kernel observations/effects."""
    def setUp(self):
        import socket
        import threading
        from pathlib import Path
        import test_supervisor as fixtures
        import test_installed_runtime as previous
        from tools.agent_control import installed_config as ic, installed_runtime as ir
        from tools.agent_control.installed_transport import OperationalChannel
        fixtures.RuntimeTests.setUp(self)
        self.supervisor.stop(self.launch_id,'CANCELLED')
        self.controller_json=dict(version=2,service=installation_spec('controller'),founder_uid=1000,
                                  founder=None,proposal=None,executions=[])
        self.supervisor_json=dict(version=2,service=installation_spec('supervisor'),roots=[],plans=[])
        m,i=previous.manifest_for(self.controller_json,self.supervisor_json)
        m['version']=3
        m['files'][ic.PREFIX+'/tools/agent_control/operational_enrollment.py']='a'*64
        m['bundle_digest']=digest({k:v for k,v in m.items() if k!='bundle_digest'})
        self.documents={ic.MANIFEST:m,ic.IDENTITIES:i,ir.CONTROLLER:self.controller_json,ir.SUPERVISOR:self.supervisor_json}
        self.csocket,self.ssocket=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(self.csocket.close);self.addCleanup(self.ssocket.close)
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        listener.bind(str(Path(self.temp.name)/'enrollment.sock'));listener.listen(1)
        self.addCleanup(listener.close)
        test=self
        class IO(previous.CompositionIO):
            def peer(self,sock):return PeerIdentity(3000,3000,101) if self.component=='supervisor' else PeerIdentity(0,0,100)
            def enroll(self,local,remote):
                own=lambda:Observation(self.identity(),self.process(self.identity().pid),local.service)
                obs=lambda:Observation(self.peer(None),self.process(self.peer(None).pid),remote.service)
                channel=OperationalChannel(test.ssocket if self.component=='supervisor' else test.csocket,
                    local,remote,local_observe=own,observe=obs,now=self.now)
                channel.listener=listener if self.component=='supervisor' else None
                channel.enroll()
                return channel
        self.sio,self.cio=IO(self,'supervisor'),IO(self,'controller')
        self.sa=ir.build_installed_supervisor_adapters(_io=self.sio)
        self.ca=ir.build_installed_controller_adapters(_io=self.cio)
        self.halt=threading.Event();self.server_errors=[];self.loop=None;self.service=None
        self.addCleanup(self.shutdown_services)

    def start_services(self):
        import threading
        from tools.agent_control import supervisor_entry,controller_entry
        def server():
            try:
                self.loop=supervisor_entry.start(adapters=self.sa)
                self.ready_at_notify=self.sa.admission.state
                while not self.halt.is_set():
                    self.loop.step();self.halt.wait(.001)
            except BaseException as error:
                self.server_errors.append(error)
                self.ssocket.close()
        self.thread=threading.Thread(target=server)
        self.thread.start()
        try:self.service=controller_entry.start(adapters=self.ca)
        except BaseException:
            self.halt.set();self.thread.join(2)
            if self.server_errors:raise self.server_errors[-1]
            raise

    def shutdown_services(self):
        if self.service is not None:
            try:self.service.close()
            except AuthorityError:pass  # Deliberate disconnect scenarios still verify closed state.
        self.halt.set()
        if hasattr(self,'thread'):self.thread.join(2);self.assertFalse(self.thread.is_alive())
        if self.loop is not None:self.loop.shutdown()

    def test_first_start_factories_enroll_reconcile_then_open(self):
        self.start_services()
        self.assertEqual(self.ca.admission.state,AdmissionState.ADMISSION_OPEN)
        self.assertEqual(self.sa.admission.state,AdmissionState.ADMISSION_OPEN)
        self.assertEqual(self.ready_at_notify,AdmissionState.RECONCILING)
        self.assertEqual(self.sio.notifications[0],'READY=1')
        self.assertEqual(self.cio.notifications[0],'READY=1')
        self.assertEqual(self.ca.admission.session,self.sa.admission.session)
        self.assertEqual(self.ca.driver.listeners,{})
        self.assertEqual(self.sa.driver.endpoint.launches,{})
        self.assertFalse(hasattr(self.sa.driver.endpoint,'runtime'))
        self.assertEqual(self.server_errors,[])

    def test_installed_configuration_contains_no_operational_identity(self):
        from tools.agent_control.installed_config import validate_activation,MANIFEST,IDENTITIES
        for name,config in (('controller',self.controller_json),('supervisor',self.supervisor_json)):
            raw=canonical_json(config)
            for field in ('"pid"','"start_ticks"','"boot_id"','"runtime_generation"'):
                self.assertNotIn(field,raw)
            validate_activation(self.documents[MANIFEST],self.documents[IDENTITIES],config,component=name)

    def test_service_enrollment_does_not_enroll_founder_or_model(self):
        self.start_services()
        for name in ('founder','proposal'):
            with self.assertRaises(AuthorityError):self.ca.driver.request(name,{},None)
        self.assertEqual(self.ca.driver.controller.proposals,{})

    def test_controller_disconnect_closes_admission(self):
        self.start_services()
        self.ca.driver.client.close()
        self.assertEqual(self.ca.admission.state,AdmissionState.STOPPING)
        with self.assertRaises(AuthorityError):self.ca.driver.controller.release('not-a-launch')

    def test_startup_malformed_identity_fails_before_enrollment(self):
        from tools.agent_control import controller_entry,installed_config as ic
        self.documents[ic.MANIFEST]['approved']=False
        with self.assertRaises(AuthorityError):controller_entry.start(adapters=self.ca)
        self.assertFalse(hasattr(self.ca,'operational_channel'))
        self.assertEqual(self.cio.notifications,[])


class PreparedLaunchTests(unittest.TestCase):
    def setUp(self):
        import test_composition as previous
        previous.CompositionTests.setUp(self)
        self.p=Pair();self.p.opened()
        # Existing durable fixture supplies grants; the new session supplies only
        # the additional admission gate. No grant is generated by enrollment.
        self.endpoint.admission=self.p.s.admission

    def test_unchanged_grant_and_open_admission_runs_normal_flow(self):
        self.assertEqual(self.sequencer.prepare(self.launch_id)['state'],'PREPARED')
        self.assertEqual(self.sequencer.release(self.launch_id)['state'],'RUNNING')
        self.assertEqual(self.backend.releases,[self.launch_id])
        self.sequencer.stop(self.launch_id,'CANCELLED')

    def test_prepared_launch_cannot_release_after_session_disconnect(self):
        self.sequencer.prepare(self.launch_id)
        self.p.s.disconnect()
        with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)
        self.assertEqual(self.backend.releases,[])
        self.assertEqual(self.backend.children,{})

    def test_prepared_launch_cannot_release_before_reconciliation(self):
        self.sequencer.prepare(self.launch_id)
        other=Pair();other.exchange()
        self.endpoint.admission=other.s.admission
        with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)
        self.assertEqual(self.backend.releases,[])
        self.assertEqual(self.backend.children,{})


class InstalledPolicyTests(unittest.TestCase):
    def test_default_kernel_adapter_rejects_precomputed_legacy_identity(self):
        from tools.agent_control.installed_runtime import KernelIO,build_installed_controller_adapters,CONTROLLER
        from unittest.mock import Mock
        io=KernelIO()
        io.read=Mock(return_value={'version':2})
        io.enroll=Mock();io.open_registry=Mock();io.verify_code=Mock()
        with self.assertRaises(AuthorityError):
            build_installed_controller_adapters(_io=io).load_config(CONTROLLER)
        io.enroll.assert_not_called();io.open_registry.assert_not_called();io.verify_code.assert_not_called()

    def test_no_caller_provided_operational_field_in_static_config(self):
        manifest=dict(bundle_digest='a'*64,configuration_digests=dict(controller='b'*64,supervisor='c'*64))
        for field in ('pid','start_ticks','boot_id','generation'):
            config=dict(service=dict(installation_spec('controller'),**{field:123}))
            with self.assertRaises(AuthorityError):installation_pair(config,manifest,'controller')

    def test_supervisor_protocol_ready_does_not_report_admission_open(self):
        from tools.agent_control.supervisor_entry import SupervisorDriver
        from tools.agent_control.composition import SupervisorEndpoint
        from unittest.mock import Mock
        p=Pair();p.exchange()
        endpoint=SupervisorEndpoint((),Mock(),generation=p.s.generation,boot_id=BOOT,admission=p.s.admission)
        endpoint.ready=True
        driver=SupervisorDriver(endpoint,Mock(),heartbeat=Mock(),control=Mock())
        self.assertTrue(driver.protocol_ready())
        self.assertEqual(driver.establish_admission(),'CLOSED')
        p.s.admission.reconciled();p.s.admission.open(p.s.session)
        self.assertEqual(driver.establish_admission(),'OPEN')

    def test_deadline_failure_prevents_admission_open_request(self):
        from tools.agent_control.installed_runtime import InstalledControllerDriver
        from unittest.mock import Mock
        p=Pair();p.exchange()
        driver=object.__new__(InstalledControllerDriver)
        driver.controller=Mock();driver.controller.admission=p.c.admission
        driver.controller.runtime.db.execute.return_value.fetchone.return_value=None
        driver.deadlines=Mock(side_effect=AuthorityError('deadline service unavailable'))
        with self.assertRaises(AuthorityError):driver.establish_admission()
        driver.controller.remote._call.assert_not_called()
        self.assertEqual(p.c.admission.state,AdmissionState.RECONCILING)
