"""Block 4 is generation/validation only: no installer or host activation."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.agent_control import installation_bundle as b
from tools.agent_control.authority import AuthenticatedContext
from tools.agent_control.types import AuthorityError,ValidationError,Role

FOUNDER=AuthenticatedContext('FOUNDER',Role.FOUNDER,1000)
BOOT='00000000-0000-4000-8000-000000000001'


def receipt(manifest):
    observations=[dict(row,device=1,inode=i+1,created=True) for i,row in enumerate(b.receipt_objects(manifest))]
    accounts=[dict(a,created=True,group_created=True) for a in b.identities()['accounts']]
    return b.make_receipt(manifest,observations,accounts=accounts,boot_id=BOOT,installed_at='2026-09-15T00:00:00Z')


def host_tests(manifest,r):
    return dict(version=1,installation_binding=b.installation_binding(manifest),receipt_digest=b.digest(r),
                results={name:'PASS' for name in b.HOST_TESTS})


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo=Path(__file__).resolve().parents[2]
        cls.original,cls.payloads=b.build(cls.repo,source_commit=b.SOURCE_COMMIT)

    def setUp(self):self.m=deepcopy(self.original)
    def invalid(self):
        b.seal(self.m)
        with self.assertRaises((AuthorityError,ValidationError)):b.validate_manifest(self.m)
    def approved(self):self.m['approved']=True;b.seal(self.m);return self.m

    def test_complete_unapproved(self):self.assertEqual(b.validate_manifest(self.m),'COMPLETE_BUT_UNAPPROVED')
    def test_controller_state_initialization_is_explicit_and_unprivileged(self):
        state=self.m['controller_state']
        self.assertEqual(state['owner'],'bonup-agentctl')
        self.assertEqual(state['schema_version'],2)
        self.assertFalse(state['automatic_startup_initialization'])
        self.assertTrue(state['before_integration_service_start'])
        self.assertEqual(state['initial_agents'],'DISABLED')
        self.assertEqual(state['initial_executions'],'EMPTY')
    def test_installed_json_size_and_depth(self):
        from tools.agent_control.protocol import bounded_json
        self.assertLess(len(b.json_bytes(self.m)),65536)
        self.assertEqual(bounded_json(b.json_bytes(self.m)),self.m)
    def test_deterministic_generation(self):
        m,p=b.build(self.repo,source_commit=b.SOURCE_COMMIT)
        self.assertEqual(m,self.m);self.assertEqual(p,self.payloads)
    def test_dependency_closure(self):
        b.verify_payloads(self.m,self.payloads)
        self.assertIn(b.PREFIX+'/tools/agent_control/operational_enrollment.py',self.payloads)
        self.assertIn(b.PREFIX+'/tools/agent_control/installation_bundle.py',self.payloads)
    def test_dependency_missing(self):
        p=dict(self.payloads);p.pop(b.PREFIX+'/tools/agent_control/installed_runtime.py')
        with self.assertRaises(ValidationError):b.verify_payloads(self.m,p)
    def test_unknown_import_rejected(self):
        p=dict(self.payloads);p[b.PREFIX+'/tools/agent_control/controller_entry.py']=b'import unapproved_runtime\n'
        with self.assertRaises(ValidationError):b.dependency_closure(p)
    def test_all_security_fields_change_digest(self):
        for field,value in (('mode','0777'),('owner','bonup-fe01'),('destination','/root/evil'),
            ('source','evil.py'),('required',False),('provisioning_generation',2),('sha256','b'*64)):
            m=deepcopy(self.m);m['artifacts'][0][field]=value
            self.assertNotEqual(b.seal(m)['bundle_digest'],self.m['bundle_digest'])
    def test_duplicate_destination(self):self.m['artifacts'][1]['destination']=self.m['artifacts'][0]['destination'];self.invalid()
    def test_missing_hash(self):self.m['artifacts'][0]['sha256']='0'*64;self.invalid()
    def test_unresolved_hash(self):self.m['artifacts'][0]['sha256']='TBD';self.invalid()
    def test_unknown_artifact_field(self):self.m['artifacts'][0]['extra']=1;self.invalid()
    def test_relative_destination(self):self.m['artifacts'][0]['destination']='relative';self.invalid()
    def test_wildcard_destination(self):self.m['artifacts'][0]['destination']='/usr/lib/*';self.invalid()
    def test_checkout_executable(self):self.m['artifacts'][0]['destination']='/home/bonup/bonup-blackboard/run';self.invalid()
    def test_worker_writable_code(self):self.m['artifacts'][0]['mode']='0666';self.invalid()
    def test_symlink_artifact_type(self):self.m['artifacts'][0]['artifact_type']='symlink';self.invalid()
    def test_source_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'real').write_text('synthetic');(p/'link').symlink_to('real')
            with self.assertRaises((OSError,ValidationError)):b.source_bytes(p,'link')
    def test_source_parent_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'real').mkdir();(p/'real/file').write_text('synthetic');(p/'link').symlink_to('real')
            with self.assertRaises((OSError,ValidationError)):b.source_bytes(p,'link/file')
    def test_source_special_file_rejected(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            os.mkfifo(Path(d)/'fifo')
            with self.assertRaises(ValidationError):b.source_bytes(d,'fifo')
    def test_generated_wrapper_tamper(self):
        a=next(a for a in self.m['artifacts'] if a['destination']==b.PREFIX+'/controller')
        a['sha256']='a'*64;self.invalid()
    def test_wrappers_isolated_and_hash_before_import(self):
        for name in ('controller','supervisor'):
            raw=b.wrapper(name).decode();compile(raw,name,'exec')
            self.assertTrue(raw.startswith('#!/usr/bin/python3 -I'))
            self.assertLess(raw.index('for path in expected_paths:'),raw.index('from tools.agent_control.'))
            self.assertNotIn('/home/bonup',raw)
            self.assertNotIn('importlib',raw)
    def test_manifest_self_hash_detached(self):
        index=b.detached_inventory(self.m)
        self.assertEqual(index['artifacts'][-1]['destination'],b.MANIFEST)
        self.assertEqual(index['artifacts'][-1]['sha256'],b.sha(b.json_bytes(self.m)))
    def test_identity_exact_candidates(self):
        rows=self.m['identity_map']['accounts'];self.assertEqual([r['uid'] for r in rows],list(range(3000,3005)))
        self.assertEqual([r['username'] for r in rows],list(b.NAMES))
    def test_no_operational_identity_in_manifest(self):
        for field in ('pid','start_ticks','boot_id','runtime_generation'):
            self.assertNotIn('"'+field+'"',b.canonical_json(self.m))
    def test_uid_collision(self):self.m['identity_map']['accounts'][1]['uid']=3000;self.invalid()
    def test_gid_collision(self):self.m['identity_map']['accounts'][1]['gid']=3000;self.invalid()
    def test_privileged_group(self):self.m['identity_map']['accounts'][1]['primary_group']='docker';self.invalid()
    def test_supplementary_group(self):self.m['identity_map']['accounts'][1]['supplementary_groups']=['sudo'];self.invalid()
    def test_interactive_shell(self):self.m['identity_map']['accounts'][1]['shell']='/bin/sh';self.invalid()
    def test_public_home(self):self.m['identity_map']['accounts'][1]['home_mode']='0777';self.invalid()
    def test_protected_directory(self):self.m['directories'][0]['path']='/home/bonup';self.invalid()
    def test_unsafe_directory_mode(self):self.m['directories'][0]['mode']='0777';self.invalid()
    def test_worker_socket_access(self):self.m['sockets'][2]['group']='bonup-fe01';self.invalid()
    def test_controller_capabilities(self):self.m['services']['controller']['capabilities']=['CAP_KILL'];self.invalid()
    def test_sys_admin(self):self.m['services']['supervisor']['capabilities'].append('CAP_SYS_ADMIN');self.invalid()
    def test_dac_override(self):self.m['capabilities']['supervisor'].append('CAP_DAC_OVERRIDE');self.invalid()
    def test_other_capability(self):self.m['capabilities']['supervisor'].append('CAP_NET_ADMIN');self.invalid()
    def test_shell_execstart(self):self.m['services']['supervisor']['argv']=['/bin/sh'];self.invalid()
    def test_repository_execstart(self):self.m['services']['controller']['argv']=['/home/bonup/bonup-blackboard/controller'];self.invalid()
    def test_founder_home(self):self.m['services']['supervisor']['environment']['HOME']='/home/bonup';self.invalid()
    def test_environmentfile(self):self.m['services']['supervisor']['environment_files']=['/tmp/evil'];self.invalid()
    def test_units_match_capability_policy(self):
        for name,raw in b.units().items():
            self.assertNotIn('CAP_SYS_ADMIN',raw);self.assertNotIn('CAP_DAC_OVERRIDE',raw)
            self.assertNotIn('RestrictNamespaces=yes',raw);self.assertNotIn('EnvironmentFile=',raw)
            self.assertNotIn('/home/bonup',raw)
        self.assertIn('DelegateSubgroup=supervisor',b.units()['bonup-agent-supervisor.service'])
    def test_limits_cannot_enlarge(self):self.m['resource_profile']['memory_bytes']*=2;self.invalid()
    def test_storage_cannot_resize(self):self.m['storage']['supervisor_dynamic_mount']=True;self.invalid()
    def test_unknown_top_field(self):self.m['founder']=True;self.invalid()
    def test_bad_version(self):self.m['version']=999;self.invalid()
    def test_hash_mismatch(self):
        self.m['bundle_digest']='a'*64
        with self.assertRaises(ValidationError):b.validate_manifest(self.m)
    def test_install_denied_unapproved(self):
        with self.assertRaises(AuthorityError):b.installation_plan(self.m,self.payloads,self.preflight(),context=FOUNDER)
    def preflight(self):
        return dict(version=1,source_commit=self.m['source_commit'],bundle_digest=self.m['bundle_digest'],
            checks={k:True for k in self.m['host_preflight']},uid_collisions=[],gid_collisions=[],account_collisions=[],target_conflicts=[])
    def test_install_plan_requires_approval_no_executor(self):
        self.approved();plan=b.installation_plan(self.m,self.payloads,self.preflight(),context=FOUNDER)
        self.assertFalse(plan['automatic_service_start']);self.assertFalse(plan['execute_checkout'])
        self.assertFalse(plan['automatic_approval']);self.assertFalse(hasattr(b,'execute_installation'))
        self.assertEqual(len(plan['copy_map']),57)
    def test_wrong_source_commit(self):
        self.approved();p=self.preflight();p['source_commit']='a'*40
        with self.assertRaises(AuthorityError):b.installation_plan(self.m,self.payloads,p,context=FOUNDER)
    def test_install_hash_mismatch(self):
        self.approved();p=dict(self.payloads);p[next(iter(p))]=b'changed'
        with self.assertRaises(ValidationError):b.installation_plan(self.m,p,self.preflight(),context=FOUNDER)
    def test_preflight_identity_collision(self):
        self.approved();p=self.preflight();p['uid_collisions']=[3001]
        with self.assertRaises(AuthorityError):b.installation_plan(self.m,self.payloads,p,context=FOUNDER)
    def test_preflight_target_conflict(self):
        self.approved();p=self.preflight();p['target_conflicts']=[b.PREFIX]
        with self.assertRaises(AuthorityError):b.installation_plan(self.m,self.payloads,p,context=FOUNDER)
    def test_no_model_founder_claim(self):
        self.approved()
        with self.assertRaises(AuthorityError):b.installation_plan(self.m,self.payloads,self.preflight(),context={'founder':True})
    def test_no_root_as_founder(self):
        self.approved()
        with self.assertRaises(AuthorityError):b.installation_plan(self.m,self.payloads,self.preflight(),context=AuthenticatedContext('FOUNDER',Role.FOUNDER,0))
    def test_receipt_is_complete_bound_evidence(self):
        self.approved();r=receipt(self.m);b.validate_receipt(self.m,r)
        self.assertEqual(r,receipt(self.m));self.assertEqual(len(r['objects']),len(b.receipt_objects(self.m)))
    def test_receipt_identity_change(self):
        self.approved();r=receipt(self.m);r['accounts'][1]['uid']=0
        with self.assertRaises(ValidationError):b.validate_receipt(self.m,r)
    def test_rollback_exact_object(self):
        self.approved();r=receipt(self.m);o=r['objects'][0]
        self.assertEqual(b.rollback_file(self.m,r,o['path'],o,cleanup_confirmed=True)['action'],'UNLINK_VERIFIED_FILE')
    def test_rollback_wildcard(self):
        self.approved();r=receipt(self.m)
        with self.assertRaises(AuthorityError):b.rollback_file(self.m,r,'/usr/lib/*',{},cleanup_confirmed=True)
    def test_rollback_protected(self):
        self.approved();r=receipt(self.m)
        with self.assertRaises(AuthorityError):b.rollback_file(self.m,r,'/home/bonup',{},cleanup_confirmed=True)
    def test_rollback_substituted_inode(self):
        self.approved();r=receipt(self.m);o=dict(r['objects'][0],inode=999999)
        with self.assertRaises(ValidationError):b.rollback_file(self.m,r,o['path'],o,cleanup_confirmed=True)
    def test_rollback_recursive(self):self.m['rollback']['recursive']=True;self.invalid()
    def test_rollback_without_cleanup(self):
        self.approved();r=receipt(self.m);o=r['objects'][0]
        with self.assertRaises(AuthorityError):b.rollback_file(self.m,r,o['path'],o,cleanup_confirmed=False)
    def test_activation_false_denies(self):
        self.approved();r=receipt(self.m)
        with self.assertRaises(AuthorityError):b.require_activation(self.m,r,host_tests(self.m,r),context=FOUNDER)
    def test_host_evidence_without_founder_denies(self):
        self.approved();r=receipt(self.m);self.m['activation']=True;b.seal(self.m)
        with self.assertRaises(AuthorityError):b.require_activation(self.m,r,host_tests(self.m,r),context=None)
    def test_founder_without_host_tests_denies(self):
        self.approved();r=receipt(self.m);self.m['activation']=True;b.seal(self.m)
        with self.assertRaises(ValidationError):b.require_activation(self.m,r,{},context=FOUNDER)
    def test_one_missing_host_test_denies(self):
        self.approved();r=receipt(self.m);self.m['activation']=True;b.seal(self.m)
        e=host_tests(self.m,r);e['results'].pop(b.HOST_TESTS[0])
        with self.assertRaises(ValidationError):b.require_activation(self.m,r,e,context=FOUNDER)
    def test_all_activation_prerequisites(self):
        self.approved();r=receipt(self.m);self.m['activation']=True;b.seal(self.m)
        self.assertEqual(b.require_activation(self.m,r,host_tests(self.m,r),context=FOUNDER),b.installation_binding(self.m))
    def test_receipt_does_not_authorize_service_start(self):
        self.approved();r=receipt(self.m)
        with self.assertRaises(AuthorityError):b.runtime_permission(self.m,r)
    def test_integration_service_permission_does_not_activate(self):
        self.approved();r=receipt(self.m);self.m['integration_services_approved']=True;b.seal(self.m)
        self.assertEqual(b.runtime_permission(self.m,r),'INTEGRATION_SERVICES_ONLY_INTAKE_DISABLED')
        with self.assertRaises(AuthorityError):b.require_activation(self.m,r,host_tests(self.m,r),context=FOUNDER)
    def test_missing_enrollment_still_denies_admission(self):
        from tools.agent_control.operational_enrollment import Admission
        self.test_all_activation_prerequisites()
        a=Admission();a.starting()
        with self.assertRaises(AuthorityError):a.require_open()
    def test_runtime_loader_accepts_complete_integration_contract(self):
        from tools.agent_control.installed_config import validate_activation
        self.approved();r=receipt(self.m);self.m['integration_services_approved']=True;b.seal(self.m)
        self.assertEqual(validate_activation(self.m,b.identities(),b.configurations()['controller'],
            component='controller',receipt=r),b.digest(self.m))
