"""Synthetic public vectors and constructed signatures; never production keys."""
import base64
import hashlib
import os
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from test_founder_root import PUBLIC,ROOT,sign
import test_founder_genesis as genesis_tests
from tools.agent_control import founder_key_validation as v
from tools.agent_control import founder_genesis as g
from tools.agent_control.founder_crypto import FounderRoot,OpenSSLVerifier,parse_founder_root,sealed,SPKI_PREFIX
from tools.agent_control.founder_session import FounderSessions
from tools.agent_control.types import AuthorityError,ValidationError

BAD=v.ORDER_TWO
MESSAGE=b'synthetic-genesis-review-2'
FORGED_SIGNATURE=b'\x01'+bytes(63)


class PointTests(unittest.TestCase):
    def test_valid_key_and_signature(self):
        v.validate_public_key(PUBLIC)
        OpenSSLVerifier().verify(ROOT,b'synthetic',sign(b'synthetic'))

    def test_feature_preflight(self):v.preflight()

    def test_invalid_point_matrix(self):
        # Identity (order 1), y=-1 (order 2), y=0/x-sign variants (order 4),
        # and noncanonical y=p. No handwritten point operations are used.
        for raw in (b'\x01'+bytes(31),BAD,bytes(32),bytes(31)+b'\x80',bytes.fromhex('ed'+'ff'*30+'7f')):
            with self.subTest(raw=raw.hex()),self.assertRaises(AuthorityError):v.validate_public_key(raw)

    def test_strict_raw_length(self):
        for raw in (b'',bytes(31),bytes(33),bytearray(PUBLIC),'x'*32):
            with self.subTest(raw=type(raw)),self.assertRaises(ValidationError):v.validate_public_key(raw)

    def test_genesis_rejects_order_two_before_fingerprinting(self):
        with patch.object(g.hashlib,'sha256',side_effect=AssertionError('fingerprint too early')):
            with self.assertRaises(AuthorityError):g.public_root(base64.b64encode(BAD).decode())

    def test_root_constructor_rejects_order_two(self):
        with self.assertRaises(AuthorityError):FounderRoot('invalid',BAD,1)

    def test_verifier_revalidates_even_preexisting_root(self):
        root=object.__new__(FounderRoot)
        object.__setattr__(root,'public_key',BAD)
        with patch('tools.agent_control.founder_crypto.subprocess.run') as process:
            with self.assertRaises(AuthorityError):OpenSSLVerifier().verify(root,MESSAGE,FORGED_SIGNATURE)
            process.assert_not_called()

    def test_invalid_root_cannot_create_session(self):
        root=object.__new__(FounderRoot)
        object.__setattr__(root,'public_key',BAD)
        with self.assertRaises(AuthorityError):FounderSessions(root,observe=lambda:None,audit=lambda *a:None)

    def test_exact_openssl_bypass_fixture(self):
        # Preserve the reviewed upstream behavior, without any signing/private key.
        fds=[sealed(raw) for raw in (SPKI_PREFIX+BAD,MESSAGE,FORGED_SIGNATURE)]
        try:
            result=subprocess.run(('/usr/bin/openssl','pkeyutl','-verify','-pubin','-keyform','DER',
                '-inkey',f'/proc/self/fd/{fds[0]}','-rawin','-in',f'/proc/self/fd/{fds[1]}',
                '-sigfile',f'/proc/self/fd/{fds[2]}'),pass_fds=tuple(fds),close_fds=True,
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                shell=False,timeout=2,cwd='/',env={'LANG':'C','LC_ALL':'C','OPENSSL_CONF':'/dev/null'})
            # OpenSSL hardening in a later patch may also reject: either outcome
            # must leave the independent bonUP validity gate closed.
            self.assertIn(result.returncode,(0,1))
            with self.assertRaises(AuthorityError):v.validate_public_key(BAD)
        finally:
            for fd in fds:os.close(fd)

    def test_installed_parser_revalidates(self):
        expected=g.public_artifact(g.public_root(base64.b64encode(PUBLIC).decode()))
        self.assertEqual(parse_founder_root(expected).public_key,PUBLIC)
        for changed in (dict(expected,public_key=base64.b64encode(BAD).decode(),key_id=hashlib.sha256(BAD).hexdigest()),
                        dict(expected,key_id='f'*64),dict(expected,algorithm='RSA'),
                        dict(expected,generation=2),dict(expected,generation=True),
                        dict(expected,public_key=expected['public_key']+'\n')):
            with self.subTest(changed=changed),self.assertRaises((AuthorityError,ValidationError)):parse_founder_root(changed)

    def test_no_library_or_symbol_selection_api(self):
        with self.assertRaises(TypeError):v.validate_public_key(PUBLIC,path='/tmp/lib.so')
        with self.assertRaises(TypeError):v.validate_public_key(PUBLIC,symbol='anything')

    def test_environment_overrides_denied(self):
        for key in ('LD_PRELOAD','LD_LIBRARY_PATH','LIBSODIUM_PATH','SODIUM_LIBRARY'):
            with patch.dict(os.environ,{key:'/tmp/anything'}),self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)


