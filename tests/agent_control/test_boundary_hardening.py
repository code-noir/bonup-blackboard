"""Deterministic corrective security regressions; disposable state, no host provisioning."""
import copy
from dataclasses import replace
from datetime import timedelta
import errno
import os
from pathlib import Path
import socket
import sqlite3
import unittest
from unittest.mock import patch

import test_routing as routing_fixtures
import test_supervisor as supervisor_fixtures
from fixtures import blank, FOUNDER, U
from tools.agent_control.confinement import PinnedMounts
from tools.agent_control.execution import RequiredLease, RoutingDenied
from tools.agent_control.protocol import ModelProposal
from tools.agent_control.records import ExecutionGrant, Reservation, Task
from tools.agent_control.release_gate import FixedPayload
from tools.agent_control.runtime_schema import check_version, migrate_v2
from tools.agent_control.serialization import canonical_json, digest, parse_json
from tools.agent_control.storage import RegistryBlocked
from tools.agent_control.supervisor_linux import secure_open
from tools.agent_control.types import AuthorityError, ValidationError
from tools.agent_control import provisioning as provision

NOW=supervisor_fixtures.NOW
EXPIRY=supervisor_fixtures.EXPIRY
uid=supervisor_fixtures.uid


def resource(execution, key, task='ATS-0001'):
    value=blank('Reservation')
    value.update(reservation_id=key,resource_type='FRONTEND_BUILD',resource_key='synthetic-build-'+key,
                 owner_task=task,owner_execution=execution,fencing_epoch=1,status='ACTIVE',
                 lease_expires_at=EXPIRY)
    return Reservation(value,context=FOUNDER)


class MountContinuityTests(unittest.TestCase):
    setUp=supervisor_fixtures.LinuxPrimitiveTests.setUp

    def pin(self):
        mounts=PinnedMounts(self.root,self.profile,expected_identity=self.root.identity)
        self.addCleanup(mounts.close)
        return mounts

    def test_replace_export_after_open_inspects_and_mounts_original_descriptor(self):
        original=(self.path/'source').stat().st_ino
        calls=[]
        def swap(root_fd,path,**kwargs):
            fd=secure_open(root_fd,path,**kwargs)
            calls.append((path,os.fstat(fd).st_ino))
            if path=='source':
                (self.path/'source').rename(self.path/'old')
                (self.path/'source').mkdir()
                (self.path/'source/uninspected').write_text('B')
            return fd
        with patch('tools.agent_control.supervisor_linux.secure_open',side_effect=swap):
            mounts=self.pin()
        self.assertEqual(os.fstat(mounts.pass_fds[0]).st_ino,original)
        self.assertEqual([p for p,_ in calls],['source','file'])
        self.assertEqual(os.listdir(mounts.pass_fds[0]),['file'])
        argv=mounts.argv(FixedPayload(('/usr/bin/true',),self.profile.environment()))
        self.assertEqual(argv[argv.index('--ro-bind-fd')+1],str(mounts.pass_fds[0]))

    def test_rename_after_inspection_keeps_same_export(self):
        mounts=self.pin(); before=os.fstat(mounts.pass_fds[0])
        (self.path/'source').rename(self.path/'renamed')
        mounts.argv(FixedPayload(('/usr/bin/true',),self.profile.environment()))
        after=os.fstat(mounts.pass_fds[0])
        self.assertEqual((before.st_dev,before.st_ino),(after.st_dev,after.st_ino))

    def test_child_open_uses_pinned_parent_even_when_parent_path_replaced(self):
        def swap(root_fd,path,**kwargs):
            fd=secure_open(root_fd,path,**kwargs)
            if path=='source':
                (self.path/'source').rename(self.path/'old')
                (self.path/'source').symlink_to('/unmounted-host',target_is_directory=True)
            return fd
        with patch('tools.agent_control.supervisor_linux.secure_open',side_effect=swap):
            self.assertEqual(os.listdir(self.pin().pass_fds[0]),['file'])

    def test_root_parent_substitution_rejected(self):
        base=self.path/'parent';base.mkdir()
        # root.verify checks the original pathname's inode before FD consumption.
        mounts=self.pin()
        displaced=self.path.with_name(self.path.name+'-moved')
        self.path.rename(displaced)
        try:
            self.path.mkdir()
            with self.assertRaises(ValidationError):mounts.argv(FixedPayload(('/usr/bin/true',),self.profile.environment()))
        finally:
            self.path.rmdir();displaced.rename(self.path)

    def test_symlink_special_socket_hardlink_git_exports_denied(self):
        for kind in ('symlink','fifo','socket','hardlink','git'):
            with self.subTest(kind=kind):
                p=self.path/'source'/('.git' if kind=='git' else 'bad')
                sock=None
                if kind=='symlink':p.symlink_to('/etc')
                elif kind=='fifo':os.mkfifo(p)
                elif kind=='socket':sock=socket.socket(socket.AF_UNIX);sock.bind(str(p))
                elif kind=='hardlink':os.link(self.path/'source/file',p)
                else:p.mkdir()
                try:
                    with self.assertRaises((OSError,AuthorityError,ValidationError)):self.pin()
                finally:
                    if sock:sock.close()
                    p.rmdir() if kind=='git' else p.unlink()

    def test_mount_crossing_rejected_and_no_descriptor_leak(self):
        before=set(os.listdir('/proc/self/fd'))
        def cross(root_fd,path,**kwargs):
            if path=='file':raise OSError(errno.EXDEV,'synthetic mount crossing')
            return secure_open(root_fd,path,**kwargs)
        with patch('tools.agent_control.supervisor_linux.secure_open',side_effect=cross):
            with self.assertRaises(OSError):self.pin()
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)

    def test_device_or_inode_identity_mismatch_denied(self):
        for index in (0,1):
            bad=list(self.root.identity);bad[index]+=1
            with self.assertRaises(ValidationError):PinnedMounts(self.root,self.profile,expected_identity=tuple(bad))

    def test_writable_export_cannot_contain_git_metadata(self):
        self.profile=replace(self.profile,readable_paths=(),writable_paths=('source',))
        (self.path/'source/.git').mkdir()
        with self.assertRaises(ValidationError):self.pin()


