"""Offline wire/sequencer tests. No installed services, root code or live cgroups."""
from dataclasses import replace
from datetime import timedelta
import struct
import socket
import unittest
from unittest.mock import patch

import test_supervisor as fixtures
from tools.agent_control.composition import (ApprovedPlan, SupervisorEndpoint,
    OfflineTransport, RemoteProcessBackend, ControllerRuntime, message)
from tools.agent_control.composition_protocol import FrameReader, frame
from tools.agent_control.serialization import canonical_json
from tools.agent_control.supervisor import Supervisor
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control.execution import Controller, Enrollment
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.model_client import FakeModelClient
from tools.agent_control.protocol import Operation
from tools.agent_control.runtime import DurableExecutionStore
from tools.agent_control.release_gate import ExpectedRelease, FixedPayload, ReleaseGate, release_frame
from tools.agent_control.integration_policy import IntegrationPolicy, validate_capabilities


class FramingTests(unittest.TestCase):
    def setUp(self):
        self.request = message('HEARTBEAT', fixtures.uid(), fixtures.uid(), fixtures.U, dict(ready=True))

    def test_partial_frame_does_not_dispatch_until_eof(self):
        data = frame(self.request)
        reader = FrameReader(now=0)
        for byte in data:
            self.assertIsNone(reader.feed(bytes([byte]), now=.1))
        self.assertEqual(reader.feed(b'', now=.2, eof=True), self.request)
        with self.assertRaises(AuthorityError):
            reader.feed(b'', now=.2, eof=True)

    def test_partial_and_empty_eof_denied(self):
        for raw in (b'', b'\0', frame(self.request)[:-1]):
            with self.subTest(raw=raw[:4]), self.assertRaises(ValidationError):
                FrameReader(now=0).feed(raw, now=0, eof=True)

    def test_extra_frame_denied(self):
        with self.assertRaises(ValidationError):
            FrameReader(now=0).feed(frame(self.request) * 2, now=0, eof=True)

    def test_unknown_fields_and_duplicate_keys_denied(self):
        raw = canonical_json(self.request).encode()
        for changed in (raw[:-1] + b',"uid":0}', raw[:-1] + b',"version":1}'):
            with self.subTest(raw=changed), self.assertRaises(ValidationError):
                FrameReader(now=0).feed(struct.pack('!I', len(changed)) + changed, now=0, eof=True)

    def test_oversize_and_invalid_utf8_denied(self):
        for data in (struct.pack('!I', 4097), b'\0\0\0\1\xff'):
            with self.assertRaises(ValidationError):
                FrameReader(now=0).feed(data, now=0, eof=True)

    def test_slow_sender_timeout_consumes_channel(self):
        reader = FrameReader(now=0)
        reader.feed(b'\0', now=.5)
        with self.assertRaises(AuthorityError):
            reader.feed(b'', now=1)
        with self.assertRaises(AuthorityError):
            reader.feed(frame(self.request), now=.5, eof=True)


