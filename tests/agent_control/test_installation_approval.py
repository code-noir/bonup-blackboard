"""Offline approval transformation and authority-boundary regression tests."""
from copy import deepcopy
from pathlib import Path
import unittest

from tools.agent_control import installation_approval as a
from tools.agent_control import installation_bundle as b
from tools.agent_control.authority import AuthenticatedContext
from tools.agent_control.types import AuthorityError, ValidationError, Role

FOUNDER = AuthenticatedContext('FOUNDER', Role.FOUNDER, 1000)  # synthetic trusted-boundary fixture
BOOT = '00000000-0000-4000-8000-000000000001'


class ApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = Path(__file__).resolve().parents[2]/'docs/agent-control/review/m3-generation-1'
        cls.raw = (cls.review/'payload'/b.MANIFEST.lstrip('/')).read_bytes()
        cls.base = a.propose(cls.raw)
        cls.payload = {r['destination']:(cls.review/'payload'/r['destination'].lstrip('/')).read_bytes()
                       for r in cls.base['installation_manifest']['artifacts']}

    def setUp(self):
        self.p = deepcopy(self.base)

    def decision(self):
        return a.approval_record(self.raw,self.p,context=FOUNDER,approval_id=BOOT,
                                 approved_at='2026-09-15T00:00:00Z')

    def receipt(self):
        m=self.p['installation_manifest']
        rows=[dict(row,device=1,inode=i+1,created=True) for i,row in enumerate(b.receipt_objects(m))]
        accounts=[dict(row,created=True,group_created=True) for row in b.identities()['accounts']]
        return a.make_receipt(self.raw,self.p,self.decision(),rows,context=FOUNDER,
                             accounts=accounts,boot_id=BOOT,installed_at='2026-09-15T00:00:01Z')

    def reject(self):
        with self.assertRaises((AuthorityError,ValidationError)):
            a.validate_proposal(self.raw,self.p)

    def test_candidate_bytes_remain_identical(self):
        before=self.raw
        a.propose(self.raw)
        self.assertEqual(self.raw,before)
        self.assertEqual((self.review/'payload'/b.MANIFEST.lstrip('/')).read_bytes(),before)
        self.assertEqual(b.sha(before),a.CANDIDATE_SHA256)

    def test_candidate_is_unapproved(self):
        self.assertFalse(a.candidate(self.raw)['approved'])

    def test_candidate_is_inactive(self):
        self.assertFalse(a.candidate(self.raw)['activation'])

    def test_only_approval_and_derived_digest_change(self):
        original=a.candidate(self.raw); transformed=self.p['installation_manifest']
        self.assertEqual({k for k in original if original[k]!=transformed[k]}, {'approved','bundle_digest'})
        self.assertTrue(transformed['approved'])
        self.assertFalse(transformed['activation'])
        self.assertFalse(transformed['integration_services_approved'])

    def test_deterministic_non_authoritative_proposal(self):
        self.assertEqual(a.propose(self.raw),self.p)
        self.assertEqual(self.p['state'],'PROPOSED_APPROVAL_STAGE')
        with self.assertRaises(AuthorityError):
            a.require_approval(self.raw,self.p,None,context=FOUNDER)

    def test_generated_json_cannot_mint_founder_context(self):
        with self.assertRaises(AuthorityError):
            a.require_approval(self.raw,self.p,self.decision(),context={'actor_id':'FOUNDER','uid':1000})

    def test_root_cannot_approve_as_founder(self):
        with self.assertRaises(AuthorityError):
            a.approval_record(self.raw,self.p,context=AuthenticatedContext('FOUNDER',Role.FOUNDER,0),
                              approval_id=BOOT,approved_at='2026-09-15T00:00:00Z')

    def test_explicit_approval_binding(self):
        d=self.decision();a.require_approval(self.raw,self.p,d,context=FOUNDER)
        self.assertEqual(d['binding'],self.p['binding'])
        self.assertFalse(d['activation'])
        self.assertFalse(d['integration_services_approved'])

    def test_forged_decision_activation_rejected(self):
        d=self.decision();d['activation']=True
        with self.assertRaises(ValidationError):a.require_approval(self.raw,self.p,d,context=FOUNDER)

    def test_replayed_decision_other_proposal_rejected(self):
        d=self.decision();d['proposal_digest']='a'*64
        with self.assertRaises(ValidationError):a.require_approval(self.raw,self.p,d,context=FOUNDER)

    def test_noncanonical_candidate_bytes_rejected(self):
        with self.assertRaises(ValidationError):a.propose(self.raw+b'\n')

    def test_56_unchanged_and_one_manifest_replacement(self):
        old=b.detached_inventory(a.candidate(self.raw))['artifacts']
        new=self.p['installation_inventory']['artifacts']
        self.assertEqual(len(new),57)
        self.assertEqual(sum(x==y for x,y in zip(old,new)),56)
        self.assertEqual([x['destination'] for x,y in zip(old,new) if x!=y],[b.MANIFEST])

    def test_approved_digest_separate_and_receipt_compatible(self):
        self.assertEqual(self.p['binding']['approved_manifest_digest'],
                         'da3124871d15fa64861c24e3a91bde66a9968029446d24de3ff2d54deb8836fe')
        self.assertNotEqual(self.p['binding']['approved_manifest_digest'],a.CANDIDATE_SHA256)
        self.assertEqual(self.p['binding']['approved_inventory_digest'],b.sha(b.json_bytes(self.p['installation_inventory'])))

    def test_installer_rejects_original_manifest_bytes(self):
        payload=dict(self.payload);payload[b.MANIFEST]=self.raw
        with self.assertRaises(ValidationError):a.verify_installation_payloads(self.raw,self.p,payload)

    def test_installer_accepts_exact_approved_inventory(self):
        payload=dict(self.payload);payload[b.MANIFEST]=b.json_bytes(self.p['installation_manifest'])
        a.verify_installation_payloads(self.raw,self.p,payload)

    def test_second_changed_payload_rejected(self):
        payload=dict(self.payload);payload[b.MANIFEST]=b.json_bytes(self.p['installation_manifest'])
        key=next(iter(self.payload));payload[key]+=b'\n'
        with self.assertRaises(ValidationError):a.verify_installation_payloads(self.raw,self.p,payload)

    def test_installation_plan_requires_decision_and_exact_commit(self):
        m=self.p['installation_manifest']
        payload=dict(self.payload);payload[b.MANIFEST]=b.json_bytes(m)
        preflight=dict(review_source_commit=a.SOURCE_COMMIT,candidate_preflight=dict(
            version=1,source_commit=m['source_commit'],bundle_digest=m['bundle_digest'],
            checks={k:True for k in m['host_preflight']},uid_collisions=[],gid_collisions=[],
            account_collisions=[],target_conflicts=[]))
        plan=a.installation_plan(self.raw,self.p,self.decision(),payload,preflight,context=FOUNDER)
        self.assertFalse(plan['activation'])
        self.assertFalse(plan['plan']['automatic_service_start'])
        with self.assertRaises(AuthorityError):
            a.installation_plan(self.raw,self.p,None,payload,preflight,context=FOUNDER)
        preflight['review_source_commit']='b'*40
        with self.assertRaises(AuthorityError):
            a.installation_plan(self.raw,self.p,self.decision(),payload,preflight,context=FOUNDER)

    def test_receipt_records_candidate_and_approved_identity(self):
        r=self.receipt();a.validate_receipt(self.raw,self.p,self.decision(),r,context=FOUNDER)
        self.assertEqual(r['binding'],self.p['binding'])
        self.assertEqual(r['binding']['source_commit'],a.SOURCE_COMMIT)
        self.assertEqual(r['binding']['candidate_manifest_digest'],a.CANDIDATE_SHA256)
        self.assertEqual(r['binding']['candidate_bundle_digest'],a.CANDIDATE_BUNDLE)
        self.assertFalse(r['activation_authority'])
        self.assertEqual(len([x for x in r['runtime_receipt']['objects'] if x['kind']=='file']),57)

    def test_receipt_candidate_link_cannot_be_removed(self):
        r=self.receipt();del r['binding']['candidate_manifest_digest']
        with self.assertRaises(ValidationError):a.validate_receipt(self.raw,self.p,self.decision(),r,context=FOUNDER)

    def test_runtime_projection_alone_not_full_receipt(self):
        with self.assertRaises(ValidationError):
            a.validate_receipt(self.raw,self.p,self.decision(),self.receipt()['runtime_receipt'],context=FOUNDER)

    def test_installation_approval_without_host_tests_cannot_activate(self):
        with self.assertRaises((AuthorityError,ValidationError)):
            a.require_activation(self.raw,self.p,self.decision(),self.receipt(),None,context=FOUNDER)

    def test_host_tests_plus_install_approval_cannot_activate(self):
        r=self.receipt();runtime=r['runtime_receipt'];m=self.p['installation_manifest']
        evidence=dict(version=1,installation_binding=b.installation_binding(m),receipt_digest=b.digest(runtime),
                      results={name:'PASS' for name in b.HOST_TESTS})
        with self.assertRaises(AuthorityError):
            a.require_activation(self.raw,self.p,self.decision(),r,evidence,context=FOUNDER)


