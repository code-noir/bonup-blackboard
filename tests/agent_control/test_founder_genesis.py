"""Synthetic offline ceremony only. No founder production key or host writes."""
import base64
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import sqlite3
import tempfile
from pathlib import Path
import unittest
from uuid import uuid4

from test_founder_root import PUBLIC, sign, BOOT
from test_authority_repairs import successor_fixture
from tools.agent_control import founder_genesis as g, successor_config as sc
from tools.agent_control.authority_installation import InstallationBinding, approval_projection, verify_receipt
from tools.agent_control.founder_session import FounderSessions
from tools.agent_control.founder_crypto import PURPOSES
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import AuthorityError, ValidationError

OTHER_PUBLIC=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')


class SyntheticCeremony(g.OfflineCeremony):
    def confirm(self, challenge, full_digest, comparison_code):
        assert digest(challenge)==full_digest and comparison_code==full_digest[:16]
        return full_digest


def raw(value):return canonical_json(value).encode()
def sha(value):return hashlib.sha256(raw(value)).hexdigest()


class GenesisTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        # TEST ONLY independent offline trust-domain initialization.
        self.db.execute('CREATE TABLE genesis(domain TEXT PRIMARY KEY,state TEXT NOT NULL,evidence TEXT NOT NULL)')
        self.db.execute('INSERT INTO genesis VALUES (?,?,?)',(g.DOMAIN,'VIRGIN','{}'))
        self.db.commit()
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.events=[]
        self.configs,self.attest,self.ids,self.receipt,self.candidate,self.approved=successor_fixture()
        for config in self.configs.values():
            config['version']=4
            p=config['authority']
            for name in ('root_id','root_digest','root_generation','algorithm','purposes','openssl'):del p[name]
            p.update(version=2,founder_root_policy=g.policy())
        self.candidate.update(founder_root_policy=g.policy(),
            configuration_digests={k:digest(v) for k,v in self.configs.items()},
            authority_digest=digest(self.configs['controller']['authority']))
        self.candidate['predecessor'] = dict(provisioning_generation=1,
            candidate_manifest_digest='b'*64, candidate_bundle_digest='c'*64,
            source_commit='d'*40, product_scope_digest='e'*64,
            runtime_modules_digest='f'*64)
        self.candidate['bundle_digest']=digest({k:v for k,v in self.candidate.items() if k!='bundle_digest'})
        self.encoded=base64.b64encode(PUBLIC).decode()
        self.service=self.service_new()

    def service_new(self,ceremony=None):
        return g.Genesis(g.GenesisLedger(self.db),validate_complete=self.valid,
            ceremony=SyntheticCeremony() if ceremony is None else ceremony,
            audit=lambda k,v:self.events.append((k,v)),clock=lambda:self.now)

    def valid(self,value):
        # Exact synthetic candidate fixture; production must use G2 validator.
        if value != self.candidate:raise AuthorityError('Candidate not reviewed.')

    def bind(self):
        self.service.propose(raw(self.candidate),self.encoded)
        return self.service.finish(raw(self.candidate))

    def installation(self):
        record=self.bind()
        approved=g.proposed_approval(raw(self.candidate),self.valid,record)['installation_manifest']
        binding=InstallationBinding(self.candidate['source_commit'],sha(self.candidate),
            self.candidate['bundle_digest'],sha(approved),'e'*64,2,record['binding_digest'],
            self.candidate['predecessor']['candidate_manifest_digest'])
        receipt=dict(version=2,binding=binding.data(),installation_id=str(uuid4()),activation=False,
            verified_artifacts_digest='e'*64,genesis=g.receipt_projection(record))
        self.attest.update(binding=binding.data(),receipt_digest=digest(receipt),
            configuration_digests=self.candidate['configuration_digests'],authority_digest=self.candidate['authority_digest'])
        self.attest['bundle_digest']=digest({k:v for k,v in self.attest.items() if k!='bundle_digest'})
        return record,binding,receipt,approved

    def test_unbound_complete(self):
        self.assertEqual(g.state(raw(self.candidate),self.valid),'COMPLETE_BUT_ROOT_UNBOUND')

    def test_no_fake_key_in_policy(self):
        self.assertNotIn('public_key',g.policy())

    def test_bound_state_candidate_unchanged(self):
        before=sha(self.candidate);record=self.bind()
        self.assertEqual(g.state(raw(self.candidate),self.valid,binding=record),'ROOT_BOUND_BUT_UNAPPROVED')
        self.assertEqual(before,sha(self.candidate))
        self.assertFalse(record['approved']);self.assertFalse(record['activation'])

    def test_default_production_adapter_denies(self):
        self.service=self.service_new(g.OfflineCeremony())
        self.service.propose(raw(self.candidate),self.encoded)
        with self.assertRaises(AuthorityError):self.service.finish(raw(self.candidate))

    def test_json_root_uid_not_confirmation(self):
        for value in ({'approved':True},{'uid':0},{'uid':1000},True):
            with self.subTest(value=value),self.assertRaises(AuthorityError):self.service_new(value)

    def test_wrong_confirmation(self):
        class Wrong(SyntheticCeremony):
            def confirm(self,*args):return '0'*64
        self.service=self.service_new(Wrong())
        with self.assertRaises(AuthorityError):self.bind()

    def test_expiry(self):
        self.service.propose(raw(self.candidate),self.encoded)
        self.now+=timedelta(seconds=300)
        with self.assertRaises(AuthorityError):self.service.finish(raw(self.candidate))

    def test_monotonic_expiry_cannot_be_revived_by_wall_clock(self):
        ticks=[0]
        self.service.elapsed=lambda:ticks[0]
        self.service.propose(raw(self.candidate),self.encoded)
        ticks[0]=301
        with self.assertRaises(AuthorityError):self.service.finish(raw(self.candidate))

    def test_replayed_finish(self):
        self.bind()
        with self.assertRaises(AuthorityError):self.service.finish(raw(self.candidate))

    def test_restart_reboot_cannot_reenable(self):
        self.bind()
        for key in (self.encoded,base64.b64encode(OTHER_PUBLIC).decode()):
            service=self.service_new()
            with self.assertRaises(AuthorityError):service.propose(raw(self.candidate),key)

    def test_missing_durable_marker_denied(self):
        self.db.execute('DELETE FROM genesis');self.db.commit()
        with self.assertRaises(AuthorityError):self.service.propose(raw(self.candidate),self.encoded)

    def test_previous_receipt_evidence_denied(self):
        self.db.execute("UPDATE genesis SET state='INSTALLED'");self.db.commit()
        with self.assertRaises(AuthorityError):self.bind()

    def test_durable_consumption_before_audit_failure(self):
        self.service.propose(raw(self.candidate),self.encoded)
        def fail(*args):raise OSError('synthetic audit failure')
        self.service.audit=fail
        with self.assertRaises(OSError):self.service.finish(raw(self.candidate))
        with self.assertRaises(AuthorityError):self.service_new().propose(raw(self.candidate),self.encoded)

    def test_malformed_private_multiple_keys_denied(self):
        for key in ('',self.encoded+'\n',self.encoded*2,'-----BEGIN PRIVATE KEY-----',base64.b64encode(bytes(32)).decode()):
            with self.subTest(key=key),self.assertRaises((ValidationError,AuthorityError)):g.public_root(key)

    def test_fingerprint_deterministic(self):
        self.assertEqual(g.public_root(self.encoded).key_id,hashlib.sha256(PUBLIC).hexdigest())
        self.assertNotEqual(g.public_root(self.encoded).key_id,g.public_root(base64.b64encode(OTHER_PUBLIC).decode()).key_id)

    def test_candidate_mismatch(self):
        self.service.propose(raw(self.candidate),self.encoded)
        changed=dict(self.candidate,source_commit='b'*40)
        with self.assertRaises(AuthorityError):self.service.finish(raw(changed))

    def test_binding_mutations_denied(self):
        record=self.bind();identity=g.candidate_identity(raw(self.candidate),self.valid)
        for key,value in dict(source_commit='b'*40,candidate_bundle_digest='f'*64,
                provisioning_generation=1,founder_root_policy_digest='f'*64,algorithm='RSA',
                key_id='f'*64,root_generation=2,activation=True).items():
            changed=dict(record,**{key:value})
            changed['binding_digest']=digest({k:v for k,v in changed.items() if k!='binding_digest'})
            with self.subTest(key=key),self.assertRaises((AuthorityError,ValidationError)):
                g.validate_binding(changed,identity)

    def test_approval_requires_binding(self):
        with self.assertRaises(AuthorityError):g.proposed_approval(raw(self.candidate),self.valid,None)

    def test_approval_exact_projection(self):
        record,binding,receipt,approved=self.installation()
        approval_projection(raw(self.candidate),raw(approved),binding)
        self.assertFalse(approved['activation'])
        for key in ('authority_digest','founder_root_binding_digest'):
            changed=dict(approved,**{key:'f'*64})
            changed['bundle_digest']=digest({k:v for k,v in changed.items() if k!='bundle_digest'})
            altered=InstallationBinding(binding.source_commit,binding.candidate_manifest_digest,
                binding.candidate_bundle_digest,sha(changed),binding.approved_inventory_digest,2,
                record['binding_digest'],binding.predecessor_candidate_manifest_digest)
            with self.assertRaises(AuthorityError):approval_projection(raw(self.candidate),raw(changed),altered)

    def test_receipt_retains_genesis(self):
        record,binding,receipt,_=self.installation()
        self.assertEqual(verify_receipt(raw(receipt),binding,digest(receipt)).binding,binding)
        receipt['genesis']['founder_root_binding_digest']='f'*64
        with self.assertRaises(AuthorityError):verify_receipt(raw(receipt),binding,digest(receipt))

    def test_successor_exact_binding_and_missing_key(self):
        record,binding,receipt,_=self.installation()
        root=g.public_root(self.encoded)
        for component in ('controller','supervisor'):
            sc.validate(self.configs[component],self.attest,self.ids,receipt,root,component=component,genesis=record)
            for bad in (None,dict(record,binding_digest='f'*64)):
                with self.assertRaises(AuthorityError):
                    sc.validate(self.configs[component],self.attest,self.ids,receipt,root,component=component,genesis=bad)

    def test_wrong_installed_root(self):
        record,_,receipt,_=self.installation()
        root=g.public_root(base64.b64encode(OTHER_PUBLIC).decode())
        with self.assertRaises(AuthorityError):sc.validate(self.configs['controller'],self.attest,self.ids,
            receipt,root,component='controller',genesis=record)

    def test_signature_and_purpose_separation(self):
        record,binding,_,_=self.installation()
        root=g.public_root(self.encoded)
        peer=PeerIdentity(1000,1000,123)
        process=ProcessIdentity(BOOT,123,100)
        sessions=FounderSessions(root,observe=lambda:(peer,process),audit=lambda *a:None)
        challenge=sessions.issue_binding(PURPOSES[0],binding.data())
        token=sessions.submit(dict(challenge_id=digest(challenge),signature=base64.b64encode(sign(raw(challenge))).decode()))
        with self.assertRaises(AuthorityError):sessions.consume(token,PURPOSES[1],binding.data())
        with self.assertRaises(AuthorityError):sessions.issue_binding('FOUNDER_ACTIVATION_APPROVAL',binding.data())

    def test_persisted_ledger_new_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'synthetic-ledger.sqlite3')
            disk=sqlite3.connect(path)
            try:
                self.db.backup(disk)
                self.service.ledger=g.GenesisLedger(disk)
                self.bind()
            finally:disk.close()
            restored=sqlite3.connect(path)
            try:
                with self.assertRaises(AuthorityError):g.GenesisLedger(restored).require_virgin()
            finally:restored.close()

    def test_two_outstanding_ceremonies_only_one_consumes(self):
        other=self.service_new()
        self.service.propose(raw(self.candidate),self.encoded)
        other.propose(raw(self.candidate),self.encoded)
        self.service.finish(raw(self.candidate))
        with self.assertRaises(AuthorityError):other.finish(raw(self.candidate))

    def test_short_code_cannot_confirm(self):
        class Short(SyntheticCeremony):
            def confirm(self,challenge,full,short):return short
        self.service=self.service_new(Short())
        with self.assertRaises(AuthorityError):self.bind()

    def test_confirmation_expiring_during_ceremony(self):
        owner=self
        class Slow(SyntheticCeremony):
            def confirm(self,challenge,full,short):
                owner.now+=timedelta(seconds=301)
                return full
        self.service=self.service_new(Slow())
        with self.assertRaises(AuthorityError):self.bind()

    def test_historical_cannot_receive_binding(self):
        with self.assertRaises(ValidationError):InstallationBinding('a'*40,'a'*64,'b'*64,'c'*64,'d'*64,1,'e'*64)

    def test_unbound_cannot_approve_even_consistent_hashes(self):
        approved=dict(self.candidate,approved=True)
        approved['bundle_digest']=digest({k:v for k,v in approved.items() if k!='bundle_digest'})
        binding=InstallationBinding('a'*40,sha(self.candidate),self.candidate['bundle_digest'],sha(approved),'e'*64,2,
            predecessor_candidate_manifest_digest=self.candidate['predecessor']['candidate_manifest_digest'])
        with self.assertRaises(AuthorityError):approval_projection(raw(self.candidate),raw(approved),binding)

    def test_declared_complete_is_insufficient(self):
        service=g.Genesis(g.GenesisLedger(self.db),validate_complete=lambda v:(_ for _ in ()).throw(AuthorityError('incomplete')),
            ceremony=SyntheticCeremony(),audit=lambda *a:None)
        with self.assertRaises(AuthorityError):service.propose(raw(self.candidate),self.encoded)

    def test_no_force_auto_option(self):
        with self.assertRaises(TypeError):self.service.finish(raw(self.candidate),force=True)

    def test_key_cannot_authorize_own_genesis(self):
        self.service=self.service_new(g.OfflineCeremony())
        challenge=self.service.propose(raw(self.candidate),self.encoded)
        with self.assertRaises(TypeError):self.service.finish(raw(self.candidate),signature='synthetic')
        self.assertEqual(challenge['purpose'],'FOUNDER_ROOT_GENESIS')

    def test_genesis_audit_is_bounded_evidence_only(self):
        record=self.bind()
        self.assertEqual([e[0] for e in self.events],['GENESIS_PROPOSAL_CREATED','GENESIS_CEREMONY_CONFIRMED','GENESIS_BINDING_CREATED'])
        self.assertNotIn(self.encoded,canonical_json([list(row) for row in self.events]))
        self.assertNotIn('signature',canonical_json(record))
