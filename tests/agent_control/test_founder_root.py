"""Synthetic Ed25519 keys only; no hardware signer or installed trust files."""
import base64
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from tools.agent_control.founder_crypto import FounderRoot, OpenSSLVerifier, sealed, PURPOSES
from tools.agent_control.founder_session import FounderSessions
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.installation_approval import propose
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.types import AuthorityError, ValidationError

# Public RFC 8032 test vector 2. This seed is test data, never a founder key.
SEED = bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb')
PUBLIC = bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
ROOT = FounderRoot('synthetic-only', PUBLIC, 1)
BOOT = '00000000-0000-4000-8000-000000000001'


def sign(message):
    """TEST ONLY software signer for the public test seed."""
    key = sealed(bytes.fromhex('302e020100300506032b657004220420') + SEED)
    data = sealed(message)
    try:
        result = subprocess.run(('/usr/bin/openssl', 'pkeyutl', '-sign', '-rawin',
            '-keyform', 'DER', '-inkey', f'/proc/self/fd/{key}', '-in', f'/proc/self/fd/{data}'),
            pass_fds=(key, data), close_fds=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2,
            env={'LANG': 'C', 'OPENSSL_CONF': '/dev/null'}, check=True)
        if len(result.stdout) != 64:
            raise AssertionError('Synthetic signing failed.')
        return result.stdout
    finally:
        os.close(data)
        os.close(key)


class OpenSSLTests(unittest.TestCase):
    def test_valid_public_key_verification(self):
        OpenSSLVerifier().verify(ROOT, b'synthetic', sign(b'synthetic'))

    def test_modified_message(self):
        with self.assertRaises(AuthorityError):
            OpenSSLVerifier().verify(ROOT, b'modified', sign(b'synthetic'))

    def test_wrong_public_key(self):
        with self.assertRaises(AuthorityError):
            OpenSSLVerifier().verify(FounderRoot('wrong', bytes(32), 1), b'x', sign(b'x'))

    def test_malformed_signature(self):
        for signature in (b'', bytes(63), bytes(65)):
            with self.assertRaises(ValidationError):
                OpenSSLVerifier().verify(ROOT, b'x', signature)

    def test_algorithm_closed(self):
        with self.assertRaises(ValidationError):
            FounderRoot('wrong', PUBLIC, 1, algorithm='RSA')

    def test_executable_not_caller_selected(self):
        with self.assertRaises(TypeError):
            OpenSSLVerifier('/tmp/openssl')

    def test_environment_ignored(self):
        with patch.dict(os.environ, {'OPENSSL_CONF': '/missing', 'LD_PRELOAD': '/missing',
                                     'OPENSSL': '/missing', 'PATH': '/missing'}):
            OpenSSLVerifier().verify(ROOT, b'x', sign(b'x'))

    def test_subcommand_not_caller_selected(self):
        with self.assertRaises(TypeError):
            OpenSSLVerifier().verify(ROOT, b'x', bytes(64), command='sign')

    def test_timeout_denies(self):
        with patch('tools.agent_control.founder_crypto.subprocess.run',
                   side_effect=subprocess.TimeoutExpired('synthetic', 2)):
            with self.assertRaises(AuthorityError):
                OpenSSLVerifier().verify(ROOT, b'x', bytes(64))

    def test_nonzero_denies(self):
        with self.assertRaises(AuthorityError):
            OpenSSLVerifier().verify(ROOT, b'x', bytes(64))

    def test_missing_binary_denies(self):
        with patch.object(OpenSSLVerifier, '_executable', side_effect=FileNotFoundError):
            with self.assertRaises(AuthorityError):
                OpenSSLVerifier().verify(ROOT, b'x', bytes(64))

    def test_known_signature_without_private_key(self):
        signature = bytes.fromhex('92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da'
                                  '085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00')
        OpenSSLVerifier().verify(ROOT, b'\x72', signature)


class FounderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (Path(__file__).resolve().parents[2] /
            'docs/agent-control/review/m3-generation-1/payload/etc/bonup-agent-control/approved-installation.json').read_bytes()
        cls.proposal = propose(cls.raw)

    def setUp(self):
        self.peer = PeerIdentity(1000, 1000, 1234)
        self.process = ProcessIdentity(BOOT, 1234, 42)
        self.now = datetime(2026, 9, 15, tzinfo=timezone.utc)
        self.ticks = 100.0
        self.events = []
        self.engine = FounderSessions(ROOT, observe=lambda: (self.peer, self.process),
            audit=lambda event, correlation: self.events.append((event, correlation)),
            clock=lambda: self.now, boottime=lambda: self.ticks)

    def issue(self, purpose=PURPOSES[0]):
        return self.engine.issue(purpose, self.raw, self.proposal,
            installation_receipt_digest='a' * 64 if purpose == PURPOSES[1] else None)

    def submit(self, challenge):
        return self.engine.submit(dict(challenge_id=digest(challenge),
            signature=base64.b64encode(sign(canonical_json(challenge).encode())).decode()))

    def test_root_not_founder(self):
        self.peer = PeerIdentity(0, 0, 1234)
        with self.assertRaises(AuthorityError): self.issue()

    def test_uid_alone_denied(self):
        challenge = self.issue()
        with self.assertRaises(AuthorityError):
            self.engine.submit(dict(challenge_id=digest(challenge), signature=base64.b64encode(bytes(64)).decode()))

    def test_signed_approval_inactive(self):
        result = self.engine.approve_installation(self.submit(self.issue()), self.raw, self.proposal)
        self.assertFalse(result['decision']['activation'])
        self.assertFalse(result['decision']['integration_services_approved'])

    def test_key_override_denied(self):
        challenge = self.issue()
        with self.assertRaises(ValidationError):
            self.engine.submit(dict(challenge_id=digest(challenge), signature='', public_key=PUBLIC.hex()))

    def test_process_identity_changes_deny(self):
        for peer, process in (
            (PeerIdentity(1000, 1000, 99), ProcessIdentity(BOOT, 99, 42)),
            (self.peer, ProcessIdentity(BOOT, 1234, 43)),
            (self.peer, ProcessIdentity('different-boot', 1234, 42)),
        ):
            with self.subTest(process=process):
                old_peer, old_process = self.peer, self.process
                challenge = self.issue()
                self.peer, self.process = peer, process
                with self.assertRaises(AuthorityError): self.submit(challenge)
                self.peer, self.process = old_peer, old_process

    def test_changed_signed_fields_deny(self):
        for field in ('purpose', 'enrollment_generation', 'nonce', 'root_generation', 'binding'):
            with self.subTest(field=field):
                original = self.issue()
                altered = deepcopy(original)
                altered[field] = 'forged'
                with self.assertRaises(AuthorityError):
                    self.engine.submit(dict(challenge_id=digest(original),
                        signature=base64.b64encode(sign(canonical_json(altered).encode())).decode()))

    def test_expiry(self):
        challenge = self.issue()
        self.now += timedelta(seconds=61)
        with self.assertRaises(AuthorityError): self.submit(challenge)

    def test_rollback_does_not_extend(self):
        challenge = self.issue()
        self.now -= timedelta(days=1)
        self.ticks += 61
        with self.assertRaises(AuthorityError): self.submit(challenge)

    def test_signature_replay(self):
        challenge = self.issue()
        self.submit(challenge)
        with self.assertRaises(AuthorityError): self.submit(challenge)

    def test_second_consumption(self):
        session = self.submit(self.issue())
        self.engine.approve_installation(session, self.raw, self.proposal)
        with self.assertRaises(AuthorityError):
            self.engine.approve_installation(session, self.raw, self.proposal)

    def test_transfer_after_signature(self):
        session = self.submit(self.issue())
        self.process = ProcessIdentity(BOOT, 1234, 99)
        with self.assertRaises(AuthorityError):
            self.engine.approve_installation(session, self.raw, self.proposal)

    def test_purposes_not_interchangeable(self):
        for purpose, other in ((PURPOSES[0], PURPOSES[1]), (PURPOSES[1], PURPOSES[0])):
            session = self.submit(self.issue(purpose))
            with self.assertRaises(AuthorityError):
                self.engine.consume(session, other, self.proposal['binding'])

    def test_activation_unavailable(self):
        with self.assertRaises(AuthorityError): self.issue('FOUNDER_ACTIVATION_APPROVAL')

    def test_audit_excludes_signature(self):
        self.engine.approve_installation(self.submit(self.issue()), self.raw, self.proposal)
        self.assertIn('INSTALLATION_APPROVAL_ISSUED', [e[0] for e in self.events])
        self.assertTrue(all(len(correlation) == 64 for _, correlation in self.events))

    def test_audit_failure_denies(self):
        self.engine.audit = lambda *args: (_ for _ in ()).throw(OSError('unavailable'))
        with self.assertRaises(OSError): self.issue()
        self.assertFalse(self.engine.pending)
