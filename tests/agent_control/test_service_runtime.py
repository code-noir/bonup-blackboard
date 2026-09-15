"""Block 1: deterministic entrypoint/authentication/loop tests; no daemon starts."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from uuid import uuid4

from tools.agent_control import controller_entry, supervisor_entry
from tools.agent_control.composition import message
from tools.agent_control.composition_protocol import frame
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2
from tools.agent_control.service_runtime import ServiceConfig, PeerAuthenticator, ServiceLoop
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control.composition import SupervisorEndpoint
from tools.agent_control.supervisor import SyntheticProcessBackend

BOOT = '00000000-0000-4000-8000-000000000001'
GEN = '00000000-0000-4000-8000-000000000002'
PEER_GEN = '00000000-0000-4000-8000-000000000003'
TOKEN = '00000000-0000-4000-8000-000000000004'


def configuration(component='supervisor'):
    peer, uid = ('controller', 3000) if component == 'supervisor' else ('supervisor', 0)
    return dict(version=1, component=component, approved=True, generation=GEN, boot_id=BOOT,
        manifest_digest='a'*64, registry_path=None if component == 'supervisor' else
        '/var/lib/bonup-agent-control/control.sqlite3',
        peer=dict(endpoint=peer, uid=uid, gid=uid, pid=42, start_ticks=123, boot_id=BOOT,
                  generation=PEER_GEN, enrollment_id=TOKEN))


class Work:
    def __init__(self):
        self.requests = []
        self.result = None
        self.cancelled = False
    def submit(self, request): self.requests.append(request)
    def take_result(self):
        result, self.result = self.result, None
        return result
    def cancel(self): self.cancelled = True


class Transport:
    def __init__(self, cfg, trace):
        p = cfg['peer']
        self.observation = (PeerIdentity(p['uid'], p['gid'], p['pid']),
            ProcessIdentity(p['boot_id'], p['pid'], p['start_ticks']),
            dict(endpoint=p['endpoint'], generation=p['generation'], enrollment_id=p['enrollment_id']))
        self.trace, self.events, self.sent = trace, [], []
        self.accepted, self.closed, self.available = False, False, True
    def ready(self):
        self.trace.append('LISTENER')
        return self.available
    def accept(self):
        if not self.accepted:
            self.accepted = True
            return self.observation
    def identity(self): return self.observation
    def poll(self, limit):
        events, self.events = self.events[:limit], self.events[limit:]
        return events
    def send(self, raw): self.sent.append(raw)
    def close(self): self.closed = True
    def enqueue(self, request): self.events.extend([('data', frame(request)), ('end', b'')])


class Driver:
    def __init__(self, trace):
        self.trace = trace
        self.work = Work()
        self.reconciled = True
        self.admission = 'CLOSED'
    def reconcile(self):
        self.trace.append('RECONCILE')
        return self.reconciled
    def validate_config(self, config): return True
    def establish_admission(self):
        self.trace.append('ADMISSION')
        return self.admission
    def deadlines(self): self.trace.append('DEADLINE')
    def control(self): self.trace.append('CONTROL')
    def heartbeat(self): self.trace.append('HEARTBEAT')
    def disconnect(self): self.trace.append('DISCONNECT')
    def peer_alive(self): self.trace.append('PEER_ALIVE')


class Adapters:
    def __init__(self, component, registry_path=None):
        self.cfg, self.trace, self.clock = configuration(component), [], 0
        self.component, self.registry_path = component, registry_path
        self.driver = Driver(self.trace)
        self.transport = Transport(self.cfg, self.trace)
    def load_config(self, path):
        self.trace.append('CONFIG')
        return deepcopy(self.cfg)
    def identity(self):
        uid = 3000 if self.component == 'controller' else 0
        return PeerIdentity(uid, uid, 99)
    def boot_id(self): return BOOT
    def verify_manifest(self): return 'a'*64
    def capabilities(self): return ()
    def open_registry(self, path):
        self.trace.append('REGISTRY')
        self.registry = Registry(self.registry_path)
        return self.registry
    def compose_controller(self, registry, config): return self.driver
    def compose_supervisor(self, config): return self.driver
    def listener(self, config): return self.transport
    def now(self): return self.clock
    def notify(self, value): self.trace.append(value)


class ControllerStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / 'control.sqlite3'
        with Registry.initialize(cls.path, Path(cls.temp.name)/'history.git', operation_id=str(uuid4())) as r:
            migrate_v2(r)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self): self.a = Adapters('controller', self.path)
    def test_success_ready_after_all_startup_stages(self):
        service = controller_entry.start(adapters=self.a)
        self.addCleanup(service.close)
        self.assertEqual(self.a.trace, ['CONFIG', 'REGISTRY', 'RECONCILE', 'LISTENER',
                                       'ADMISSION', 'DEADLINE', 'CONTROL', 'READY=1'])
    def test_missing_registry_never_initializes(self):
        self.a.registry_path = Path(self.temp.name)/'missing.sqlite3'
        with self.assertRaises(ValidationError): controller_entry.start(adapters=self.a)
        self.assertFalse(self.a.registry_path.exists())
        self.assertNotIn('READY=1', self.a.trace)
    def test_invalid_registry_prevents_ready(self):
        path = Path(self.temp.name)/'invalid.sqlite3'
        path.write_bytes(b'not a database')
        self.a.registry_path = path
        with self.assertRaises(Exception): controller_entry.start(adapters=self.a)
        self.assertNotIn('READY=1', self.a.trace)
    def test_reconciliation_failure_prevents_ready(self):
        self.a.driver.reconciled = False
        with self.assertRaises(AuthorityError): controller_entry.start(adapters=self.a)
        self.assertNotIn('READY=1', self.a.trace)
        self.assertIn('DISCONNECT', self.a.trace)
    def test_listener_failure_prevents_ready(self):
        self.a.transport.available = False
        with self.assertRaises(AuthorityError): controller_entry.start(adapters=self.a)
        self.assertTrue(self.a.transport.closed)
        self.assertNotIn('READY=1', self.a.trace)
    def test_unknown_admission_and_capabilities_rejected(self):
        self.a.driver.admission = None
        with self.assertRaises(AuthorityError): controller_entry.start(adapters=self.a)
        self.a.driver.admission = 'CLOSED'
        self.a.capabilities = lambda: ('CAP_SETUID',)
        with self.assertRaises(AuthorityError): controller_entry.start(adapters=self.a)
        self.assertNotIn('READY=1', self.a.trace)
    def test_fixed_path_cannot_select_application_database(self):
        with self.assertRaises(AuthorityError):
            controller_entry.start(adapters=self.a, config_path='/tmp/arbitrary.json')
        with self.assertRaises(AuthorityError): controller_entry.open_existing_registry('/tmp/application.sqlite3')


class SupervisorStartupTests(unittest.TestCase):
    def setUp(self): self.a = Adapters('supervisor')
    def test_success_has_no_registry_dependency_and_ordered_ready(self):
        self.a.open_registry = lambda _: self.fail('Supervisor accessed controller DB')
        loop = supervisor_entry.start(adapters=self.a)
        self.addCleanup(loop.shutdown)
        self.assertNotIn('REGISTRY', self.a.trace)
        self.assertEqual(self.a.trace[-3:], ['DEADLINE', 'CONTROL', 'READY=1'])
        self.assertFalse(hasattr(loop, 'registry'))
    def test_configuration_unknown_unapproved_wrong_manifest_and_db_rejected(self):
        for change in ({'approved':False}, {'unexpected':True}, {'manifest_digest':'b'*64},
                       {'registry_path':'/var/lib/bonup-agent-control/control.sqlite3'}):
            with self.subTest(change=change):
                self.a.cfg = dict(configuration(), **change)
                with self.assertRaises((AuthorityError, ValidationError)): supervisor_entry.start(adapters=self.a)
                self.assertNotIn('READY=1', self.a.trace)
    def test_reconciliation_failure(self):
        self.a.driver.reconciled = False
        with self.assertRaises(AuthorityError): supervisor_entry.start(adapters=self.a)
        self.assertNotIn('READY=1', self.a.trace)
    def test_endpoint_failure(self):
        self.a.transport.available = False
        with self.assertRaises(AuthorityError): supervisor_entry.start(adapters=self.a)
        self.assertNotIn('READY=1', self.a.trace)
        self.assertTrue(self.a.transport.closed)
    def test_existing_supervisor_endpoint_is_composed(self):
        backend = SyntheticProcessBackend(ProcessIdentity(BOOT,99,123))
        endpoint = SupervisorEndpoint((),backend,generation=GEN,boot_id=BOOT,elapsed=self.a.now)
        driver = supervisor_entry.SupervisorDriver(endpoint,Work(),heartbeat=lambda:None,control=lambda:None)
        self.a.compose_supervisor = lambda config:driver
        loop=supervisor_entry.start(adapters=self.a)
        self.addCleanup(loop.shutdown)
        self.assertTrue(endpoint.ready)
        self.a.clock=.5
        self.a.transport.enqueue(message('HEARTBEAT',str(uuid4()),GEN,BOOT,dict(ready=True)))
        loop.step()
        self.assertEqual(endpoint.last_heartbeat,.5)
        loop.shutdown()
        self.assertFalse(endpoint.ready)


class PeerTests(unittest.TestCase):
    def setUp(self):
        self.a = Adapters('supervisor')
        self.config = ServiceConfig.parse(self.a.cfg, component='supervisor', identity=self.a.identity(),
                                         boot_id=BOOT, manifest_digest='a'*64)
    def test_valid_and_replayed_enrollment(self):
        auth = PeerAuthenticator(self.config.peer)
        auth.verify(*self.a.transport.observation, consume=True)
        with self.assertRaises(AuthorityError): auth.verify(*self.a.transport.observation, consume=True)
    def test_uid_pid_start_boot_and_generation_rejected(self):
        peer, proc, handshake = self.a.transport.observation
        changes = [(PeerIdentity(1000,1000,42),proc,handshake), (PeerIdentity(3000,3000,43),proc,handshake),
            (peer,ProcessIdentity(BOOT,42,124),handshake), (peer,ProcessIdentity(str(uuid4()),42,123),handshake),
            (peer,proc,dict(handshake,generation=str(uuid4()))), (peer,proc,dict(handshake,endpoint='worker')),
            (peer,proc,dict(handshake,uid=3000)), (dict(uid=3000),proc,handshake)]
        for observation in changes:
            with self.subTest(observation=observation), self.assertRaises((AuthorityError,ValidationError)):
                PeerAuthenticator(self.config.peer).verify(*observation, consume=True)
    def test_supervisor_evidence_peer_requires_root_and_exact_process(self):
        a = Adapters('controller')
        config = ServiceConfig.parse(a.cfg, component='controller', identity=a.identity(), boot_id=BOOT, manifest_digest='a'*64)
        auth = PeerAuthenticator(config.peer)
        auth.verify(*a.transport.observation, consume=True)
        peer, process, handshake = a.transport.observation
        with self.assertRaises(AuthorityError): auth.verify(PeerIdentity(3000,3000,42),process,handshake)


class ExistingControllerTests(unittest.TestCase):
    def test_existing_controller_reconciles_durable_state_before_ready(self):
        import test_supervisor as fixtures
        from tools.agent_control.composition import ControllerRuntime, RemoteProcessBackend, OfflineTransport
        fixtures.RuntimeTests.setUp(self)
        a=Adapters('controller')
        endpoint=SupervisorEndpoint((),self.backend,generation=PEER_GEN,boot_id=BOOT,
                                    elapsed=a.now,now=lambda:fixtures.NOW)
        remote=RemoteProcessBackend(OfflineTransport(endpoint),{},generation=PEER_GEN,boot_id=BOOT)
        authorization=SimpleNamespace(clock=lambda:fixtures.NOW,elapsed=a.now)
        controller=ControllerRuntime(self.runtime,authorization,remote,generation=PEER_GEN,boot_id=BOOT)
        driver=controller_entry.ControllerDriver(controller,Work(),heartbeat=lambda:None,deadlines=lambda:None)
        a.open_registry=lambda path:self.registry
        a.compose_controller=lambda registry,config:driver
        service=controller_entry.start(adapters=a)
        self.addCleanup(service.close)
        self.assertEqual(self.runtime.launch(self.launch_id)['state'],'TERMINAL')
        self.assertIn('READY=1',a.trace)
        self.assertTrue(driver.validate_config(service.loop.config))


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.a = Adapters('supervisor')
        self.loop = supervisor_entry.start(adapters=self.a)
        self.addCleanup(self.loop.shutdown)
    def request(self, action='RECONCILE', data=None):
        return message(action, str(uuid4()), GEN, BOOT, data or {})
    def test_valid_frame_queued_without_running_handler(self):
        request = self.request()
        self.a.transport.enqueue(request)
        self.loop.step()
        self.assertEqual(self.a.driver.work.requests, [request])
        self.assertIsNotNone(self.loop.pending)
    def test_partial_timeout_and_malformed_disconnect(self):
        self.a.transport.events = [('data', b'\0')]
        self.loop.step()
        self.a.clock = 1
        with self.assertRaises(AuthorityError): self.loop.step()
        self.assertTrue(self.a.transport.closed)
        self.assertEqual(self.a.driver.work.requests, [])
    def test_duplicate_unknown_fields_and_oversize_rejected(self):
        for raw in (b'{"version":1,"version":1}', b'{"extra":true}', b'\xff'):
            a = Adapters('supervisor')
            loop = supervisor_entry.start(adapters=a)
            a.transport.events = [('data', len(raw).to_bytes(4,'big')+raw), ('end',b'')]
            with self.assertRaises(ValidationError): loop.step()
            self.assertTrue(a.transport.closed)
        self.a.transport.events = [('data', (4097).to_bytes(4,'big'))]
        with self.assertRaises(ValidationError): self.loop.step()
    def test_slow_sender_and_pending_job_do_not_block_maintenance(self):
        self.a.transport.events = [('data',b'\0')]
        self.loop.step()
        self.a.clock = .3
        self.loop.step()
        self.assertEqual(self.a.trace.count('DEADLINE'), 3)
        self.assertEqual(self.a.trace.count('CONTROL'), 3)
        self.assertEqual(self.a.trace.count('HEARTBEAT'), 2)
        self.assertIn('WATCHDOG=1', self.a.trace)
    def test_heartbeat_processed_while_normal_job_pending(self):
        self.a.transport.enqueue(self.request())
        self.loop.step()
        self.a.transport.enqueue(self.request('HEARTBEAT',dict(ready=True)))
        self.a.clock = .5
        self.loop.step()
        self.assertEqual(len(self.a.driver.work.requests),1)
        self.assertEqual(self.loop.last_peer,.5)
        self.assertEqual(self.a.trace.count('CONTROL'),3)
    def test_replay_and_concurrent_work_fail_closed(self):
        request=self.request()
        self.a.transport.enqueue(request)
        self.loop.step()
        self.a.transport.enqueue(request)
        with self.assertRaises(AuthorityError): self.loop.step()
        self.assertTrue(self.a.driver.work.cancelled)
    def test_peer_reuse_and_disconnect_detected(self):
        self.loop.step()
        peer, proc, handshake = self.a.transport.observation
        self.a.transport.observation = (peer,ProcessIdentity(BOOT,42,124),handshake)
        with self.assertRaises(AuthorityError): self.loop.step()
        self.assertIn('DISCONNECT',self.a.trace)
    def test_disconnect_both_directions(self):
        for component in ('controller','supervisor'):
            a=Adapters(component)
            config=ServiceConfig.parse(a.cfg,component=component,identity=a.identity(),boot_id=BOOT,manifest_digest='a'*64)
            loop=ServiceLoop(config,a.transport,a.driver.work,now=a.now,deadlines=a.driver.deadlines,
                control=a.driver.control,heartbeat=a.driver.heartbeat,disconnect=a.driver.disconnect,notifier=a.notify)
            loop.activate()
            a.transport.events=[('disconnect',b'')]
            with self.assertRaises(AuthorityError):loop.step()
            self.assertIn('DISCONNECT',a.trace)
    def test_shutdown_idempotent_and_watchdog_only_after_ready(self):
        self.assertNotIn('WATCHDOG=1',self.a.trace)
        self.a.clock=.3
        self.loop.step()
        self.loop.shutdown(); self.loop.shutdown()
        self.assertEqual(self.a.trace.count('STOPPING=1'),1)
        self.assertLess(self.a.trace.index('READY=1'),self.a.trace.index('WATCHDOG=1'))
        with self.assertRaises(AuthorityError):self.loop.step()
    def test_stale_wire_generation_and_direction_denied(self):
        self.a.transport.enqueue(dict(self.request(),generation=str(uuid4())))
        with self.assertRaises(AuthorityError):self.loop.step()
    def test_completed_work_returns_bounded_correlated_evidence(self):
        request=self.request()
        self.a.transport.enqueue(request)
        self.loop.step()
        result=message('CLEANUP_EVIDENCE',request['launch_id'],GEN,BOOT,
                       dict(empty=True,exit_code=None),request_id=request['request_id'])
        self.a.driver.work.result=result
        self.loop.step()
        self.assertIsNone(self.loop.pending)
        self.assertEqual(self.a.transport.sent,[frame(result)])
    def test_wrong_result_correlation_shuts_down(self):
        request=self.request()
        self.a.transport.enqueue(request)
        self.loop.step()
        self.a.driver.work.result=message('CLEANUP_EVIDENCE',request['launch_id'],GEN,BOOT,
                                          dict(empty=True,exit_code=None))
        with self.assertRaises(AuthorityError):self.loop.step()
        self.assertEqual(self.a.transport.sent,[])
    def test_pending_work_does_not_block_cancellation_revocation_callback(self):
        self.a.transport.enqueue(self.request())
        self.loop.step()
        self.loop.control=self.a.driver.work.cancel
        self.loop.step()
        self.assertTrue(self.a.driver.work.cancelled)
        self.assertIsNotNone(self.loop.pending)
    def test_run_shutdown_is_deterministic_without_sleep(self):
        calls=[]
        self.loop.run(lambda:bool(calls),lambda timeout:calls.append(timeout))
        self.assertEqual(calls,[.05])
        self.assertEqual(self.a.trace.count('STOPPING=1'),1)