class CompositionTests(unittest.TestCase):
    def setUp(self):
        fixtures.RuntimeTests.setUp(self)
        self.plan = ApprovedPlan(fixtures.uid(), self.execution_id, self.record,
                                 (1, 2, 3001, 3001), self.profile_id, self.backend.process)
        self.endpoint = SupervisorEndpoint((self.plan,), self.backend, generation=self.generation,
            boot_id=self.boot, now=lambda: self.now, elapsed=lambda: self.elapsed)
        self.transport = OfflineTransport(self.endpoint)
        self.remote = RemoteProcessBackend(self.transport, {self.execution_id: self.plan.plan_id},
                                           generation=self.generation, boot_id=self.boot)
        self.assertTrue(self.remote.reconcile_unknown())
        self.sequencer = Supervisor(self.runtime, self.remote, generation=self.generation, boot_id=self.boot,
                                   authorize=lambda *_: self.record, now=lambda: self.now, elapsed=lambda: self.elapsed)

    def test_durable_prepare_release_stop_lifecycle(self):
        self.assertEqual(self.sequencer.prepare(self.launch_id)['state'], 'PREPARED')
        self.assertEqual(self.backend.releases, [])
        self.assertEqual(self.sequencer.release(self.launch_id)['state'], 'RUNNING')
        self.assertEqual(self.backend.releases, [self.launch_id])
        self.assertEqual(self.sequencer.stop(self.launch_id, 'CANCELLED')['state'], 'TERMINAL')
        self.assertEqual(self.backend.children, {})
        self.assertFalse(hasattr(self.endpoint, 'runtime'))
        self.assertFalse(hasattr(self.endpoint, 'db'))

    def test_wire_never_contains_privileged_configuration(self):
        self.sequencer.prepare(self.launch_id)
        for request in self.transport.sent:
            self.assertFalse({'uid', 'gid', 'argv', 'environment', 'mounts', 'paths', 'capabilities'} & request['data'].keys())
        wire = canonical_json(self.transport.sent)
        self.assertNotIn('/usr/bin/true', wire)
        self.assertNotIn('/home/bonup', wire)

    def test_different_installed_payload_denied(self):
        self.record = replace(self.record, argv=('/usr/bin/false',))
        with self.assertRaises(AuthorityError):
            self.sequencer.prepare(self.launch_id)
        self.assertEqual(self.backend.releases, [])

    def test_authority_change_after_prepared_prevents_release(self):
        self.sequencer.prepare(self.launch_id)
        self.runtime.revoke(self.execution_id, 0, context=fixtures.FOUNDER)
        with self.assertRaises(AuthorityError):
            self.sequencer.release(self.launch_id)
        self.assertEqual(self.backend.releases, [])
        self.assertEqual(self.runtime.launch(self.launch_id)['state'], 'TERMINAL')

    def test_prepare_failure_stops_without_release(self):
        self.backend.fail_setup = True
        with self.assertRaises(AuthorityError):
            self.sequencer.prepare(self.launch_id)
        self.assertEqual(self.backend.releases, [])
        self.assertEqual(self.runtime.launch(self.launch_id)['state'], 'TERMINAL')

    def test_lost_release_acknowledgement_never_replays(self):
        self.sequencer.prepare(self.launch_id)
        self.backend.acknowledge = False
        with self.assertRaises(AuthorityError):
            self.sequencer.release(self.launch_id)
        with self.assertRaises(AuthorityError):
            self.sequencer.release(self.launch_id)
        self.assertEqual(self.backend.releases, [self.launch_id])
        self.assertEqual(self.backend.children, {})

    def test_release_delivery_without_exec_proof_never_becomes_running(self):
        self.sequencer.prepare(self.launch_id)
        with patch.object(self.backend,'release',return_value=None):
            with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)
        self.assertEqual(self.runtime.launch(self.launch_id)['state'],'TERMINAL')
        self.assertEqual(self.backend.children,{})
        with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)

    def test_ambiguous_delivery_with_survivors_retains_cleanup_reservation(self):
        self.sequencer.prepare(self.launch_id)
        self.backend.cleanup_known=False
        with patch.object(self.backend,'release',return_value=None):
            with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)
        self.assertEqual(self.runtime.launch(self.launch_id)['state'],'STOPPING')
        self.assertTrue(self.backend.children)

    def test_cleanup_uncertainty_retains_stopping(self):
        self.sequencer.prepare(self.launch_id)
        self.sequencer.release(self.launch_id)
        self.backend.cleanup_known = False
        self.assertEqual(self.sequencer.stop(self.launch_id, 'CANCELLED')['state'], 'STOPPING')
        self.backend.cleanup_known = True
        self.assertEqual(self.sequencer.poll(self.launch_id)['state'], 'TERMINAL')

    def test_deadline_stops_independently_of_partial_ipc(self):
        self.record = replace(self.record, timeout_seconds=.2)
        self.sequencer.prepare(self.launch_id)
        self.sequencer.release(self.launch_id)
        reader = FrameReader(now=0)
        self.assertIsNone(reader.feed(b'\0', now=.1))
        self.elapsed = .2
        self.endpoint.tick()
        self.assertEqual(self.backend.children, {})
        self.assertEqual(self.sequencer.poll(self.launch_id)['state'], 'TERMINAL')

    def test_controller_disconnect_stops_root_endpoint(self):
        self.sequencer.prepare(self.launch_id)
        self.sequencer.release(self.launch_id)
        self.transport.disconnect()
        self.assertFalse(self.endpoint.ready)
        self.assertEqual(self.backend.children, {})
        with self.assertRaises(AuthorityError):
            self.sequencer.poll(self.launch_id, controller_alive=False)
        self.assertEqual(self.runtime.launch(self.launch_id)['state'], 'STOPPING')

    def test_heartbeat_stall_stops_without_controller_poll(self):
        self.sequencer.prepare(self.launch_id)
        self.sequencer.release(self.launch_id)
        self.elapsed = 2
        self.endpoint.tick()
        self.assertFalse(self.endpoint.ready)
        self.assertEqual(self.backend.children, {})

    def test_request_replay_and_stale_generation_denied(self):
        request = message('HEARTBEAT', self.launch_id, self.generation, self.boot, dict(ready=True))
        self.endpoint.handle(request)
        with self.assertRaises(AuthorityError):
            self.endpoint.handle(request)
        request = dict(request, generation=fixtures.uid(), request_id=fixtures.uid())
        with self.assertRaises(AuthorityError):
            self.endpoint.handle(request)

    def test_running_evidence_substitution_triggers_stop(self):
        self.sequencer.prepare(self.launch_id)
        original = self.transport.exchange
        def substitute(request):
            response = original(request)
            if response['action'] == 'RUNNING_EVIDENCE':
                response['data']['process']['start_ticks'] += 1
            return response
        with patch.object(self.transport, 'exchange', side_effect=substitute):
            with self.assertRaises(AuthorityError):
                self.sequencer.release(self.launch_id)
        self.assertEqual(self.backend.children, {})
        self.assertEqual(self.runtime.launch(self.launch_id)['state'], 'TERMINAL')

    def test_expiry_during_preparation_prevents_release(self):
        def expire():
            self.elapsed = 31
            self.now += timedelta(seconds=31)
        self.backend.before_ready = expire
        with self.assertRaises(AuthorityError):
            self.sequencer.prepare(self.launch_id)
        self.assertEqual(self.backend.releases, [])

    def test_release_requires_durable_release_pending(self):
        self.sequencer.prepare(self.launch_id)
        original = self.backend.release
        def verify(launch, record):
            self.assertEqual(self.runtime.launch(self.launch_id)['state'], 'RELEASE_PENDING')
            return original(launch, record)
        with patch.object(self.backend, 'release', side_effect=verify):
            self.sequencer.release(self.launch_id)

    def test_exclusive_admission_checks_all_unresolved_launches(self):
        with self.assertRaises(AuthorityError):
            self.runtime.register_launch(self.execution_id, fixtures.uid(), 'b'*64, self.generation,
                self.boot, dict(workspace=[1,2,3001,3001], repository=None, profile_digest=self.profile_id),
                exclusive=True)

    def test_proposal_through_real_authorizer_registry_and_release_gate(self):
        # The filesystem/process bootstrap is synthetic. Authorization, durable
        # transitions, framing and the real one-use release parser are not mocked.
        self.supervisor.stop(self.launch_id, 'CANCELLED')
        class SyntheticRoot:
            path = '/synthetic/work'
            identity = (1, 2, 3001, 3001)
            def verify(self):
                pass
        store = DurableExecutionStore(self.runtime, {self.execution_id: SyntheticRoot()}, {})
        caller = ProcessIdentity(self.boot, 42001, 124)
        enrollment = Enrollment(PeerIdentity(3000, 3000, caller.pid), caller, self.execution_id)
        authorization = Controller(store, (enrollment,), None, lambda event: None,
            clock=lambda: self.now, elapsed=lambda: self.elapsed,
            process_reader=lambda pid: {42000: self.backend.process, 42001: caller}[pid])
        raw = canonical_json(dict(version=1, request_id=fixtures.uid(), execution_id=self.execution_id,
            operation='RUN_TEST', arguments=dict(command_id='true'))).encode()
        proposal = FakeModelClient(raw).propose({}, {Operation.RUN_TEST})
        record = authorization._check(enrollment, proposal)
        plan = replace(self.plan, record=record)
        endpoint = SupervisorEndpoint((plan,), self.backend, generation=self.generation, boot_id=self.boot,
                                      now=lambda: self.now, elapsed=lambda: self.elapsed)
        remote = RemoteProcessBackend(OfflineTransport(endpoint), {self.execution_id: plan.plan_id},
                                      generation=self.generation, boot_id=self.boot)
        controller = ControllerRuntime(self.runtime, authorization, remote,
                                       generation=self.generation, boot_id=self.boot)
        controller.reconcile()
        launch_id = controller.register(canonical_json(proposal.to_dict()).encode(), enrollment)
        self.assertEqual(self.runtime.launch(launch_id)['state'], 'REGISTERED')
        controller.prepare(launch_id)
        original_release = self.backend.release
        gates = []
        def gated_release(launch, prepared):
            sender, receiver = socket.socketpair()
            self.addCleanup(sender.close)
            self.addCleanup(receiver.close)
            expected = ExpectedRelease(launch_id, self.generation, prepared.authorization_digest,
                fixtures.uid(), prepared.expires_at, PeerIdentity.current(),
                int(prepared.elapsed_deadline * 1e9))
            gate = ReleaseGate(expected, FixedPayload(prepared.argv, prepared.environment))
            gates.append(gate)
            sender.sendall(release_frame(expected))
            sender.shutdown(socket.SHUT_WR)
            gate.authorize(receiver, now=lambda: self.now, elapsed_ns=lambda: int(self.elapsed * 1e9))
            return original_release(launch, prepared)
        with patch.object(self.backend, 'release', side_effect=gated_release):
            self.assertEqual(controller.release(launch_id)['state'], 'RUNNING')
        self.assertTrue(gates[0].used)
        self.assertEqual(controller.stop(launch_id)['state'], 'TERMINAL')

    def test_db_failure_before_release_never_reaches_root_release(self):
        self.sequencer.prepare(self.launch_id)
        original = self.runtime.transition
        def fail(launch_id, revision, target, **kw):
            if target == 'RELEASE_PENDING':
                raise AuthorityError('Synthetic database failure')
            return original(launch_id, revision, target, **kw)
        with patch.object(self.runtime, 'transition', side_effect=fail):
            with self.assertRaises(AuthorityError):
                self.sequencer.release(self.launch_id)
        self.assertEqual(self.backend.releases, [])

    def test_gate_eof_failure_stops_and_cannot_retry(self):
        self.sequencer.prepare(self.launch_id)
        def eof(launch, record):
            sender, receiver = socket.socketpair()
            self.addCleanup(receiver.close)
            expected = ExpectedRelease(self.launch_id, self.generation, record.authorization_digest,
                fixtures.uid(), record.expires_at, PeerIdentity.current(), int(record.elapsed_deadline * 1e9))
            sender.close()
            ReleaseGate(expected, FixedPayload(record.argv, record.environment)).authorize(
                receiver, now=lambda: self.now, elapsed_ns=lambda: int(self.elapsed * 1e9))
        with patch.object(self.backend, 'release', side_effect=eof):
            with self.assertRaises(AuthorityError):
                self.sequencer.release(self.launch_id)
        self.assertEqual(self.backend.releases, [])
        self.assertEqual(self.runtime.launch(self.launch_id)['state'], 'TERMINAL')