class ClosedSchemaTests(unittest.TestCase):
    setUp=supervisor_fixtures.MigrationTests.setUp

    def test_closed_inventory_rejects_extra_objects_in_both_versions(self):
        statements=[
            "CREATE TRIGGER injected AFTER INSERT ON metadata BEGIN DELETE FROM sequences; END",
            'CREATE VIEW injected AS SELECT * FROM metadata',
            'CREATE TABLE injected(x)',
            'CREATE INDEX injected ON metadata(value)',
            'CREATE TEMP TRIGGER injected AFTER INSERT ON metadata BEGIN DELETE FROM sequences; END']
        for version in (1,2):
            if version==2:migrate_v2(self.registry)
            for sql in statements:
                with self.subTest(version=version,sql=sql):
                    self.registry.db.execute('SAVEPOINT attack')
                    self.registry.db.execute(sql)
                    with self.assertRaises(RegistryBlocked):check_version(self.registry.db)
                    self.registry.db.execute('ROLLBACK TO attack');self.registry.db.execute('RELEASE attack')

    def test_migration_refuses_untrusted_source_without_changes(self):
        self.registry.db.execute('CREATE TRIGGER injected AFTER INSERT ON metadata BEGIN DELETE FROM sequences; END')
        before=list(self.registry.db.iterdump())
        with self.assertRaises(RegistryBlocked):migrate_v2(self.registry)
        self.assertEqual(list(self.registry.db.iterdump()),before)

    def test_modified_expected_trigger_and_missing_table_fail_closed(self):
        for sql in ('DROP TABLE metadata',
                    'DROP TRIGGER immutable_audit_events_update'):
            self.registry.db.execute('SAVEPOINT attack')
            self.registry.db.execute(sql)
            if 'TRIGGER' in sql:
                self.registry.db.execute('CREATE TRIGGER immutable_audit_events_update BEFORE UPDATE ON audit_events BEGIN SELECT 1; END')
            with self.assertRaises(RegistryBlocked):check_version(self.registry.db)
            self.registry.db.execute('ROLLBACK TO attack');self.registry.db.execute('RELEASE attack')

    def test_sqlite_internal_sequence_autoindexes_and_analyze_accepted(self):
        for version in (1,2):
            if version==2:migrate_v2(self.registry)
            self.registry.db.execute('ANALYZE')
            self.assertEqual(check_version(self.registry.db),version)
            self.assertTrue(self.registry.db.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone())

    def test_untrusted_target_verification_rolls_back(self):
        from tools.agent_control import runtime_schema
        original=runtime_schema.check_version
        def corrupt_target(db):
            if db.execute('SELECT max(version) FROM schema_versions').fetchone()[0]==2:
                db.execute('CREATE VIEW unexpected AS SELECT * FROM metadata')
            return original(db)
        before=list(self.registry.db.iterdump())
        with patch.object(runtime_schema,'check_version',side_effect=corrupt_target):
            with self.assertRaises(RegistryBlocked):migrate_v2(self.registry)
        self.assertEqual(list(self.registry.db.iterdump()),before)
        self.assertEqual(check_version(self.registry.db),1)

    def test_version_view_is_rejected_before_evaluation(self):
        calls=[]
        self.registry.db.create_function('unexpected',0,lambda:calls.append(True) or 1)
        self.registry.db.execute('DROP TABLE schema_versions')
        self.registry.db.execute('CREATE VIEW schema_versions AS SELECT unexpected() AS version')
        with self.assertRaises(RegistryBlocked):check_version(self.registry.db)
        self.assertEqual(calls,[])