class DependencyTests(unittest.TestCase):
    def setUp(self):
        for name,value in (('_native',None),('_failed',False)):
            p=patch.object(v,name,value);p.start();self.addCleanup(p.stop)

    def fake(self):
        return SimpleNamespace(sodium_init=Mock(return_value=0),
            crypto_core_ed25519_is_valid_point=Mock(side_effect=lambda raw:1 if bytes(raw)==PUBLIC else 0))

    def test_missing_library(self):
        with patch.object(v,'_load_fixed',side_effect=FileNotFoundError),self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)

    def test_wrong_library_identity(self):
        with patch.object(v.os,'readlink',return_value='/tmp/attacker.so'),self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)

    def test_missing_symbols(self):
        for symbol in ('sodium_init','crypto_core_ed25519_is_valid_point'):
            library=self.fake();delattr(library,symbol)
            with patch.object(v,'_failed',False),patch.object(v,'_load_fixed',return_value=library),self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)

    def test_initialization_failure(self):
        library=self.fake();library.sodium_init.return_value=-1
        with patch.object(v,'_load_fixed',return_value=library),self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)

    def test_unexpected_results_and_native_errors(self):
        for result in (-1,2,None):
            library=self.fake();library.crypto_core_ed25519_is_valid_point=Mock(return_value=result)
            with patch.object(v,'_failed',False),patch.object(v,'_load_fixed',return_value=library),self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)
        library=self.fake();library.crypto_core_ed25519_is_valid_point.side_effect=OSError('synthetic')
        with patch.object(v,'_failed',False),patch.object(v,'_load_fixed',return_value=library),self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)

    def test_dependency_failure_latched_without_fallback(self):
        with patch.object(v,'_load_fixed',side_effect=OSError) as load:
            for _ in range(2):
                with self.assertRaises(AuthorityError):v.validate_public_key(PUBLIC)
            self.assertEqual(load.call_count,1)

    def test_false_positive_feature_denied(self):
        library=self.fake();library.crypto_core_ed25519_is_valid_point=Mock(return_value=1)
        with patch.object(v,'_load_fixed',return_value=library),self.assertRaises(AuthorityError):v.preflight()


class ConsumptionTests(unittest.TestCase):
    def test_invalid_then_valid_then_second_genesis(self):
        fixture=genesis_tests.GenesisTests('test_unbound_complete');fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with self.assertRaises(AuthorityError):fixture.service.propose(g.canonical_json(fixture.candidate).encode(),base64.b64encode(BAD).decode())
        fixture.service.ledger.require_virgin()
        self.assertIsNone(fixture.service.pending)
        self.assertEqual(fixture.events[-1],('GENESIS_KEY_DENIED',{'reason':'INVALID_FOUNDER_ROOT_KEY'}))
        fixture.bind()
        with self.assertRaises(AuthorityError):fixture.bind()
