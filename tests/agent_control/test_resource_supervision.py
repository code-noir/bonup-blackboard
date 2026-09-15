"""Block 3 deterministic contracts; no UID changes, mounts, cgroups or live API."""
from dataclasses import asdict, replace
from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_supervisor as fixtures
import test_composition as composition_fixtures
import test_boundary_hardening as lease_fixtures
import test_service_runtime as service_fixtures
from fixtures import FOUNDER
from tools.agent_control.resource_supervision import (authority_deadline, DeadlineScheduler,
    OutputCollector, ResourceBackend, build_plan)
from tools.agent_control.integration_policy import IntegrationPolicy
from tools.agent_control.serialization import digest
from tools.agent_control.supervisor import ExecutionDeadline
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control.composition_protocol import frame
from tools.agent_control.composition import message
from tools.agent_control.confinement import ConfinementProfile
from tools.agent_control.identity import WorkerIdentity, ProcessIdentity
from tools.agent_control.execution import LaunchRecord
from tools.agent_control.protocol import Operation
from tools.agent_control.types import Role


class ResourceContractTests(unittest.TestCase):
    def setUp(self):
        self.now=fixtures.NOW;self.elapsed=0
        self.scheduler=DeadlineScheduler(lambda:self.now,lambda:self.elapsed)
        self.policy=IntegrationPolicy()

    def deadline(self, grant=40, leases=(), operation=40, **kw):
        stamp=lambda n:(fixtures.NOW+timedelta(seconds=n)).isoformat()
        return authority_deadline(stamp(grant),tuple(stamp(n) for n in leases),now=self.now,
            elapsed=self.elapsed,operation_seconds=operation,**kw)

    def test_complete_closed_resource_profile(self):
        data=asdict(self.policy)
        self.assertEqual(IntegrationPolicy.parse(data),self.policy)
        for key in data:
            altered=dict(data)
            altered[key]=not data[key] if type(data[key]) is bool else (data[key]+1 if type(data[key]) is int else data[key]+'x')
            self.assertNotEqual(digest(altered),self.policy.policy_digest)
            with self.assertRaises(ValidationError):IntegrationPolicy.parse(altered)
        with self.assertRaises(ValidationError):IntegrationPolicy.parse(dict(data,resize=True))

    def test_model_resource_and_identity_overrides_rejected(self):
        for field,value in (('memory_bytes',2**40),('processes',10000),('uid',0),('resize',True)):
            request=message('STATUS_LAUNCH',fixtures.uid(),fixtures.uid(),fixtures.U,{})
            request['data'][field]=value
            with self.assertRaises(ValidationError):frame(request)

    def test_grant_earliest(self):self.assertEqual(self.deadline(grant=2).elapsed_deadline,2)
    def test_lease_earliest(self):self.assertEqual(self.deadline(leases=(2,)).elapsed_deadline,2)
    def test_multiple_leases_earliest(self):self.assertEqual(self.deadline(leases=(8,2,6)).elapsed_deadline,2)
    def test_profile_earliest(self):self.assertEqual(self.deadline().elapsed_deadline,30)
    def test_operation_earliest(self):self.assertEqual(self.deadline(operation=1).elapsed_deadline,1)
    def test_operation_absolute_deadline(self):self.assertEqual(self.deadline(operation_elapsed=.4).elapsed_deadline,.4)
    def test_subsecond(self):self.assertEqual(self.deadline(leases=(.2,)).elapsed_deadline,.2)

    def test_zero_negative_nonfinite_denied(self):
        for n in (0,-1,float('nan'),float('inf')):
            with self.assertRaises((AuthorityError,ValidationError)):self.deadline(operation=n)

    def test_rollback_and_replacement_cannot_extend(self):
        old=self.deadline(leases=(2,))
        self.elapsed=1;self.now-=timedelta(days=1)
        self.assertEqual(self.deadline(leases=(100,),original=old).elapsed_deadline,2)
        self.elapsed=2
        with self.assertRaises(AuthorityError):self.deadline(leases=(100,),original=old)

    def test_independent_timer_ignores_pending_request_and_output(self):
        stopped=[];key=fixtures.uid()
        self.scheduler.arm(key,self.deadline(leases=(.2,)),lambda:stopped.append(key))
        pending_request=object()  # No handler invocation or completion is needed.
        output=OutputCollector()
        for _ in range(8):output.feed('stdout',b'x'*16384)
        self.elapsed=.2;self.now-=timedelta(days=1)
        self.scheduler.service()
        self.assertEqual(stopped,[key]);self.assertIsNotNone(pending_request)
        with self.assertRaises(AuthorityError):self.scheduler.arm(key,self.deadline(),lambda:None)

    def test_deadline_can_only_shorten(self):
        key=fixtures.uid();self.scheduler.arm(key,self.deadline(),lambda:None)
        self.scheduler.shorten(key,self.deadline(operation=1))
        with self.assertRaises(AuthorityError):self.scheduler.shorten(key,self.deadline(operation=2))

    def test_reconciliation_consumes_old_timers_without_replay(self):
        backend=ResourceBackend(ProcessIdentity(fixtures.U,42000,123),self.scheduler)
        key=fixtures.uid()
        backend.arm_deadline(key,self.deadline())
        backend.children[key]={'alive':True,'descendants':2}
        backend.cleanup_known=False
        self.assertFalse(backend.reconcile_unknown())
        self.assertTrue(backend.children)
        backend.cleanup_known=True
        self.assertTrue(backend.reconcile_unknown())
        self.assertFalse(backend.children);self.assertFalse(self.scheduler.entries)
        with self.assertRaises(AuthorityError):backend.arm_deadline(key,self.deadline())

    def test_stop_delivery_failure_observable_and_not_revived(self):
        key=fixtures.uid()
        self.scheduler.arm(key,self.deadline(operation=1),lambda:(_ for _ in ()).throw(AuthorityError('delivery')))
        self.elapsed=1
        with self.assertRaises(AuthorityError):self.scheduler.service()
        self.elapsed=0;self.now-=timedelta(days=1)
        with self.assertRaises(AuthorityError):self.scheduler.service()

    def test_stdout_bounded(self):self.check_output('stdout')
    def test_stderr_bounded(self):self.check_output('stderr')
    def test_tighter_authorized_output_bound_preserved(self):
        output=OutputCollector(limit=2)
        output.feed('stdout',b'longer')
        self.assertEqual(bytes(output.buffers['stdout']),b'lo')
        self.assertTrue(output.evidence()['stdout']['truncated'])
        with self.assertRaises(ValidationError):OutputCollector(limit=65537)
    def check_output(self, stream):
        collector=OutputCollector()
        for _ in range(20):collector.feed(stream,b'x'*16384)
        self.assertEqual(len(collector.buffers[stream]),65536)
        self.assertEqual(collector.evidence()[stream],dict(retained=65536,truncated=True))
        other='stderr' if stream=='stdout' else 'stdout'
        self.assertEqual(collector.evidence()[other],dict(retained=0,truncated=False))
        with self.assertRaises(ValidationError):collector.feed(stream,b'x'*16385)

    def test_uid_cgroup_rlimit_gate_and_storage_plan(self):
        profile=ConfinementProfile()
        worker=WorkerIdentity('FE-01',Role.FRONTEND_ENGINEERING,'bonup-fe01',3002,3002)
        record=LaunchRecord(Operation.RUN_TEST,('/usr/bin/true',),'/work',profile.environment(),30,
            65536,profile.profile_digest,worker,'{}','b'*64,fixtures.EXPIRY)
        handle=SimpleNamespace(pass_fds=(10,),mapping=SimpleNamespace(profile=profile,object_identity=(1,2,3002,3002)),
            argv=lambda launch,gate:('/usr/bin/bwrap','--ro-bind-fd','10','/work/source','--',*gate.argv))
        launch=dict(launch_id=fixtures.uid(),supervisor_generation=fixtures.uid(),boot_id=fixtures.U)
        plan=build_plan(launch,record,handle,config_fd=11,release_fd=12)
        self.assertEqual(plan.worker,(3002,3002,(),(),True))
        self.assertEqual(dict(plan.cgroup_values),{'memory.max':'268435456','memory.swap.max':'0',
            'pids.max':'32','cpu.max':'100000 100000'})
        self.assertEqual(dict(plan.rlimits),{'NOFILE':256,'FSIZE':16777216,'CORE':0,'CPU':30})
        self.assertIn('/usr/lib/bonup-agent-control/gate_entry.py',plan.bwrap_argv)
        self.assertNotIn('--block-fd',plan.bwrap_argv)
        self.assertEqual(plan.bwrap_argv[0],'/usr/bin/bwrap')
        self.assertEqual(plan.fixed_payload.argv,record.argv)
        self.assertIn('EPHEMERAL_TMPFS_WORKSPACE',plan.resource_json)
        self.assertNotIn('CAP_SYS_ADMIN',plan.resource_json)
        self.assertNotEqual(plan.cgroup,build_plan(dict(launch,launch_id=fixtures.uid()),record,handle,
            config_fd=11,release_fd=12).cgroup)
        with self.assertRaises(AuthorityError):build_plan(launch,replace(record,worker=replace(worker,uid=4000)),handle,config_fd=11,release_fd=12)
        with self.assertRaises(TypeError):build_plan(launch,record,handle,config_fd=11,release_fd=12,uid=0)
        smaller=replace(profile,memory_bytes=128*1024*1024)
        handle.mapping.profile=smaller
        with self.assertRaises(AuthorityError):build_plan(launch,replace(record,profile_digest=smaller.profile_digest),handle,config_fd=11,release_fd=12)


class ResourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        composition_fixtures.CompositionTests.setUp(self)
        self.scheduler=DeadlineScheduler(lambda:self.now,lambda:self.elapsed)
        self.backend=ResourceBackend(self.backend.process,self.scheduler)
        self.endpoint.backend=self.backend

    def running(self):
        self.sequencer.prepare(self.launch_id);self.sequencer.release(self.launch_id)

    def test_normal_exit_waits_for_descendants_and_carries_output(self):
        self.running();row=self.runtime.launch(self.launch_id)
        self.backend.output[self.launch_id].feed('stderr',b'synthetic')
        self.backend.observe_exit(row,self.backend.process,7)
        self.backend.cleanup_known=False
        self.assertEqual(self.sequencer.poll(self.launch_id)['state'],'STOPPING')
        self.assertEqual(self.remote.results[self.launch_id]['stderr']['retained'],9)
        self.backend.cleanup_known=True
        result=self.sequencer.poll(self.launch_id)
        self.assertEqual(result['state'],'TERMINAL');self.assertEqual(result['exit_code'],7)

    def test_independent_expiry_requires_cleanup_and_blocks_reuse(self):
        self.running();self.backend.cleanup_known=False
        self.elapsed=30;self.now-=timedelta(days=1)
        self.scheduler.service()
        self.assertIn(self.launch_id,self.backend.stop_requested)
        self.assertEqual(self.sequencer.poll(self.launch_id)['state'],'STOPPING')
        with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)

    def test_revocation_preparing(self):
        self.backend.before_ready=lambda:self.runtime.revoke(self.execution_id,0,context=FOUNDER)
        with self.assertRaises(AuthorityError):self.sequencer.prepare(self.launch_id)
        self.assertFalse(self.backend.releases)

    def test_revocation_prepared(self):
        self.sequencer.prepare(self.launch_id)
        self.runtime.revoke(self.execution_id,0,context=FOUNDER)
        with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)
        self.assertFalse(self.backend.releases)

    def test_revocation_release_pending(self):
        self.sequencer.prepare(self.launch_id)
        original=self.runtime.transition
        def transition(*args,**kwargs):
            row=original(*args,**kwargs)
            if row['state']=='RELEASE_PENDING':self.runtime.revoke(self.execution_id,0,context=FOUNDER)
            return row
        with patch.object(self.runtime,'transition',side_effect=transition):
            with self.assertRaises(AuthorityError):self.sequencer.release(self.launch_id)
        self.assertFalse(self.backend.releases)

    def test_revocation_running(self):
        self.running();self.runtime.revoke(self.execution_id,0,context=FOUNDER)
        self.assertEqual(self.sequencer.poll(self.launch_id)['reason'],'REVOKED')

    def test_cancel_running(self):
        self.running()
        self.assertEqual(self.sequencer.poll(self.launch_id,cancelled=True)['reason'],'CANCELLED')

    def test_controller_crash(self):
        self.running();self.transport.disconnect()
        self.assertFalse(self.backend.children)
        self.assertEqual(self.backend.releases,[self.launch_id])

    def test_supervisor_crash_uncertain_cleanup(self):
        self.running();self.backend.cleanup_known=False
        self.endpoint.disconnect()
        self.assertEqual(self.endpoint.launches[self.launch_id]['state'],'STOPPING')
        self.assertFalse(self.remote.reconcile_unknown())
        self.assertEqual(self.backend.releases,[self.launch_id])

    def test_stale_process_exit_evidence(self):
        self.running();row=self.runtime.launch(self.launch_id)
        with self.assertRaises(AuthorityError):self.backend.observe_exit(row,replace(self.backend.process,start_ticks=999),0)

    def test_cpu_budget_covers_descendants(self):
        self.running()
        self.backend.account_cpu(self.launch_id,29)
        self.backend.account_cpu(self.launch_id,1)
        self.assertIn(self.launch_id,self.backend.stop_requested)