class LeaseRoutingTests(unittest.TestCase):
    raw=routing_fixtures.RoutingTests.raw
    deny=routing_fixtures.RoutingTests.deny

    def setUp(self):
        routing_fixtures.RoutingTests.setUp(self)
        self.now=NOW;self.elapsed=0
        self.controller.clock=lambda:self.now
        self.controller.elapsed=lambda:self.elapsed
        self.leases((2,))

    def leases(self, lifetimes):
        g=self.store.binding.grant.to_dict();t=self.store.binding.task.to_dict()
        keys=[uid() for _ in lifetimes]
        g['reserved_resources']=keys;t['resource_reservations']=keys
        leases=tuple(RequiredLease(key,U,1,(NOW+timedelta(seconds=seconds)).isoformat(),1,True,False,
                                  canonical_json(resource(U,key).to_dict())) for key,seconds in zip(keys,lifetimes))
        self.store.binding=replace(self.store.binding,grant=ExecutionGrant(g),task=Task(t),
                                  active_reservations=frozenset(keys),required_leases=leases)

    def test_expired_lease_before_authorization_never_prepares(self):
        self.now+=timedelta(seconds=2);self.deny()
        self.assertNotIn('CONFINEMENT_SETUP',self.supervisor.trace)

    def test_lease_expiry_during_setup_never_releases(self):
        self.supervisor.before_ready=lambda:setattr(self,'now',NOW+timedelta(seconds=2))
        self.deny();self.assertIn('ABORT',self.supervisor.trace)

    def test_wall_rollback_cannot_extend_authorized_lease(self):
        def rollback():self.now=NOW-timedelta(days=1);self.elapsed=2
        self.supervisor.before_ready=rollback
        self.deny();self.assertIn('ABORT',self.supervisor.trace)

    def test_earliest_of_multiple_leases_sets_timeout(self):
        self.leases((5,2,7))
        self.controller.dispatch(self.raw(),self.enrollment)
        self.assertEqual(self.supervisor.records[0].timeout_seconds,2)

    def test_subsecond_lease_is_not_rounded_up(self):
        self.leases((.125,))
        self.controller.dispatch(self.raw(),self.enrollment)
        self.assertEqual(self.supervisor.records[0].timeout_seconds,.125)

    def test_unchanged_valid_lease_executes(self):
        self.assertEqual(self.controller.dispatch(self.raw(),self.enrollment).status,'EXITED')

    def test_replacement_revision_fence_owner_revocation_resource_and_restore_rejected(self):
        original=self.store.binding
        for mutation in ('expiry','revision','fence','owner','revoked','resource','restore'):
            with self.subTest(mutation=mutation):
                self.store.binding=original;self.supervisor.trace.clear()
                def change():
                    lease=original.required_leases[0];r=parse_json(lease.resource_json)
                    kwargs={}
                    if mutation=='expiry':kwargs['expires_at']=(NOW+timedelta(seconds=20)).isoformat()
                    if mutation in ('revision','restore'):kwargs['revision']=2
                    if mutation=='fence':kwargs['fencing_epoch']=2;r['fencing_epoch']=2
                    if mutation=='owner':kwargs['execution_id']=uid();r['owner_execution']=kwargs['execution_id']
                    if mutation=='revoked':kwargs['revoked']=True
                    if mutation=='resource':r['resource_key']='different-resource'
                    self.store.binding=replace(original,required_leases=(replace(lease,resource_json=canonical_json(r),**kwargs),))
                self.supervisor.before_ready=change
                self.deny();self.assertIn('ABORT',self.supervisor.trace)

    def test_resource_ids_alone_are_not_authority(self):
        self.store.binding=replace(self.store.binding,required_leases=())
        self.deny()

    def test_new_request_cannot_revive_same_expired_lease_after_rollback(self):
        self.controller.dispatch(self.raw(),self.enrollment)
        self.supervisor.trace.clear()
        self.now=NOW-timedelta(days=1);self.elapsed=2
        self.deny()  # new request UUID, same immutable lease

    def test_observed_wall_expiry_remains_expired_after_rollback(self):
        self.controller.dispatch(self.raw(),self.enrollment)
        self.supervisor.trace.clear()
        self.now=NOW+timedelta(seconds=2)
        self.deny()
        self.now=NOW-timedelta(days=1)
        self.deny()  # elapsed clock has not advanced; observed expiry is latched


