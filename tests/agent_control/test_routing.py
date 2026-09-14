"""Offline routing acceptance: synthetic state, model output and supervisor only."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fixtures import blank, task_data, U
from tools.agent_control.confinement import ConfinementProfile, TaskRoot
from tools.agent_control.execution import (Cancellation, CommandPolicy, Controller, Enrollment,
    ExecutionBinding, LaunchResult, RoutingDenied, SyntheticLaunchSupervisor)
from tools.agent_control.identity import (PeerIdentity, ProcessIdentity, WorkerIdentity,
    founder_context, validate_identity_map)
from tools.agent_control.model_client import FakeModelClient, OpenAIProposalClient, function_tool
from tools.agent_control.protocol import ModelProposal, Operation, bounded_json, encode_frame, receive_frame
from tools.agent_control.records import ExecutionGrant, Task, task_spec_digest
from tools.agent_control.serialization import canonical_json
from tools.agent_control.types import AuthorityError, Role, ValidationError


class Store:
    def __init__(self, binding):
        self.binding = binding

    def load(self, execution_id):
        if execution_id != self.binding.grant['execution_id']:
            raise KeyError(execution_id)
        return self.binding


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root/'frontend').mkdir()
        (root/'frontend/example.ts').write_text('synthetic source')
        (root/'.git').mkdir()
        (root/'.git/HEAD').write_text('synthetic metadata')
        self.root = TaskRoot(root)
        self.addCleanup(self.root.close)
        task = task_data('IN_PROGRESS')
        task['assignments'][0]['worktree'] = str(root)
        task['worktree']['FE-01'] = str(root)
        task['spec_digest'] = task_spec_digest(task)
        self.task = Task(task)
        g = blank('ExecutionGrant')
        g.update(agent_id='FE-01', role='FRONTEND_ENGINEERING', execution_id=U,
            task_id=self.task['task_id'], spec_version=self.task['spec_version'], spec_digest=self.task['spec_digest'],
            branch='agent/ATS-0001/frontend', worktree=str(root),
            can_read=[{'kind':'FILE','path':'frontend/example.ts'}],
            can_write=[{'kind':'FILE','path':'frontend/example.ts'}],
            process_scope='pid:42001', process_start_identity='123', boot_id=U,
            expires_at='2026-09-15T00:00:00Z', fencing_epoch=1)
        self.peer = PeerIdentity(3000, 3000, 42000)
        self.caller_process = ProcessIdentity(U, 42000, 122)
        self.worker_process = ProcessIdentity(U, 42001, 123)
        self.worker = WorkerIdentity('FE-01', Role.FRONTEND_ENGINEERING, 'synthetic-fe', 3001, 3001)
        self.enrollment = Enrollment(self.peer, self.caller_process, U)
        self.profile = ConfinementProfile(readable_paths=('frontend/example.ts',), writable_paths=('frontend/example.ts',))
        commands = tuple(CommandPolicy(op.value, op, ('/usr/bin/true',)) for op in Operation)
        self.store = Store(ExecutionBinding(ExecutionGrant(g), self.task, self.worker, self.worker_process,
            self.root, self.profile, self.profile.profile_digest, commands))
        self.supervisor = SyntheticLaunchSupervisor()
        self.events = []
        self.reader = lambda pid: {42000:self.caller_process,42001:self.worker_process}[pid]
        self.controller = Controller(self.store, [self.enrollment], self.supervisor, self.events.append,
            clock=lambda:datetime(2026,9,14,tzinfo=timezone.utc), process_reader=self.reader)

    def raw(self, operation='READ_FILE', arguments=None, **overrides):
        d = dict(version=1, request_id=str(uuid4()), execution_id=U, operation=operation,
                 arguments={'path':'frontend/example.ts'} if arguments is None else arguments)
        d.update(overrides)
        return canonical_json(d).encode()

    def deny(self, raw=None, enrollment=None):
        with self.assertRaises(RoutingDenied):
            self.controller.dispatch(raw or self.raw(), enrollment or self.enrollment)
        self.assertNotIn('EXEC', self.supervisor.trace)
        self.assertEqual(self.events[-1].event_type, 'OPERATION_DENIED')

    def test_fake_proposal_alone_never_executes(self):
        p = FakeModelClient(self.raw()).propose({}, {Operation.READ_FILE})
        self.assertEqual(p.operation, Operation.READ_FILE)
        self.assertEqual(self.supervisor.trace, [])

    def test_fake_end_to_end_without_network_or_process_execution(self):
        with patch('socket.create_connection',side_effect=AssertionError('network forbidden')), \
             patch('subprocess.Popen',side_effect=AssertionError('process execution forbidden')):
            proposal=FakeModelClient(self.raw()).propose({},[Operation.READ_FILE])
            result=self.controller.dispatch(canonical_json(proposal.to_dict()).encode(),self.enrollment)
        self.assertEqual(result.status,'EXITED')

    def test_proposal_rejects_all_authority_and_unknown_fields(self):
        for field in ['founder','actor','role','uid','gid','grant','approval','permissions','profile',
                      'fencing_epoch','environment','mounts','sudo','unknown']:
            with self.subTest(field=field):
                self.deny(self.raw(**{field:'SECRET_TEST_VALUE'}))

    def test_nested_claims_and_malformed_json(self):
        for raw in [b'{}', b'not json', b'[]', b'\xff', self.raw(arguments={'path':'frontend/example.ts','uid':0})]:
            self.deny(raw)

    def test_operations_default_deny(self):
        for op in ['PUSH','MERGE','DEPLOY','SUDO','PRODUCTION_DB','CREDENTIAL_ACCESS','AGENT_PERMISSION_CHANGE']:
            self.deny(self.raw(operation=op))

    def test_wrong_grant_and_unenrolled_caller(self):
        self.deny(self.raw(execution_id=str(uuid4())))
        self.deny(enrollment=replace(self.enrollment))
        self.deny(enrollment=replace(self.enrollment, peer=PeerIdentity(0,0,42000)))

    def test_cross_agent_binding(self):
        self.store.binding = replace(self.store.binding, worker=WorkerIdentity('BE-01',Role.BACKEND_ENGINEERING,'synthetic-be',3002,3002))
        self.deny()

    def test_revoked_inactive_fencing_and_expiry(self):
        original = self.store.binding
        for changes in [{'revoked':True},{'active':False},{'fencing_epoch':2}]:
            self.store.binding = replace(original, **changes)
            self.deny()
        g = original.grant.to_dict();g['expires_at']='2026-09-14T00:00:00Z'
        self.store.binding = replace(original, grant=ExecutionGrant(g))
        self.deny()

    def test_spec_and_process_binding(self):
        original = self.store.binding
        for changes in [{'spec_digest':'a'*64},{'process_start_identity':'999'},{'process_scope':'pid:1'}]:
            g = original.grant.to_dict();g.update(changes)
            self.store.binding = replace(original, grant=ExecutionGrant(g))
            self.deny()

    def test_stale_caller_process(self):
        self.caller_process = replace(self.caller_process, start_ticks=999)
        self.deny()

    def test_reservation_denied(self):
        g=self.store.binding.grant.to_dict();g['reserved_resources']=[U]
        self.store.binding=replace(self.store.binding,grant=ExecutionGrant(g))
        self.deny()

    def test_authorization_setup_recheck_exec_order(self):
        result=self.controller.dispatch(self.raw(),self.enrollment)
        self.assertEqual(result.status,'EXITED')
        self.assertEqual(self.supervisor.trace,['AUTHORIZATION','CONFINEMENT_SETUP','FINAL_AUTHORITY_RECHECK','EXEC'])
        self.assertEqual([e.event_type for e in self.events],['MODEL_PROPOSAL_RECEIVED','OPERATION_AUTHORIZED',
            'CONFINEMENT_SETUP_STARTED','WORKER_STARTED','WORKER_EXITED'])
        self.assertFalse(self.controller._issued)

    def test_setup_failure_no_fallback(self):
        self.supervisor.fail_setup=True
        self.deny()
        self.assertIn('CONFINEMENT_SETUP_FAILED',[e.event_type for e in self.events])
        self.assertFalse(self.controller._issued)

    def test_final_authority_recheck_revocation(self):
        self.supervisor.before_ready=lambda:setattr(self.store,'binding',replace(self.store.binding,revoked=True))
        self.deny()
        self.assertEqual(self.supervisor.trace[-1],'ABORT')
        self.assertFalse(self.supervisor._prepared)

    def test_profile_change_during_setup(self):
        self.supervisor.before_ready=lambda:setattr(self.store,'binding',replace(self.store.binding,profile_digest='0'*64))
        self.deny()

    def change_grant(self, **changes):
        grant = self.store.binding.grant.to_dict()
        grant.update(changes)
        self.store.binding = replace(self.store.binding, grant=ExecutionGrant(grant))

    def reject_prepared_change(self, change, raw=None):
        self.supervisor.before_ready = change
        self.deny(raw)
        self.assertEqual(self.supervisor.trace[-1], 'ABORT')
        self.assertFalse(self.supervisor._prepared)
        self.assertFalse(self.controller._issued)
        self.assertEqual(self.supervisor.records, [])

    def test_valid_replacement_grant_rejects_prepared_launch(self):
        self.reject_prepared_change(lambda: self.change_grant(expires_at='2026-09-16T00:00:00Z'))

    def test_coordinated_fencing_change_rejects_prepared_launch(self):
        def change():
            self.change_grant(fencing_epoch=2)
            self.store.binding = replace(self.store.binding, fencing_epoch=2)
        self.reject_prepared_change(change)

    def test_coordinated_task_spec_change_rejects_prepared_launch(self):
        def change():
            task = self.store.binding.task.to_dict()
            task['objective'] = 'Changed synthetic objective'
            task['spec_version'] += 1
            task['spec_digest'] = task_spec_digest(task)
            self.store.binding = replace(self.store.binding, task=Task(task))
            self.change_grant(spec_version=task['spec_version'], spec_digest=task['spec_digest'])
        self.reject_prepared_change(change)

    def test_valid_workspace_rebinding_rejects_prepared_launch(self):
        def change():
            root = Path(self.root.path)/'replacement'
            (root/'frontend').mkdir(parents=True)
            (root/'frontend/example.ts').write_text('synthetic replacement')
            replacement = TaskRoot(root)
            self.addCleanup(replacement.close)
            task = self.store.binding.task.to_dict()
            task['assignments'][0]['worktree'] = str(root)
            task['worktree']['FE-01'] = str(root)
            task['spec_digest'] = task_spec_digest(task)
            self.store.binding = replace(self.store.binding, root=replacement, task=Task(task))
            self.change_grant(worktree=str(root), spec_digest=task['spec_digest'])
        self.reject_prepared_change(change)

    def test_valid_repository_rebinding_rejects_prepared_launch(self):
        profile = replace(self.profile, git_metadata='readonly')
        git = Path(self.root.path)/'.git'
        self.store.binding = replace(self.store.binding, profile=profile, profile_digest=profile.profile_digest,
                                     repository_identity=TaskRoot._identity(git.stat()))
        def change():
            git.rename(git.with_name('old-git'))
            git.mkdir()
            self.store.binding = replace(self.store.binding, repository_identity=TaskRoot._identity(git.stat()))
        self.reject_prepared_change(change, self.raw('GIT_STATUS', {}))

    def test_valid_profile_rebinding_rejects_prepared_launch(self):
        def change():
            profile = replace(self.profile, process_limit=16)
            self.store.binding = replace(self.store.binding, profile=profile, profile_digest=profile.profile_digest)
        self.reject_prepared_change(change)

    def test_valid_process_rebinding_rejects_prepared_launch(self):
        def change():
            self.worker_process = replace(self.worker_process, start_ticks=124)
            self.store.binding = replace(self.store.binding, execution_process=self.worker_process)
            self.change_grant(process_start_identity='124')
        self.reject_prepared_change(change)

    def test_authority_revision_detects_revoke_restore(self):
        def change():
            self.store.binding = replace(self.store.binding, revoked=True, authority_revision=1)
            self.store.binding = replace(self.store.binding, revoked=False, authority_revision=2)
        self.reject_prepared_change(change)

    def use_expiry_clock(self, remaining):
        self.now = datetime(2026, 9, 15, tzinfo=timezone.utc) - timedelta(seconds=remaining)
        self.controller.clock = lambda: self.now

    def test_expiry_before_record_creation(self):
        self.use_expiry_clock(0)
        self.deny()
        self.assertEqual(self.supervisor.trace, [])
        self.assertFalse(self.controller._issued)

    def test_expiry_during_initial_validation(self):
        self.use_expiry_clock(.5)
        original = self.root.inspect
        def inspect(*args, **kwargs):
            original(*args, **kwargs)
            self.now += timedelta(seconds=1)
        with patch.object(self.root, 'inspect', side_effect=inspect):
            self.deny()
        self.assertEqual(self.supervisor.trace, [])

    def test_expiry_in_setup_audit_prevents_preparation(self):
        self.use_expiry_clock(.5)
        def audit(event):
            self.events.append(event)
            if event.event_type == 'CONFINEMENT_SETUP_STARTED':
                self.now += timedelta(seconds=1)
        self.controller.audit = audit
        self.deny()
        self.assertNotIn('CONFINEMENT_SETUP', self.supervisor.trace)

    def test_expiry_during_preparation_aborts(self):
        self.use_expiry_clock(.5)
        self.reject_prepared_change(lambda: setattr(self, 'now', self.now + timedelta(seconds=1)))

    def test_expiry_during_final_validation_aborts(self):
        self.use_expiry_clock(.5)
        original = self.root.inspect
        def inspect(*args, **kwargs):
            original(*args, **kwargs)
            if 'FINAL_AUTHORITY_RECHECK' in self.supervisor.trace:
                self.now += timedelta(seconds=1)
        with patch.object(self.root, 'inspect', side_effect=inspect):
            self.reject_prepared_change(lambda: None)

    def test_expiry_at_last_release_clock_aborts(self):
        self.use_expiry_clock(.5)
        original = self.controller._check
        def check(*args):
            record = original(*args)
            if 'FINAL_AUTHORITY_RECHECK' in self.supervisor.trace:
                self.now += timedelta(seconds=1)
            return record
        with patch.object(self.controller, '_check', side_effect=check):
            self.reject_prepared_change(lambda: None)

    def test_grant_disappears_during_final_validation(self):
        original_inspect = self.root.inspect
        original_load = self.store.load
        removed = False
        def inspect(*args, **kwargs):
            nonlocal removed
            original_inspect(*args, **kwargs)
            if 'FINAL_AUTHORITY_RECHECK' in self.supervisor.trace:
                removed = True
        def load(execution_id):
            if removed:
                raise KeyError(execution_id)
            return original_load(execution_id)
        with patch.object(self.root, 'inspect', side_effect=inspect), patch.object(self.store, 'load', side_effect=load):
            self.reject_prepared_change(lambda: None)

    def test_subsecond_authority_never_rounded_up(self):
        self.use_expiry_clock(.5)
        self.supervisor.before_ready = lambda: setattr(self, 'now', self.now + timedelta(seconds=.25))
        self.controller.dispatch(self.raw(), self.enrollment)
        self.assertEqual(self.supervisor.records[0].timeout_seconds, .25)

    def test_unchanged_authority_with_elapsed_time_succeeds(self):
        self.use_expiry_clock(10)
        self.supervisor.before_ready = lambda: setattr(self, 'now', self.now + timedelta(seconds=2))
        self.controller.dispatch(self.raw(), self.enrollment)
        self.assertEqual(self.supervisor.records[0].timeout_seconds, 8)

    def test_worker_started_audit_cannot_bypass_release_recheck(self):
        def audit(event):
            self.events.append(event)
            if event.event_type == 'WORKER_STARTED':
                self.change_grant(fencing_epoch=2)
                self.store.binding = replace(self.store.binding, fencing_epoch=2)
        self.controller.audit = audit
        self.reject_prepared_change(lambda: None)

    def test_state_change_during_final_validation_aborts(self):
        original = self.root.inspect
        def inspect(*args, **kwargs):
            original(*args, **kwargs)
            if 'FINAL_AUTHORITY_RECHECK' in self.supervisor.trace:
                self.store.binding = replace(self.store.binding, revoked=True)
        with patch.object(self.root, 'inspect', side_effect=inspect):
            self.reject_prepared_change(lambda: None)

    def test_replay_is_one_use(self):
        raw=self.raw();self.controller.dispatch(raw,self.enrollment)
        count=len(self.supervisor.records)
        with self.assertRaises(RoutingDenied):self.controller.dispatch(raw,self.enrollment)
        self.assertEqual(len(self.supervisor.records),count)

    def test_audit_failure_prevents_execution(self):
        def fail(event):
            if event.event_type=='OPERATION_AUTHORIZED':raise OSError('synthetic unavailable')
        self.controller.audit=fail
        with self.assertRaises(OSError):self.controller.dispatch(self.raw(),self.enrollment)
        self.assertEqual(self.supervisor.trace,[])

    def test_parent_environment_and_descriptors_not_in_launch_record(self):
        secrets={k:'SYNTHETIC_SECRET' for k in ['OPENAI_API_KEY','GH_TOKEN','SSH_AUTH_SOCK','AWS_TEST','DATABASE_TEST',
            'POSTGRES_TEST','SMTP_TEST','EMAIL_TEST','ANTHROPIC_TEST','DIGITALOCEAN_TEST','GITHUB_TEST','SECRET_TEST',
            'TOKEN_TEST','KEY_TEST','RESEND_TEST','STRIPE_TEST','LIVEKIT_TEST','DOCKER_TEST','GIT_CONFIG','LD_PRELOAD',
            'PYTHONPATH','NODE_OPTIONS','BASH_ENV','ENV','HOME','USER','LOGNAME','SUDO_USER']}
        with patch.dict(os.environ,secrets):self.controller.dispatch(self.raw(),self.enrollment)
        record=self.supervisor.records[0]
        self.assertEqual(record.environment,self.profile.environment())
        self.assertEqual(record.inherited_fds,())
        self.assertNotIn('SYNTHETIC_SECRET',repr(record))
        self.assertNotIn('OPENAI_API_KEY',repr(record))
        self.assertFalse(record.shell)

    def test_paths_absolute_traversal_git_and_forbidden(self):
        for path in ['/etc/passwd','../outside','frontend/../outside','frontend/\x00bad','.git/HEAD',
                     '.codex/auth.json','backend/other.py']:
            self.deny(self.raw(arguments={'path':path}))

    def test_symlink_escape_and_hardlink(self):
        path=Path(self.root.path)/'frontend/example.ts';path.unlink()
        target=Path(self.temp.name)/'outside';target.write_text('synthetic')
        path.symlink_to(target)
        self.deny()
        path.unlink();os.link(target,path)
        self.deny()

    def test_task_root_substitution(self):
        path=Path(self.root.path);moved=path.with_name(path.name+'-moved')
        path.rename(moved);path.mkdir()
        try:self.deny()
        finally:
            path.rmdir();moved.rename(path)

    def test_safe_read_uses_pinned_descriptor(self):
        fd=self.root.open_read('frontend/example.ts')
        try:self.assertEqual(os.read(fd,100),b'synthetic source')
        finally:os.close(fd)

    def test_overbroad_profile_is_denied(self):
        p=replace(self.profile,readable_paths=('frontend',))
        self.store.binding=replace(self.store.binding,profile=p,profile_digest=p.profile_digest)
        self.deny()

    def test_fixed_argv_only(self):
        self.deny(self.raw('RUN_COMMAND',{'command_id':'RUN_COMMAND','argv':['/usr/bin/sh','-c','echo bad']}))
        self.deny(self.raw('RUN_COMMAND',{'command_id':'RUN_COMMAND','argv':'echo bad'}))
        result=self.controller.dispatch(self.raw('RUN_COMMAND',{'command_id':'RUN_COMMAND','argv':['/usr/bin/true']}),self.enrollment)
        self.assertEqual(result.status,'EXITED')

    def test_timeout_bounded_output(self):
        self.supervisor.duration=100
        self.supervisor.stdout=b'x'*70000
        self.supervisor.stderr=b'y'*70000
        r=self.controller.dispatch(self.raw(),self.enrollment)
        self.assertEqual(r.status,'TIMED_OUT');self.assertIsNone(r.exit_code)
        self.assertTrue(r.truncated);self.assertEqual(len(r.stdout),65536)
        self.assertEqual(len(r.stderr),65536)

    def test_cancellation_before_exec(self):
        cancel=Cancellation();self.supervisor.before_ready=cancel.cancel
        with self.assertRaises(RoutingDenied):self.controller.dispatch(self.raw(),self.enrollment,cancellation=cancel)
        self.assertNotIn('EXEC',self.supervisor.trace)
        self.assertFalse(self.supervisor._prepared)

    def test_no_raw_contents_in_audit(self):
        self.controller.dispatch(self.raw('WRITE_FILE',{'path':'frontend/example.ts','content':'SECRET_TEST_VALUE'}),self.enrollment)
        self.assertNotIn('SECRET_TEST_VALUE',repr(self.events))
        self.assertNotIn('frontend/example.ts',repr(self.events))

    def test_bwrap_generation(self):
        argv=self.profile.bwrap_argv(self.root,('/usr/bin/true',))
        self.assertEqual(argv[0],'/usr/bin/bwrap')
        for flag in ['--unshare-user','--unshare-net','--unshare-pid','--clearenv','--remount-ro']:
            self.assertIn(flag,argv)
        self.assertNotIn('/home/bonup',repr(argv))
        self.assertEqual(argv[-2:],('--','/usr/bin/true'))
        self.assertEqual(argv,self.profile.bwrap_argv(self.root,('/usr/bin/true',)))
        with self.assertRaises(ValidationError):replace(self.profile,readonly_roots=('/home/bonup/.codex',))
        with self.assertRaises(ValidationError):TaskRoot('/home/bonup/.codex')

    def test_git_operation_requires_pinned_repository(self):
        p=replace(self.profile,git_metadata='readonly')
        self.store.binding=replace(self.store.binding,profile=p,profile_digest=p.profile_digest)
        self.deny(self.raw('GIT_STATUS',{}))
        identity=TaskRoot._identity(os.stat(Path(self.root.path)/'.git'))
        self.store.binding=replace(self.store.binding,repository_identity=identity)
        self.controller.dispatch(self.raw('GIT_STATUS',{}),self.enrollment)
        git=Path(self.root.path)/'.git'
        git.rename(git.with_name('old-git'));git.mkdir()
        count=len(self.supervisor.records)
        with self.assertRaises(RoutingDenied):self.controller.dispatch(self.raw('GIT_STATUS',{}),self.enrollment)
        self.assertEqual(len(self.supervisor.records),count)

    def test_git_commit_gate_and_no_writable_git_for_commands(self):
        p=replace(self.profile,git_metadata='commit')
        self.store.binding=replace(self.store.binding,profile=p,profile_digest=p.profile_digest,
            repository_identity=TaskRoot._identity(os.stat(Path(self.root.path)/'.git')))
        self.deny(self.raw('GIT_COMMIT_LOCAL',{'message':'synthetic'}))
        g=self.store.binding.grant.to_dict();g['can_commit_local']=True
        self.store.binding=replace(self.store.binding,grant=ExecutionGrant(g))
        self.controller.dispatch(self.raw('GIT_COMMIT_LOCAL',{'message':'synthetic'}),self.enrollment)
        count=len(self.supervisor.records)
        with self.assertRaises(RoutingDenied):self.controller.dispatch(self.raw(),self.enrollment)
        self.assertEqual(len(self.supervisor.records),count)

    def test_unconfigured_operation_denied(self):
        self.store.binding=replace(self.store.binding,commands=())
        self.deny()

    def test_cancelled_result_representation(self):
        result=LaunchResult.bounded('CANCELLED',limit=10)
        self.assertEqual(result.stdout,b'')
        self.assertIsNone(result.exit_code)

    def test_profile_inventory_rejects_nested_secrets(self):
        (Path(self.root.path)/'frontend/.env').write_text('synthetic')
        with self.assertRaises(ValidationError):list(self.root.export_entries('frontend'))

    def test_model_response_unknown_multiple_incomplete(self):
        c=OpenAIProposalClient()
        call={'type':'function_call','name':'READ_FILE','call_id':'synthetic',
              'arguments':'{"path":"frontend/example.ts"}'}
        for response in [dict(status='incomplete',output=[call]),dict(status='completed',output=[call,call]),
                         dict(status='completed',output=[dict(call,name='SUDO')]),
                         dict(status='completed',output=[{'type':'web_search_call'}])]:
            with self.assertRaises(ValidationError):
                c.parse_response(json.dumps(response).encode(),request_id=U,execution_id=U,allowed_operations=[Operation.READ_FILE])

    def test_model_credential_objects_cannot_serialize(self):
        class Credential:pass
        with self.assertRaises(ValidationError):canonical_json({'arguments':Credential()})
        with self.assertRaises(ValidationError):ModelProposal.parse(self.raw(arguments={'path':'frontend/example.ts','credential':{}}))

    def test_openai_offline_contract(self):
        client=OpenAIProposalClient()
        request=client.build_request('synthetic-model','sanitized context',[Operation.READ_FILE])
        self.assertEqual(request['tools'],[function_tool(Operation.READ_FILE)])
        self.assertEqual(request['tools'][0]['type'],'function')
        self.assertTrue(request['tools'][0]['strict']);self.assertFalse(request['parallel_tool_calls'])
        with self.assertRaises(ValidationError):client.propose({},[Operation.READ_FILE])
        response={'status':'completed','output':[{'type':'function_call','name':'READ_FILE','call_id':'call_synthetic',
            'arguments':json.dumps({'path':'frontend/example.ts'})}]}
        call,p=client.parse_response(json.dumps(response).encode(),request_id=U,execution_id=U,allowed_operations=[Operation.READ_FILE])
        self.assertEqual(p.operation,Operation.READ_FILE)
        self.assertEqual(client.function_output(call,accepted=False)['type'],'function_call_output')
        response['output'][0]['arguments']='{"founder":true}'
        with self.assertRaises(ValidationError):client.parse_response(json.dumps(response).encode(),request_id=U,execution_id=U,allowed_operations=[Operation.READ_FILE])


class IdentityProtocolTests(unittest.TestCase):
    def test_socket_kernel_peer(self):
        a,b=socket.socketpair()
        try:self.assertEqual(PeerIdentity.from_socket(a),PeerIdentity.current())
        finally:a.close();b.close()

    def test_founder_enrollment_root_and_environment(self):
        proc=ProcessIdentity('synthetic',12,34)
        peer=PeerIdentity(1000,1000,12)
        with patch.dict(os.environ,{'USER':'root','SUDO_USER':'bonup'}):
            ctx=founder_context(peer,founder_uid=1000,enrolled_process=proc,reader=lambda _:proc)
        self.assertEqual(ctx.actor_id,'FOUNDER')
        for bad in [PeerIdentity(0,0,12),PeerIdentity(1001,1001,12),PeerIdentity(1000,1000,13)]:
            with self.assertRaises(AuthorityError):founder_context(bad,founder_uid=1000,enrolled_process=proc,reader=lambda _:proc)
        with self.assertRaises(AuthorityError):founder_context(PeerIdentity(0,0,12),founder_uid=0,enrolled_process=proc,reader=lambda _:proc)

    def test_mapping_and_process_identity(self):
        w=WorkerIdentity('FE-01',Role.FRONTEND_ENGINEERING,'synthetic',2000,2000)
        validate_identity_map([w],1000)
        for workers,founder in [([w,w],1000),([w],2000)]:
            with self.assertRaises(AuthorityError):validate_identity_map(workers,founder)
        p=ProcessIdentity.read(os.getpid());p.verify()
        with self.assertRaises(AuthorityError):replace(p,start_ticks=p.start_ticks+1).verify()

    def test_duplicate_depth_size_unicode(self):
        for raw in [b'{"a":1,"a":2}',b'['*13+b'0'+b']'*13,b' '*65537,b'"\xff"']:
            with self.assertRaises(ValidationError):bounded_json(raw)

    def test_framing_roundtrip_and_timeout(self):
        p=ModelProposal.parse(json.dumps(dict(version=1,request_id=U,execution_id=U,operation='GIT_STATUS',arguments={})).encode())
        a,b=socket.socketpair()
        try:
            a.sendall(encode_frame(p));self.assertEqual(receive_frame(b),p)
            with self.assertRaises(ValidationError):receive_frame(b,timeout=.01)
            a.sendall(struct.pack('!I',65537))
            with self.assertRaises(ValidationError):receive_frame(b)
        finally:a.close();b.close()

    def test_truncated_frame(self):
        a,b=socket.socketpair()
        try:
            a.sendall(struct.pack('!I',5)+b'{}');a.shutdown(socket.SHUT_WR)
            with self.assertRaises(ValidationError):receive_frame(b)
        finally:a.close();b.close()