class ResourceLeaseTests(unittest.TestCase):
    def setUp(self):
        lease_fixtures.LeaseSupervisorTests.setUp(self)
        self.scheduler=DeadlineScheduler(lambda:self.now,lambda:self.elapsed)
        self.backend=ResourceBackend(self.backend.process,self.scheduler)
        self.supervisor.backend=self.backend

    def test_lease_revocation_retains_ownership_until_cleanup(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.runtime.revoke_lease(self.key,1,context=FOUNDER)
        self.backend.cleanup_known=False
        self.assertEqual(self.supervisor.poll(self.launch_id)['state'],'STOPPING')
        self.assertTrue(self.runtime.required_leases(self.execution_id)[0].held)

    def test_lease_deadline_independent_of_controller(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.elapsed=2;self.now-=timedelta(days=1)
        self.scheduler.service()
        self.assertIn(self.launch_id,self.backend.stop_requested)
        self.assertFalse(self.backend.children)


class WatchdogTests(unittest.TestCase):
    def test_notifier_failure_observable_and_stopping_emitted(self):
        a=service_fixtures.Adapters('supervisor')
        loop=service_fixtures.supervisor_entry.start(adapters=a)
        self.addCleanup(loop.shutdown)
        emitted=[]
        def notify(value):
            emitted.append(value)
            if value=='WATCHDOG=1':raise AuthorityError('Synthetic notifier failure')
        loop.notifier=notify;a.clock=.3
        with self.assertRaises(AuthorityError):loop.step()
        self.assertTrue(loop.stopped)
        self.assertEqual(emitted,['WATCHDOG=1','STOPPING=1'])

    def test_heartbeat_does_not_replace_execution_timer(self):
        a=service_fixtures.Adapters('supervisor')
        loop=service_fixtures.supervisor_entry.start(adapters=a)
        self.addCleanup(loop.shutdown)
        stopped=[]
        timer=DeadlineScheduler(lambda:fixtures.NOW,a.now)
        timer.arm(fixtures.uid(),ExecutionDeadline(fixtures.NOW+timedelta(seconds=20),.2),lambda:stopped.append(True))
        loop.deadlines=timer.service
        a.transport.enqueue(message('HEARTBEAT',fixtures.uid(),service_fixtures.GEN,service_fixtures.BOOT,dict(ready=True)))
        a.clock=.2;loop.step()
        self.assertEqual(stopped,[True])