class LeaseSupervisorTests(unittest.TestCase):
    def setUp(self):
        supervisor_fixtures.RuntimeTests.setUp(self)
        self.supervisor.stop(self.launch_id,'CANCELLED')
        self.key=uid()
        original=self.registry.load
        grant=original('ExecutionGrant',self.execution_id).to_dict();grant['reserved_resources']=[self.key]
        self.grant=ExecutionGrant(grant)
        def load(kind,key):
            return self.grant if kind=='ExecutionGrant' and key==self.execution_id else original(kind,key)
        p=patch.object(self.registry,'load',side_effect=load);p.start();self.addCleanup(p.stop)
        self.runtime.acquire_lease(self.execution_id,self.key,1,(NOW+timedelta(seconds=2)).isoformat(),NOW,
            reservation=resource(self.execution_id,self.key,self.grant['task_id']))
        self.launch_id=self.runtime.register_launch(self.execution_id,uid(),'b'*64,self.generation,self.boot,
            {'workspace':[1,2,3001,3001],'repository':None,'profile_digest':self.profile_id})

    def test_lease_wins_over_longer_grant_and_operation(self):
        self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.supervisor.deadlines[self.launch_id].elapsed_deadline,2)
        self.assertEqual(self.supervisor.deadlines[self.launch_id].expires_at,NOW+timedelta(seconds=2))

    def test_running_expiry_and_wall_rollback_require_whole_launch_cleanup(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.backend.cleanup_known=False;self.elapsed=2;self.now=NOW-timedelta(days=1)
        self.assertEqual(self.supervisor.poll(self.launch_id)['state'],'STOPPING')
        self.assertEqual(self.runtime.required_leases(self.execution_id)[0].held,True)
        self.backend.cleanup_known=True
        self.assertEqual(self.supervisor.poll(self.launch_id)['state'],'TERMINAL')
        self.assertFalse(self.runtime.required_leases(self.execution_id)[0].held)

    def test_running_revocation_retains_lease_until_cleanup(self):
        self.supervisor.prepare(self.launch_id);self.supervisor.release(self.launch_id)
        self.runtime.revoke_lease(self.key,1,context=FOUNDER)
        self.backend.cleanup_known=False
        self.assertEqual(self.supervisor.poll(self.launch_id)['reason'],'REVOKED')
        self.assertTrue(self.runtime.required_leases(self.execution_id)[0].held)

    def test_revision_change_in_preparation_rejects_release(self):
        def change():self.runtime.db.execute('UPDATE resource_leases SET revision=revision+1')
        self.backend.before_ready=change
        with self.assertRaises(AuthorityError):self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.backend.releases,[])
        self.assertEqual(self.runtime.launch(self.launch_id)['state'],'TERMINAL')

    def test_later_replacement_lease_cannot_authorize_old_preparation(self):
        self.supervisor.prepare(self.launch_id)
        self.runtime.db.execute('UPDATE resource_leases SET expires_at=?,revision=revision+1',(EXPIRY,))
        with self.assertRaises(AuthorityError):self.supervisor.release(self.launch_id)
        self.assertEqual(self.backend.releases,[])

    def test_release_at_exact_deadline_denied_even_after_wall_rollback(self):
        self.supervisor.prepare(self.launch_id)
        self.elapsed=2;self.now=NOW-timedelta(days=1)
        with self.assertRaises(AuthorityError):self.supervisor.release(self.launch_id)
        self.assertEqual(self.backend.releases,[])

    def test_lease_revision_guard_and_no_delete_prevent_aba(self):
        for sql in ('UPDATE resource_leases SET revoked=1','DELETE FROM resource_leases'):
            with self.assertRaises(sqlite3.IntegrityError):self.runtime.db.execute(sql)
        self.runtime.revoke_lease(self.key,1,context=FOUNDER)
        with self.assertRaises(AuthorityError):self.runtime.revoke_lease(self.key,1,context=FOUNDER)

    def test_lease_expires_during_backend_setup_no_release(self):
        self.backend.before_ready=lambda:setattr(self,'now',NOW+timedelta(seconds=2))
        with self.assertRaises(AuthorityError):self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.backend.releases,[])

    def test_original_controller_elapsed_deadline_cannot_be_rearmed(self):
        self.record=replace(self.record,elapsed_deadline=.125)
        self.now=NOW-timedelta(days=1)
        self.supervisor.prepare(self.launch_id)
        self.assertEqual(self.supervisor.deadlines[self.launch_id].elapsed_deadline,.125)
        self.elapsed=.125
        with self.assertRaises(AuthorityError):self.supervisor.release(self.launch_id)
        self.assertEqual(self.backend.releases,[])

    def test_resource_digest_corruption_rejected(self):
        self.runtime.db.execute("UPDATE resource_leases SET resource_digest=?,revision=revision+1",('a'*64,))
        with self.assertRaises(AuthorityError):self.runtime.required_leases(self.execution_id)

    def test_alias_reservation_cannot_acquire_same_held_physical_resource(self):
        other=uid();g=self.grant.to_dict();g['reserved_resources'].append(other);self.grant=ExecutionGrant(g)
        alias=resource(self.execution_id,other).to_dict()
        alias['resource_key']=resource(self.execution_id,self.key)['resource_key']
        with self.assertRaises(sqlite3.IntegrityError):self.runtime.acquire_lease(
            self.execution_id,other,1,EXPIRY,NOW,reservation=Reservation(alias,context=FOUNDER))