def mutation_test(path, value):
    def run(self):
        target=self.p
        for key in path[:-1]:target=target[key]
        target[path[-1]]=value
        # Rehashing cannot authorize a policy change.
        b.seal(self.p['installation_manifest'])
        self.reject()
    return run


for name,path,value in (
    ('activation',['installation_manifest','activation'],True),
    ('identity',['installation_manifest','identity_map','accounts',1,'username'],'evil'),
    ('uid',['installation_manifest','identity_map','accounts',1,'uid'],0),
    ('gid',['installation_manifest','identity_map','accounts',1,'gid'],0),
    ('capability',['installation_manifest','capabilities','supervisor'],['CAP_SYS_ADMIN']),
    ('artifact_hash',['installation_manifest','artifacts',0,'sha256'],'b'*64),
    ('service',['installation_manifest','services','supervisor','argv'],['/bin/sh']),
    ('storage',['installation_manifest','storage','workspace_bytes'],1),
    ('resource',['installation_manifest','resource_profile','memory_bytes'],1),
    ('rollback',['installation_manifest','rollback','recursive'],True),
    ('host_tests',['installation_manifest','host_test_required'],[]),
    ('enrollment',['installation_manifest','operational_enrollment','reconciliation_required'],False),
    ('candidate_binding',['binding','candidate_manifest_digest'],'b'*64),
    ('source_binding',['binding','source_commit'],'b'*40),
    ('bundle_binding',['binding','candidate_bundle_digest'],'b'*64),
    ('generation',['binding','provisioning_generation'],2),
    ('second_inventory_change',['installation_inventory','artifacts',0,'sha256'],'b'*64),
    ('owner',['installation_inventory','artifacts',0,'owner'],'bonup-fe01'),
    ('mode',['installation_inventory','artifacts',0,'mode'],'0777'),
    ('destination',['installation_inventory','artifacts',0,'destination'],'/root/evil'),
    ('services_approval',['installation_manifest','integration_services_approved'],True),
    ('proposed_state',['state'],'APPROVED'),
):
    setattr(ApprovalTests,'test_reject_'+name,mutation_test(path,value))