class IntegrationPolicyTests(unittest.TestCase):
    def test_initial_limits_are_exact_and_immutable(self):
        policy = IntegrationPolicy()
        self.assertEqual(policy.workspace_bytes, 128 * 1024 * 1024)
        self.assertEqual(policy.workspace_inodes, 16384)
        self.assertEqual(policy.storage_mode, 'EPHEMERAL_TMPFS_WORKSPACE')
        self.assertEqual(len(policy.policy_digest), 64)
        for change in (dict(memory_bytes=2**30), dict(global_launches=2), dict(durable_workspace=True),
                       dict(supervisor_mounts_workspace=True), dict(version=True)):
            with self.assertRaises(ValidationError):
                IntegrationPolicy(**change)

    def test_capabilities_are_component_specific(self):
        validate_capabilities('supervisor', ['CAP_SETUID', 'CAP_SETGID', 'CAP_KILL', 'CAP_DAC_READ_SEARCH'])
        for component in ('controller', 'worker'):
            validate_capabilities(component, [])
            with self.assertRaises(ValidationError):
                validate_capabilities(component, ['CAP_DAC_READ_SEARCH'])
        for forbidden in ('CAP_SYS_ADMIN', 'CAP_DAC_OVERRIDE', 'CAP_NET_ADMIN'):
            with self.assertRaises(ValidationError):
                validate_capabilities('supervisor', ['CAP_SETUID', 'CAP_SETGID', 'CAP_KILL', forbidden])