def approved_manifest():
    m=provision.review_manifest(Path(__file__).resolve().parents[2])
    m.update(approved=True,provisioning_generation=1,service=provision.service_policy(),
             files=[dict(p,sha256=digest(p)) for p in provision.artifact_policy()])
    for index,a in enumerate(m['accounts']):a.update(uid=3000+index,gid=3000+index,provisioning_generation=1)
    m['workspace_storage_limit']=[dict(path=path,bytes=2**30,inodes=10000,enforcement='filesystem-quota')
        for path in ['/var/lib/bonup-agent-control',*('/srv/bonup-agent-work/'+n for n in provision.NAMES[1:])]]
    m['rollback']=provision.rollback_policy(m)
    return m


class ApprovedManifestTests(unittest.TestCase):
    def test_complete_synthetic_manifest_has_stable_digest(self):
        m=approved_manifest()
        self.assertEqual(provision.validate_approved_manifest(m),digest(m))
        self.assertEqual(provision.validate_approved_manifest(copy.deepcopy(m)),digest(m))

    def test_unsafe_top_level_values_rejected(self):
        for key,value in [('version',999),('unknown',True),('provisioning_generation',None),('files',[]),
                          ('capabilities',['CAP_SYS_ADMIN']),('capabilities',['CAP_CHOWN']),
                          ('workspace_storage_limit',{}),('workspace_storage_limit',None),
                          ('service',None),('activation',True),('founder_uid',999),('founder_gid',999),
                          ('approved',1),('version',True)]:
            with self.subTest(key=key,value=value):
                m=approved_manifest();m[key]=value
                with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)

    def test_unsafe_identity_fields_rejected(self):
        values=[('primary_group',g) for g in ('docker','sudo','ollama','bonup','users','systemd-journal')]
        values += [('home','/root'),('home_mode','0777'),('shell','/bin/sh'),('supplementary_groups',['docker']),
                   ('uid',0),('gid',0),('uid',1000),('gid',1000),('uid',3000),('gid',3000),
                   ('ssh_keys',['synthetic']),('password','unlocked'),('provisioning_generation',None),
                   ('username','unexpected'),('unknown',True)]
        for key,value in values:
            with self.subTest(key=key,value=value):
                m=approved_manifest();m['accounts'][1][key]=value
                with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)

    def test_unsafe_artifact_fields_and_incomplete_inventory_rejected(self):
        for key,value in [('mode','0777'),('mode','0664'),('owner','bonup-fe01'),('group','bonup-fe01'),
                          ('destination','/home/bonup/bonup-blackboard/supervisor'),('destination','/usr/lib/*'),
                          ('sha256',None),('sha256','TODO'),('sha256','0'*64),('artifact_type','symlink'),
                          ('source','/home/bonup/bonup-blackboard/tools/agent_control/supervisor.py'),('unknown',True)]:
            with self.subTest(key=key,value=value):
                m=approved_manifest();m['files'][0][key]=value
                with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)
        for action in ('remove','duplicate'):
            m=approved_manifest()
            if action=='remove':m['files'].pop()
            else:m['files'][1]=m['files'][0].copy()
            with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)

    def test_unsafe_service_fields_rejected(self):
        for key,value in [('argv',['/bin/sh']),('argv',['/usr/bin/python3','-c','untrusted']),
                          ('argv',['/home/bonup/bonup-blackboard/operator']),('argv',provision.ENTRYPOINT),
                          ('capabilities',['CAP_SYS_ADMIN']),('working_directory','/home/bonup/bonup-blackboard'),
                          ('environment_files',['/home/bonup/.env']),('environment',{'HOME':'/home/bonup'}),
                          ('user','bonup'),('unknown_systemd_property','anything')]:
            with self.subTest(key=key,value=value):
                m=approved_manifest();m['service'][key]=value
                with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)

    def test_storage_directory_socket_overlap_or_unbounded_policy_rejected(self):
        for path in ('/root','/home/bonup','/var/lib/postgresql','/srv/customers','/var/lib/bonup-agent-control/../postgresql'):
            m=approved_manifest();m['workspace_storage_limit'][1]['path']=path
            with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)
        for key,value in [('bytes',None),('bytes',0),('bytes',2**60),('inodes',0),('enforcement','TODO')]:
            m=approved_manifest();m['workspace_storage_limit'][0][key]=value
            with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)
        for section in ('directories','socket'):
            m=approved_manifest();row=m[section][0] if section=='directories' else m[section];row['mode']='0777'
            with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)

    def test_rollback_wildcards_recursion_unknown_objects_and_shell_rejected(self):
        for mutation in ('wildcard','recursive','unknown','shell','receipt','generation','incomplete'):
            with self.subTest(mutation=mutation):
                m=approved_manifest();r=m['rollback']
                if mutation=='wildcard':r['objects'][0]['path']='/usr/lib/*'
                elif mutation=='recursive':r['recursive']=True
                elif mutation=='unknown':r['objects'].append(dict(kind='directory',path='/home/bonup'))
                elif mutation=='shell':r['command']='rm -rf /'
                elif mutation=='receipt':r['verify_installation_receipt']=False
                elif mutation=='generation':r['generation']=2
                else:r['objects'].pop()
                with self.assertRaises(ValidationError):provision.validate_approved_manifest(m)
